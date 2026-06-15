# 阅读助手 - 设计文档

> **日期**: 2026-06-15
> **状态**: 已确认

## 目标

构建一个浏览器阅读辅助工具：在浏览器中阅读文档时，通过快捷键框选页面内容截图，自动发送给本地多模态大模型（LM Studio / qwen3-vl-4b），在侧边聊天面板中进行多轮对话提问。

---

## 整体架构

```
┌─────────────────────┐     HTTP      ┌───────────────────────┐    OpenAI兼容     ┌──────────────┐
│  Chrome 扩展 (截图)   │ ────────────> │  FastAPI 后端           │ ───────────────> │  LM Studio   │
│                     │ <─ SSE 推送 ── │  (localhost:8000)      │ <─────────────── │ :1234        │
└─────────────────────┘               └───────────────────────┘                  │ qwen3-vl-4b  │
         │                                      │                                └──────────────┘
         │ 打开新标签页                          │ 内存存储会话
         v                                      v
┌─────────────────────┐               ┌───────────────────────┐
│  浏览器标签页         │               │  dict[session_id]      │
│  /chat/<session_id>  │               │  → { image, messages }  │
└─────────────────────┘               └───────────────────────┘
```

---

## 组件职责

| 组件 | 职责 | 技术 |
|------|------|------|
| Chrome 扩展 | 快捷键(Ctrl+Shift+X) → 鼠标框选 → `captureVisibleTab` 截图 → POST 到后端 → 打开聊天页 | Manifest V3, JS |
| FastAPI 后端 | 接收截图、管理会话（内存）、调用 LM Studio LLM、SSE 流式推送 | FastAPI + httpx + SSE |
| 聊天面板 | 展示对话历史、发送追问、SSE 接收流式回复、Markdown 渲染 | 纯 HTML/CSS/JS, marked.js |
| LM Studio | 本地多模态推理 | qwen3-vl-4b, localhost:1234 |

---

## 对话模式

- **多轮对话**：围绕单张截图可连续追问
- **不保存历史**：会话仅存内存，页面关闭即销毁
- **首条消息自动触发**：打开聊天页时自动发送初始提问，无需用户先打字
- **图片不保存**：截图仅在该会话中使用，不落盘

---

## API 设计

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/health` | 健康检查（扩展启动时检测后端可用） |
| `POST` | `/api/sessions` | 创建会话，上传 base64 截图 |
| `POST` | `/api/sessions/{id}/messages` | 发送追问消息 |
| `GET` | `/api/sessions/{id}/stream` | SSE 流式接收 LLM 回复 |
| `GET` | `/chat/{session_id}` | 返回聊天面板 HTML 页面 |

### POST /api/sessions

```
请求:  { "image": "data:image/png;base64,..." }
响应:  { "session_id": "abc123", "chat_url": "http://localhost:8000/chat/abc123" }
```

### POST /api/sessions/{id}/messages

```
请求:  { "content": "这段代码是什么意思？" }
响应:  204 (触发 SSE 推送)
```

- 首条消息：构建 `[user: image + text]` 发送给 LLM
- 后续消息：追加到已有对话历史，不重复发送图片

### GET /api/sessions/{id}/stream

```
SSE 事件流:
  data: {"delta": "这是第一段..."}
  data: [DONE]
```

---

## Chrome 扩展设计

### 文件结构

```
extension/
├── manifest.json      # MV3 配置
├── background.js      # Service Worker (快捷键处理)
├── content.js         # 注入页面 (框选逻辑)
├── content.css        # 框选遮罩样式
└── icon.png           # 扩展图标
```

### 工作流程

1. 用户按 `Ctrl+Shift+X`
2. `background.js` 收到命令，通知当前标签页 `content.js`
3. `content.js` 注入框选遮罩层
4. 用户拖拽鼠标绘制选区矩形
5. 松开鼠标 → 右下角弹出确认/取消按钮
6. 确认 → `content.js` 通知 `background.js` 调用 `chrome.tabs.captureVisibleTab` 截图
7. `background.js` 按选区坐标裁剪图片 → 转 base64 → POST `/api/sessions`
8. 拿到 `chat_url` → 打开新标签页

### Manifest V3 关键配置

- `commands`: `Ctrl+Shift+X` / `Command+Shift+X` (macOS)
- `permissions`: `activeTab`, `scripting`
- `host_permissions`: `http://localhost:8000/*`
- 选区过小（<100px²）提示"选区太小"

---

## 聊天面板设计

### 页面布局

```
┌──────────────────────────────────┐
│  📄 阅读助手                [×] │  顶栏
├──────────────────────────────────┤
│  ┌─ 截图预览（可折叠） ────────┐ │
│  │  [缩略图]                   │ │
│  └─────────────────────────────┘ │
│  ┌── 对话区域 ─────────────────┐ │
│  │  🤖 初始问候                 │ │
│  │  👤 用户追问                 │ │
│  │  🤖 流式回复 (Markdown)      │ │
│  └─────────────────────────────┘ │
│  ┌── 输入区 ───────────────────┐ │
│  │  [输入框]              [发送] │ │
│  └─────────────────────────────┘ │
└──────────────────────────────────┘
```

### 技术细节

- 纯 HTML + CSS + JavaScript，无框架
- `marked.js` 渲染 Markdown（代码高亮）
- `EventSource` (SSE) 接收流式回复
- 截图预览区可折叠，默认展开
- 页面加载时自动发送初始提问（"请描述这张截图的内容"）

---

## 错误处理

### 后端

| 场景 | HTTP 状态码 | 响应 |
|------|------------|------|
| LM Studio 未启动 | 503 | `{"error": "LM Studio 服务未启动，请确认已加载 qwen3-vl-4b 模型"}` |
| 截图过大 (>10MB) | 413 | `{"error": "截图大小超过限制"}` |
| session 不存在 | 404 | `{"error": "会话不存在或已过期"}` |
| 并发消息（同一会话） | 429 | `{"error": "请等待当前回复完成"}` |
| LLM 超时 (120s) | 504 | `{"error": "回复超时，请重试"}` |
| 代理拦截 | - | 启动时设置 `NO_PROXY`，httpx 使用 `proxy=None` |

### 前端

| 场景 | 处理 |
|------|------|
| SSE 断连 | EventSource 自动重连 |
| 扩展检测不到后端 | 发截图前 GET `/api/health`，失败弹提示 |
| chrome:// 页面 | 检测后提示不可用 |

### 会话清理

- 后端每 5 分钟清理超过 30 分钟无 SSE 连接的会话

---

## LM Studio 调用要点

- 端点: `POST http://localhost:1234/v1/chat/completions`
- 模型: `qwen/qwen3-vl-4b`
- 图片格式: base64 data URI (`data:image/png;base64,...`)
- 必须设置: `os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"`
- 必须设置: `httpx.Client(proxy=None, timeout=120)`
- 支持 stream: `{"stream": true}`
- 启动时预热: 发一个简单文本请求

---

## 项目结构

```
reading-files-assistant/
├── backend/
│   ├── main.py              # FastAPI 入口，路由注册
│   ├── config.py             # 配置（LM Studio URL、端口等）
│   ├── llm_client.py         # LM Studio 调用封装
│   ├── session_manager.py    # 会话内存管理
│   ├── routes/
│   │   ├── sessions.py       # /api/sessions 端点 + SSE
│   │   └── pages.py          # /chat/{id} 静态页面
│   └── static/
│       └── chat.html         # 聊天面板
├── extension/
│   ├── manifest.json
│   ├── background.js
│   ├── content.js
│   ├── content.css
│   └── icon.png
├── docs/
│   └── LM_Studio_API_指南.txt
├── objectives.md
└── opencode.json
```

---

## 开发顺序

| 阶段 | 内容 |
|------|------|
| 1 | FastAPI 骨架 + LLM 客户端 |
| 2 | 会话管理 + API 端点 (`/api/sessions`, `/api/sessions/{id}/messages`) |
| 3 | SSE 流式回复 (`/api/sessions/{id}/stream`) |
| 4 | 聊天面板页面 (`/chat/{id}`) |
| 5 | Chrome 扩展 (`extension/*`) |
| 6 | 联调 + 边界处理完善 |
