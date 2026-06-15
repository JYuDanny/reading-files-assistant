# 阅读助手 (Reading Assistant)

浏览器阅读辅助工具：通过 Chrome 扩展快捷键框选页面内容截图，发送给本地多模态大模型（LM Studio），在新标签页中进行多轮对话提问。

## 系统架构

```
┌─────────────────┐     HTTP      ┌──────────────────┐    OpenAI兼容    ┌──────────────┐
│  Chrome 扩展     │ ────────────> │  FastAPI 后端     │ ──────────────> │  LM Studio   │
│  (截图工具)      │ <─ SSE 推送 ─ │  (localhost:8420) │ <────────────── │ :1234        │
└─────────────────┘               └──────────────────┘                 └──────────────┘
```

## 环境要求

- **Python** 3.9+
- **LM Studio** (最新版, 用于本地运行多模态模型)
- **Chrome 浏览器** (用于加载扩展)
- **Git** (用于版本管理)
- 支持 **Windows** / **macOS** / **Linux**

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/JYuDanny/reading-files-assistant.git
cd reading-files-assistant
```

### 2. 创建虚拟环境并安装依赖

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 启动 LM Studio

1. 打开 LM Studio
2. 搜索并下载模型：`qwen/qwen3-vl-4b`（或其他兼容的多模态模型）
3. 加载模型后，进入 **Developer** → **Start Server**
4. 确认端口为 `1234`

> 后端会**自动检测** LM Studio 中已加载的模型，无需手动配置。如有多个模型，可通过环境变量 `LM_STUDIO_MODEL` 指定。

验证 LM Studio 服务：

**Windows:**
```powershell
Invoke-RestMethod -Uri "http://localhost:1234/v1/models" -Method Get
```

**macOS / Linux:**
```bash
curl http://localhost:1234/v1/models
```

### 4. 启动后端

```bash
python run.py
```

服务默认运行在 `http://localhost:8420`。

验证后端：

```bash
curl http://localhost:8420/api/health
```

### 5. 加载 Chrome 扩展

1. 打开 Chrome，地址栏输入 `chrome://extensions/`
2. 开启右上角 **开发者模式**
3. 点击 **加载已解压的扩展程序**
4. 选择项目中的 `extension/` 目录
5. 确认扩展出现在列表中

快捷键：
- **Windows**: `Ctrl+Shift+X`
- **macOS**: `Command+Shift+X`

### 6. 开始使用

1. 打开任意网页（如技术文档、论文等）
2. 按快捷键，鼠标框选感兴趣的内容区域
3. 点击 **确认截图**
4. 自动打开新标签页聊天面板，在输入框发送你的问题
5. 支持多轮追问

## 迁移到其他机器

项目已发布在 GitHub，在任何新机器上使用只需三步：

```bash
# 1. 克隆代码
git clone https://github.com/JYuDanny/reading-files-assistant.git
cd reading-files-assistant

# 2. 创建虚拟环境并安装依赖（参考上方对应系统的命令）

# 3. 在 LM Studio 中加载模型并启动 Server，然后启动后端
python run.py
```

代码完全跨平台——所有路径使用 `pathlib`，无硬编码的 Windows 路径，无系统特定依赖。Chrome 扩展的 manifest 已同时配置 Windows 和 macOS 快捷键。

## 项目结构

```
reading-files-assistant/
├── backend/
│   ├── config.py              # 配置管理（支持环境变量覆盖）
│   ├── llm_client.py          # LM Studio 异步客户端
│   ├── session_manager.py     # 内存会话管理
│   ├── main.py                # FastAPI 应用入口
│   ├── routes/
│   │   ├── sessions.py        # API 端点 + SSE 流式推送
│   │   └── pages.py           # 聊天页面路由
│   └── static/
│       └── chat.html          # 聊天面板 UI（Catppuccin 主题）
├── extension/
│   ├── manifest.json          # Chrome Manifest V3
│   ├── background.js          # Service Worker（快捷键/API通信）
│   ├── content.js             # 页面注入脚本（框选交互）
│   ├── content.css            # 框选样式
│   └── icon.png               # 扩展图标
├── run.py                     # 启动入口
├── tests/                     # 25 个单元测试
├── docs/                      # 设计文档和实现计划
├── requirements.txt           # Python 依赖
└── README.md
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/health` | 健康检查 |
| `POST` | `/api/sessions` | 创建会话，上传截图 |
| `POST` | `/api/sessions/{id}/messages` | 发送追问消息 |
| `GET` | `/api/sessions/{id}/stream` | SSE 流式接收回复 |
| `GET` | `/api/sessions/{id}` | 查询会话信息 |
| `GET` | `/chat/{session_id}` | 聊天面板页面 |

## 环境变量

可通过环境变量覆盖默认配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | `127.0.0.1` | 后端监听地址 |
| `PORT` | `8420` | 后端端口 |
| `LM_STUDIO_BASE_URL` | `http://localhost:1234/v1` | LM Studio 地址 |
| `LM_STUDIO_MODEL` | (自动检测) | 模型 ID，留空则自动从 LM Studio 获取 |
| `MAX_REQUEST_SIZE_MB` | `10` | 截图大小上限 |
| `SESSION_TIMEOUT_MINUTES` | `30` | 会话超时时间 |
| `LLM_TIMEOUT_SECONDS` | `120` | LLM 请求超时 |
| `LLM_MAX_TOKENS` | `-1` | 最大输出 token（-1 不限） |

## 运行测试

```bash
# 确保 LM Studio 正在运行
pytest tests/ -v
```

## 常见问题

### 自定义端口

如需更改后端端口，需同步修改三处：

1. 设置环境变量 `PORT`（如 `$env:PORT="9000"`）
2. `extension/background.js` 第 1 行的 `BACKEND_URL`
3. `extension/manifest.json` 中的 `host_permissions`

然后重新加载 Chrome 扩展，重启后端。

### HTTP 503 (VPN/代理拦截)

部分 VPN 软件会劫持本地 HTTP 流量。后端已内置处理：设置 `NO_PROXY` 环境变量并使用 `proxy=None` 创建 httpx 客户端。如果仍有问题，请关闭 VPN 或在其设置中排除 `localhost`。

### 图片上传返回 400

LM Studio 只接受 base64 编码的图片，不接受 URL。后端已自动处理转换。

### 首次请求较慢

多模态模型首次推理需要加载视觉编码器（约几十秒）。后端启动时会自动预热。

## 技术栈

- **后端**: FastAPI + httpx (async) + SSE (Server-Sent Events)
- **大模型**: LM Studio (OpenAI 兼容接口)
- **前端**: Chrome Extension Manifest V3 + 纯 HTML/CSS/JS
- **渲染**: marked.js (Markdown + 代码高亮) + KaTeX (LaTeX 数学公式)
