# AIWUS - 智能对话助手

基于 Flask + OpenAI API 的多角色智能对话系统，支持陪伴聊天和知识问答两种模式。

## 功能特点

- **多角色系统** - 陪伴型 + 知识型角色自由切换
- **流式输出** - 实时逐字显示 AI 回复
- **视频头像** - 回复时角色头像循环播放动态视频
- **Markdown 渲染** - 自动渲染代码块、列表、表格等格式
- **Web Search** - 一键开启联网搜索，AI 回答更准确
- **文件上传** - 支持上传图片（多模态识图）和文档（内容提取）
- **追问建议** - AI 回答后自动生成 3 个追问选项，点击即可继续对话
- **独立配置** - 模型、参数、API 密钥集中在 `config.json` 管理

## 角色列表

| 角色 | 类型 | 描述 |
|------|------|------|
| 小樱 Sakura | 陪伴型 | 温柔治愈的女孩，适合日常聊天 |
| 阿哲 Alex | 陪伴型 | 阳光开朗的运动男孩 |
| AIWUS | 知识型 | 城市规划与创新专业助手 |
| AIWUS IntelliGuide | 知识型 | Smart City 2035 专家 |
| Classical-Style Academician | 知识型 | 古典风格学者顾问 |

## 项目结构

```
├── index.html          # 前端单页应用
├── server.py           # Flask 后端服务
├── config.json         # 配置文件（模型、API、参数）
├── Dockerfile          # Docker 部署文件
├── .dockerignore       # Docker 忽略文件
├── pic/                # 角色图片/视频资源
│   ├── girl.jpg / girl.mp4
│   └── boy.jpg / boy.mp4
└── uploads/            # 用户上传文件目录（自动创建）
```

## 快速启动

### 方式一：直接运行

```bash
# 1. 安装依赖
pip install flask flask-cors openai

# 2. 编辑配置
vim config.json   # 修改 api_key 和 base_url

# 3. 启动服务
python server.py
```

浏览器打开 `http://localhost:8081`

### 方式二：Docker 部署（推荐）

```bash
# 1. 编辑配置
vim config.json   # 修改 api_key 和 base_url

# 2. 构建镜像
docker build -t aiwus .

# 3. 运行容器
docker run -d -p 8080:8080 --name aiwus aiwus
```

浏览器打开 `http://localhost:8080`

#### Docker 管理命令

```bash
# 查看日志
docker logs -f aiwus

# 停止
docker stop aiwus

# 重启
docker restart aiwus

# 删除并重建（修改配置后）
docker rm -f aiwus && docker build -t aiwus . && docker run -d -p 8080:8080 --name aiwus aiwus
```

### 生产部署

```bash
# 1. 安装
pip install flask flask-cors openai gunicorn

# 2. 创建 systemd 服务
sudo tee /etc/systemd/system/aiwus.service << 'EOF'
[Unit]
Description=AIWUS Chat Service
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/aiwus
ExecStart=/usr/local/bin/gunicorn -w 2 -b 127.0.0.1:8080 --timeout 120 server:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 3. 启动
sudo systemctl enable --now aiwus
```

配合 Nginx 反向代理使用（注意关闭 `proxy_buffering` 以支持流式输出）：

```nginx
server {
    listen 443 ssl;
    server_name domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_buffering off;
        proxy_read_timeout 240s;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 配置说明

所有配置集中在 `config.json`：

```json
{
  "api_key": "sk-xxx",
  "base_url": "https://api.xx.com/v1",
  "model": "qwen3.5-plus",
  "temperature": 0.7,
  "max_tokens": 8192,
  "stream": true,
  "disable_thinking": true
}
```

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `api_key` | API 密钥 | 必填 |
| `base_url` | API 地址（以 `/v1` 结尾） | 必填 |
| `model` | 模型名称 | `qwen3.5-plus` |
| `temperature` | 创造性（0-1） | `0.7` |
| `max_tokens` | 最大输出长度 | `8192` |
| `stream` | 是否启用流式输出 | `true` |
| `disable_thinking` | 是否关闭推理思考（加快首字） | `true` |

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 前端页面 |
| `/api/chat` | POST | 对话接口（支持流式） |
| `/api/upload` | POST | 文件上传接口 |
| `/api/suggestions` | POST | 追问建议生成接口 |

### POST /api/chat

```json
{
  "role": "xiaoying",
  "messages": [{"role": "user", "content": "你好"}],
  "enable_search": false
}
```

### POST /api/upload

Multipart 表单上传，字段名 `file`。支持：
- 图片（jpg/png/gif/webp）→ 返回 base64 data URL
- 文本文件（txt/md/csv/json 等）→ 返回文件内容

### POST /api/suggestions

```json
{
  "answer": "AI 回答的内容...",
  "role": "aiwus"
}
```

返回 3 个追问建议。

## 添加新角色

### 1. 在 `server.py` 中添加 System Prompt

```python
SYSTEM_PROMPTS = {
    "newrole": """角色描述...
    - 性格特点
    - 说话风格
    """
}
```

### 2. 在 `index.html` 中添加角色数据

```javascript
const roleData = {
  newrole: {
    name: '角色名称',
    handle: '@wupen.org',
    avatar: '/pic/avatar.jpg',
    video: '/pic/avatar.mp4',
    welcome: '欢迎语...',
    suggestions: ['建议1', '建议2']
  }
};
```

### 3. 在 HTML 中添加角色卡片

```html
<div class="role-card" onclick="enterChat('newrole')">
  <div class="role-card-avatar">
    <img src="/pic/avatar.jpg" alt="角色名称">
  </div>
  <div class="role-card-content">
    <div class="role-card-name">角色名称</div>
    <div class="role-card-desc">角色描述</div>
  </div>
</div>
```

## 技术栈

- **前端**: HTML5 + CSS3 + Vanilla JavaScript + marked.js
- **后端**: Python Flask + Flask-CORS + OpenAI SDK
- **部署**: Docker (Alpine) / Gunicorn + Nginx / 直接运行
- **镜像体积**: ~136MB（python:3.12-alpine + 多阶段构建）

## 部署体积对比

| 方案 | 磁盘占用 |
|------|---------|
| 直接运行 | ~12 MB（项目 + pip 依赖） |
| systemd + gunicorn | ~12 MB |
| Docker (alpine, 多阶段) | ~136 MB |
| Docker (slim) | ~170 MB |
