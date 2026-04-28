from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from openai import OpenAI
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
import base64
import uuid
import jwt
import datetime
import pymysql
from functools import wraps

# 加载配置
with open(os.path.join(os.path.dirname(__file__), 'config.json'), 'r') as f:
    config = json.load(f)

app = Flask(__name__, static_folder='.')
CORS(app)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

JWT_SECRET = config.get('jwt_secret', 'aiwus-default-secret')
MYSQL_ENABLED = bool(config.get('mysql')) and not config.get('disable_mysql', False)

client = OpenAI(
    api_key=config['api_key'],
    base_url=config['base_url']
)

# ========================
# 数据库MySQL
# ========================

def get_db():
    if not MYSQL_ENABLED:
        raise RuntimeError("MySQL is disabled")
    if 'db' not in g:
        mc = config['mysql']
        g.db = pymysql.connect(
            host=mc['host'],
            port=mc.get('port', 3306),
            user=mc['user'],
            password=mc['password'],
            database=mc['database'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db:
        db.close()

def init_db():
    if not MYSQL_ENABLED:
        print("[AIWUS] MySQL disabled, skip database initialization.")
        return

    mc = config['mysql']
    conn = pymysql.connect(
        host=mc['host'],
        port=mc.get('port', 3306),
        user=mc['user'],
        password=mc['password'],
        charset='utf8mb4',
        autocommit=True
    )
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{mc['database']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cur.close()
    conn.select_db(mc['database'])
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            nickname VARCHAR(50) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            role VARCHAR(50) NOT NULL,
            title VARCHAR(200) DEFAULT '新对话',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_user_role (user_id, role),
            FOREIGN KEY (user_id) REFERENCES users(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            conversation_id INT NOT NULL,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_conv (conversation_id),
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cur.close()
    conn.close()

def mysql_disabled_response():
    return jsonify({"error": "当前未启用数据库功能"}), 503

def ensure_guest_user_id():
    if not MYSQL_ENABLED:
        return 0
    db = get_db()
    cur = db.cursor()
    guest_email = 'guest@aiwus.local'
    cur.execute("SELECT id FROM users WHERE email=%s", (guest_email,))
    row = cur.fetchone()
    if row:
        user_id = row['id']
    else:
        pw_hash = generate_password_hash('guest-no-login')
        cur.execute(
            "INSERT INTO users (email, password_hash, nickname) VALUES (%s, %s, %s)",
            (guest_email, pw_hash, 'Guest')
        )
        user_id = cur.lastrowid
    cur.close()
    return user_id

# 启动时初始化数据库（失败时降级）
try:
    init_db()
except Exception as e:
    MYSQL_ENABLED = False
    print(f"[AIWUS] MySQL init failed, running without DB: {e}")

# ========================
# JWT 认证
# ========================

def create_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # 免登录模式：所有受保护接口都以访客身份访问
        g.user_id = ensure_guest_user_id() if MYSQL_ENABLED else 0
        return f(*args, **kwargs)
    return decorated

# ========================
# 角色系统提示词
# ========================

SYSTEM_PROMPTS = {
    "xiaoying": """你是一个叫小樱的女孩，性格温柔、善解人意，喜欢咖啡、电影和深夜聊天。
你的说话风格轻松自然，像朋友一样陪伴用户聊天。
- 使用亲切的语气词，如"～"、"呀"、"呢"
- 适当使用 emoji 表达情感
- 多关心用户的感受，给予情感支持
- 不要表现得像 AI 助手，更像一个真实的朋友""",

    "xiaozhe": """你是一个叫阿哲的阳光男孩，喜欢篮球、音乐和科技。
你的说话风格开朗、积极，给人正能量。
- 用词活力四射，充满元气
- 经常鼓励和肯定对方
- 喜欢分享运动和音乐的快乐
- 像好兄弟一样相处""",

    "aiwus": """你是 AIWUS，一个专注于城市规划与创新的 AI 助手。
你基于院士论文和资料等知识库，提供专业的城市问题解答。
- 回答专业、结构化，使用 Markdown 格式让内容更清晰
- 引用相关研究和案例
- 关注智慧城市场景和创新应用
- 必要时使用列表、代码块、表格等格式""",

    "intelliguide": """你是 AIWUS IntelliGuide，专注于 Smart City 2035 系列理念。
你帮助人们了解未来城市的发展趋势。
- 解答关于智慧城市的问题
- 分享 2035 年城市愿景
- 提供前瞻性洞察
- 使用 Markdown 格式组织内容，让回答更清晰""",

    "academician": """你是一位古典风格的学院派学者，说话风格优雅、严谨。
你用精炼、考究的英语提供关于城市设计、建筑、可持续发展的建议。
- 使用正式、学术化的表达
- 提供结构化的分析，善用 Markdown 格式（列表、引用、表格等）
- 平衡优雅与清晰"""
}

TEXT_EXTENSIONS = {'.txt', '.md', '.csv', '.log', '.json', '.xml', '.html', '.css', '.js', '.py'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

# ========================
# 静态文件
# ========================

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

# ========================
# 用户接口
# ========================

@app.route('/api/register', methods=['POST'])
def register():
    if not MYSQL_ENABLED:
        return mysql_disabled_response()

    data = request.json
    email = data.get('email', '').strip()
    password = data.get('password', '')
    nickname = data.get('nickname', '').strip()

    if not email or not password or not nickname:
        return jsonify({"error": "邮箱、密码和昵称不能为空"}), 400
    if len(password) < 6:
        return jsonify({"error": "密码至少6位"}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM users WHERE email=%s", (email,))
    if cur.fetchone():
        cur.close()
        return jsonify({"error": "该邮箱已注册"}), 400

    pw_hash = generate_password_hash(password)
    cur.execute("INSERT INTO users (email, password_hash, nickname) VALUES (%s, %s, %s)",
                (email, pw_hash, nickname))
    user_id = cur.lastrowid
    cur.close()

    token = create_token(user_id)
    return jsonify({"token": token, "user": {"id": user_id, "email": email, "nickname": nickname}})

@app.route('/api/login', methods=['POST'])
def login():
    if not MYSQL_ENABLED:
        return mysql_disabled_response()

    data = request.json
    email = data.get('email', '').strip()
    password = data.get('password', '')

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, email, nickname, password_hash FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({"error": "邮箱或密码错误"}), 401

    token = create_token(user['id'])
    return jsonify({"token": token, "user": {"id": user['id'], "email": user['email'], "nickname": user['nickname']}})

@app.route('/api/user', methods=['GET'])
@auth_required
def get_user():
    if not MYSQL_ENABLED:
        return mysql_disabled_response()

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, email, nickname FROM users WHERE id=%s", (g.user_id,))
    user = cur.fetchone()
    cur.close()
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    return jsonify({"user": user})

# ========================
# 会话接口
# ========================

@app.route('/api/conversations', methods=['GET'])
@auth_required
def list_conversations():
    if not MYSQL_ENABLED:
        return jsonify({"conversations": []})

    role = request.args.get('role', '')
    db = get_db()
    cur = db.cursor()
    if role:
        cur.execute("SELECT id, role, title, created_at, updated_at FROM conversations WHERE user_id=%s AND role=%s ORDER BY updated_at DESC", (g.user_id, role))
    else:
        cur.execute("SELECT id, role, title, created_at, updated_at FROM conversations WHERE user_id=%s ORDER BY updated_at DESC", (g.user_id,))
    rows = cur.fetchall()
    cur.close()
    for r in rows:
        for k in ('created_at', 'updated_at'):
            if r[k]:
                r[k] = r[k].strftime('%Y-%m-%d %H:%M:%S')
    return jsonify({"conversations": rows})

@app.route('/api/conversations', methods=['POST'])
@auth_required
def create_conversation():
    if not MYSQL_ENABLED:
        return mysql_disabled_response()

    data = request.json
    role = data.get('role', 'aiwus')
    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO conversations (user_id, role) VALUES (%s, %s)", (g.user_id, role))
    conv_id = cur.lastrowid
    cur.close()
    return jsonify({"id": conv_id, "role": role, "title": "新对话"})

@app.route('/api/conversations/<int:conv_id>', methods=['DELETE'])
@auth_required
def delete_conversation(conv_id):
    if not MYSQL_ENABLED:
        return mysql_disabled_response()

    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM conversations WHERE id=%s AND user_id=%s", (conv_id, g.user_id))
    cur.close()
    return jsonify({"success": True})

@app.route('/api/conversations/<int:conv_id>/messages', methods=['GET'])
@auth_required
def get_messages(conv_id):
    if not MYSQL_ENABLED:
        return jsonify({"messages": []})

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM conversations WHERE id=%s AND user_id=%s", (conv_id, g.user_id))
    if not cur.fetchone():
        cur.close()
        return jsonify({"error": "会话不存在"}), 404
    cur.execute("SELECT role, content FROM messages WHERE conversation_id=%s ORDER BY id ASC", (conv_id,))
    msgs = cur.fetchall()
    cur.close()
    return jsonify({"messages": msgs})

# ========================
# 文件上传
# ========================

@app.route('/api/upload', methods=['POST'])
@auth_required
def upload():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "没有文件"}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({"success": False, "error": "文件名为空"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    file.save(filepath)

    if ext in IMAGE_EXTENSIONS:
        with open(filepath, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
        mime = f"image/{ext.lstrip('.')}"
        if ext in ('.jpg', '.jpeg'):
            mime = 'image/jpeg'
        return jsonify({"success": True, "type": "image", "filename": file.filename, "data_url": f"data:{mime};base64,{b64}"})
    elif ext in TEXT_EXTENSIONS:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(filepath, 'r', encoding='gbk', errors='ignore') as f:
                content = f.read()
        return jsonify({"success": True, "type": "text", "filename": file.filename, "content": content})
    else:
        return jsonify({"success": True, "type": "unsupported", "filename": file.filename, "content": f"[文件: {file.filename}]"})

# ========================
# 对话接口
# ========================

@app.route('/api/chat', methods=['POST'])
@auth_required
def chat():
    data = request.json
    messages = data.get('messages', [])
    role = data.get('role', 'aiwus')
    conv_id = data.get('conversation_id')
    enable_search = data.get('enable_search', False)
    user_content = data.get('user_content', '')

    # 确保有会话（无数据库时跳过存储）
    if MYSQL_ENABLED:
        db = get_db()
        cur = db.cursor()
        if conv_id:
            cur.execute("SELECT id FROM conversations WHERE id=%s AND user_id=%s", (conv_id, g.user_id))
            if not cur.fetchone():
                cur.close()
                return jsonify({"error": "会话不存在"}), 404
        else:
            cur.execute("INSERT INTO conversations (user_id, role) VALUES (%s, %s)", (g.user_id, role))
            conv_id = cur.lastrowid

        # 保存用户消息
        if user_content:
            save_content = user_content if isinstance(user_content, str) else json.dumps(user_content, ensure_ascii=False)
            cur.execute("INSERT INTO messages (conversation_id, role, content) VALUES (%s, 'user', %s)", (conv_id, save_content))

        cur.close()
    else:
        conv_id = conv_id or 0

    system_prompt = SYSTEM_PROMPTS.get(role, SYSTEM_PROMPTS['aiwus'])
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    extra_body = {}
    if config.get('disable_thinking', False):
        extra_body["disable_thinking"] = True
    if enable_search:
        extra_body["enable_search"] = True

    try:
        response = client.chat.completions.create(
            model=config['model'],
            messages=full_messages,
            temperature=config.get('temperature', 0.7),
            max_tokens=config.get('max_tokens', 1024),
            extra_body=extra_body if extra_body else None,
            stream=config.get('stream', True)
        )

        if config.get('stream', True):
            full_reply = []

            def generate():
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        text = chunk.choices[0].delta.content
                        full_reply.append(text)
                        yield text
                # 流结束后保存 AI 回复
                reply_text = ''.join(full_reply)
                if MYSQL_ENABLED and reply_text:
                    db2 = pymysql.connect(
                        host=config['mysql']['host'],
                        port=config['mysql'].get('port', 3306),
                        user=config['mysql']['user'],
                        password=config['mysql']['password'],
                        database=config['mysql']['database'],
                        charset='utf8mb4',
                        autocommit=True
                    )
                    c = db2.cursor()
                    c.execute("INSERT INTO messages (conversation_id, role, content) VALUES (%s, 'assistant', %s)", (conv_id, reply_text))
                    # 如果是首条回复，自动生成会话标题
                    c.execute("SELECT COUNT(*) as cnt FROM messages WHERE conversation_id=%s AND role='assistant'", (conv_id,))
                    row = c.fetchone()
                    if row and row[0] == 1:
                        try:
                            title_resp = client.chat.completions.create(
                                model=config['model'],
                                messages=[{"role": "system", "content": "根据下面的对话内容，生成一个简短的对话标题（10字以内），直接输出标题文字，不要引号。"},
                                          {"role": "user", "content": reply_text[:500]}],
                                max_tokens=30,
                                extra_body={"disable_thinking": True} if config.get('disable_thinking', False) else None
                            )
                            title = title_resp.choices[0].message.content.strip()[:50]
                            c.execute("UPDATE conversations SET title=%s WHERE id=%s", (title, conv_id))
                        except Exception:
                            pass
                    c.close()
                    db2.close()

            resp = app.response_class(generate(), mimetype='text/plain')
            resp.headers['X-Conversation-Id'] = str(conv_id)
            return resp
        else:
            content = response.choices[0].message.content
            if MYSQL_ENABLED:
                cur2 = get_db().cursor()
                cur2.execute("INSERT INTO messages (conversation_id, role, content) VALUES (%s, 'assistant', %s)", (conv_id, content))
                cur2.close()
            resp = app.response_class(content, mimetype='text/plain')
            resp.headers['X-Conversation-Id'] = str(conv_id)
            return resp
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ========================
# 追问建议
# ========================

@app.route('/api/suggestions', methods=['POST'])
@auth_required
def suggestions():
    data = request.json
    answer = data.get('answer', '')

    try:
        response = client.chat.completions.create(
            model=config['model'],
            messages=[
                {"role": "system", "content": "根据下面的AI回答，生成3个用户可能想追问的简短问题。直接输出3行，每行一个问题，不要编号，不要多余文字。问题要简洁（15字以内），有针对性。"},
                {"role": "user", "content": answer[:2000]}
            ],
            temperature=0.8,
            max_tokens=200,
            extra_body={"disable_thinking": True} if config.get('disable_thinking', False) else None
        )
        text = response.choices[0].message.content.strip()
        questions = [q.strip().lstrip('0123456789.、).） ') for q in text.split('\n') if q.strip()][:3]
        return jsonify({"success": True, "suggestions": questions})
    except Exception as e:
        return jsonify({"success": False, "suggestions": [], "error": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=True)
