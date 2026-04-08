from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openai import OpenAI
import os
import json
import base64
import uuid

# 加载配置
with open(os.path.join(os.path.dirname(__file__), 'config.json'), 'r') as f:
    config = json.load(f)

app = Flask(__name__, static_folder='.')
CORS(app)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

client = OpenAI(
    api_key=config['api_key'],
    base_url=config['base_url']
)

# 角色系统提示词
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

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

@app.route('/api/upload', methods=['POST'])
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
        return jsonify({
            "success": True,
            "type": "image",
            "filename": file.filename,
            "data_url": f"data:{mime};base64,{b64}"
        })
    elif ext in TEXT_EXTENSIONS:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(filepath, 'r', encoding='gbk', errors='ignore') as f:
                content = f.read()
        return jsonify({
            "success": True,
            "type": "text",
            "filename": file.filename,
            "content": content
        })
    else:
        return jsonify({
            "success": True,
            "type": "unsupported",
            "filename": file.filename,
            "content": f"[文件: {file.filename}]"
        })

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    messages = data.get('messages', [])
    role = data.get('role', 'aiwus')
    enable_search = data.get('enable_search', False)

    system_prompt = SYSTEM_PROMPTS.get(role, SYSTEM_PROMPTS['aiwus'])

    full_messages = [
        {"role": "system", "content": system_prompt}
    ] + messages

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
            def generate():
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content

            return app.response_class(
                generate(),
                mimetype='text/plain'
            )
        else:
            content = response.choices[0].message.content
            return app.response_class(content, mimetype='text/plain')
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/suggestions', methods=['POST'])
def suggestions():
    data = request.json
    answer = data.get('answer', '')
    role = data.get('role', 'aiwus')

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
