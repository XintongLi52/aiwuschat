# AIWUS - 智能对话助手

基于 Flask + MySQL + OpenAI API 的多角色智能对话系统，支持用户注册登录、聊天记录持久化、多会话管理。

## 功能特点

- **用户系统** - 邮箱注册/登录，JWT 认证，多用户隔离
- **聊天记录持久化** - 所有对话存入 MySQL，刷新不丢失
- **会话管理** - 新建对话、切换历史对话、删除对话（侧边栏）
- **响应式设计** - PC 端侧边栏常驻，手机端抽屉式滑出（汉堡菜单）
- **多角色系统** - 陪伴型 + 知识型角色自由切换
- **流式输出** - 实时逐字显示 AI 回复
- **视频头像** - 对话中角色头像循环播放动态视频
- **Markdown 渲染** - 自动渲染代码块、列表、表格等格式
- **Web Search** - 一键开启联网搜索（`enable_search: true`）
- **文件上传** - 支持上传图片（多模态识图）和文档（文本内容提取）
- **追问建议** - AI 回答后自动生成 3 个追问选项，点击淡出并发送
- **自动标题** - 首次对话后 AI 自动生成会话标题
- **独立配置** - 模型、参数、数据库连接集中在 `config.json` 管理

## 角色列表

| 角色 | 类型 | 描述 |
|------|------|------|
| Urbania | 陪伴型 | 温柔治愈的城市女孩，适合日常聊天 |
| Urbanest | 陪伴型 | 阳光开朗的城市男孩 |
| Lumina | 灵感导师 / 聊天导师 | 陪你思考、激发创意、探讨话题 |


> 其他历史角色（IntelliGuide、Academician）已在前端 `hidden`，代码仍保留，随时可恢复显示。

## 角色头像配置

三个角色的头像/动画资源集中在 `index.html` 的 `roleData` 对象里（约第 294-296 行）。前端会根据文件扩展名自动选择渲染方式：

- **图片** (`.png` / `.jpg` / `.jpeg` / `.gif` / `.webp`) → `<img>` 标签，静态显示
- **视频** (`.mp4` / `.webm` / `.ogg`) → `<video>` 标签，带循环动画

### 切换头像 / 从图片改为动态视频

编辑 `index.html` 中 `roleData` 的对应字段即可，无需改动其它代码：

```javascript
const roleData = {
  xiaoying: { name: 'Urbania', avatar: '/img/Urbania.png', video: '/img/Urbania.png', ... },
  xiaozhe:  { name: 'Urbanest', avatar: '/img/Urbanest.png', video: '/img/Urbanest.png', ... },
  aiwus:    { name: 'Lumina', avatar: '/img/lumina.jpg', video: '/img/lumina.jpg', ... },
};
```

| 字段 | 使用位置 | 建议类型 |
|------|---------|---------|
| `avatar` | 角色卡片、聊天顶栏小头像 | 图片（静态） |
| `video` | 欢迎页大头像、对话气泡左侧头像 | 图片或视频均可 |

**示例：把 Urbania 改成动态视频**

1. 把视频文件（如 `Urbania.mp4`）放入 `pic/` 或 `img/` 目录
2. 只改 `video` 字段指向新路径：

```javascript
xiaoying: { name: 'Urbania', avatar: '/img/Urbania.png', video: '/pic/Urbania.mp4', ... },
```

保存刷新即可，渲染逻辑会自动用 `<video>` 标签。

### 动画播放逻辑（仅视频生效，图片自动忽略）

| 位置 | 进入角色 | 用户发送 / AI 回答中 | AI 回答结束 |
|------|---------|--------------------|------------|
| **欢迎页大头像** | 暂停（第一帧） | 循环播放 | 暂停并重置到第一帧 |
| **聊天气泡左侧头像** | 始终循环播放 | 始终循环播放 | 始终循环播放 |

> 播放/暂停控制集中在 `doSend()`：发送时 `wv.play()`，`finally` 里 `wv.pause(); wv.currentTime = 0`。静态图片模式下 `querySelector('video')` 返回 null，这两处自动跳过。

## 项目结构

```
├── index.html          # 前端单页应用（登录/注册 + 侧边栏 + 聊天）
├── server.py           # Flask 后端（用户系统 + 会话管理 + AI 对话）
├── config.json         # 配置文件（API + MySQL + 模型参数）
├── requirements.txt    # Python 依赖
├── Dockerfile          # Docker 部署
├── .dockerignore
├── img/                # 新版角色头像资源（Urbania/Urbanest/lumina）
├── pic/                # 历史角色图片/视频资源（仍保留，可随时切回）
└── uploads/            # 用户上传文件目录（自动创建）
```

## 前置条件

- Python 3.10+
- MySQL 5.7+（已运行）
- OpenAI 兼容的 API Key

## 快速启动

### 1. 编辑配置

```bash
vim config.json
```

```json
{
  "api_key": "sk-your-key",
  "base_url": "https://your-api.com/v1",
  "model": "qwen3.5-plus",
  "temperature": 0.7,
  "max_tokens": 1024,
  "stream": true,
  "disable_thinking": true,
  "jwt_secret": "change-me-to-random-string",
  "mysql": {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "password",
    "database": "aiwus"
  }
}
```

### 2. 安装依赖并启动

```bash
pip install -r requirements.txt
python server.py
```

浏览器打开 `http://localhost:8081`

> 数据库和表会自动创建，无需手动建表。

### Docker 部署

```bash
# 构建
docker build -t aiwus .

# 运行（确保 MySQL 可从容器内访问）
docker run -d -p 8080:8080 --name aiwus aiwus
```

> 如果 MySQL 在宿主机，`mysql.host` 应设为 `host.docker.internal`（Mac/Win）或宿主机 IP。

### 生产部署（systemd + gunicorn + Nginx）

```bash
pip install -r requirements.txt

sudo tee /etc/systemd/system/aiwus.service << 'EOF'
[Unit]
Description=AIWUS Chat Service
After=network.target mysql.service

[Service]
User=www-data
WorkingDirectory=/opt/aiwus
ExecStart=/usr/local/bin/gunicorn -w 2 -b 127.0.0.1:8080 --timeout 120 server:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now aiwus
```

Nginx 配置：

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_buffering off;
        proxy_read_timeout 120s;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `api_key` | API 密钥 | 必填 |
| `base_url` | API 地址（`/v1` 结尾） | 必填 |
| `model` | 模型名称 | `qwen3.5-plus` |
| `temperature` | 创造性（0-1） | `0.7` |
| `max_tokens` | 最大输出长度 | `1024` |
| `stream` | 流式输出 | `true` |
| `disable_thinking` | 关闭推理思考 | `true` |
| `jwt_secret` | JWT 签名密钥 | 必改 |
| `mysql.host` | MySQL 地址 | `127.0.0.1` |
| `mysql.port` | MySQL 端口 | `3306` |
| `mysql.user` | MySQL 用户名 | `root` |
| `mysql.password` | MySQL 密码 | 必填 |
| `mysql.database` | 数据库名 | `aiwus` |

## 数据库结构

启动时自动创建，包含 3 张表：

- **users** - 用户表（id, email, password_hash, nickname）
- **conversations** - 会话表（id, user_id, role, title）
- **messages** - 消息表（id, conversation_id, role, content）

## API 接口

| 接口 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/api/register` | POST | - | 注册（email, password, nickname） |
| `/api/login` | POST | - | 登录，返回 JWT token |
| `/api/user` | GET | JWT | 获取当前用户信息 |
| `/api/conversations` | GET | JWT | 获取会话列表（?role=xxx 过滤） |
| `/api/conversations` | POST | JWT | 创建新会话 |
| `/api/conversations/:id` | DELETE | JWT | 删除会话 |
| `/api/conversations/:id/messages` | GET | JWT | 获取历史消息 |
| `/api/chat` | POST | JWT | 对话（流式，自动存储） |
| `/api/upload` | POST | JWT | 文件上传 |
| `/api/suggestions` | POST | JWT | 追问建议 |

## 技术栈

- **前端**: HTML5 + CSS3 + Vanilla JS + marked.js
- **后端**: Python Flask + Flask-CORS + OpenAI SDK + PyJWT + PyMySQL
- **数据库**: MySQL
- **部署**: Docker (Alpine) / Gunicorn + Nginx / 直接运行
