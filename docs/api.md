# Kamiu Agent API 说明

服务默认地址：`http://127.0.0.1:8002`（以 `run.sh` 或 uvicorn 启动为准）。

**多轮对话测试前端**：浏览器访问 `http://127.0.0.1:8002/` 即可使用简单聊天界面，自动带历史进行多轮对话。

---

## 健康检查

### GET /health

检查服务是否存活。

**响应示例**

```json
{
  "status": "ok"
}
```

---

## 助手对话

### GET /api/models

获取当前可选的模型 ID 列表（千问/DashScope），供前端下拉选择。

**响应示例**

```json
{
  "models": ["qwen-turbo", "qwen-plus", "qwen-max", "deepseek-v3", ...]
}
```

模型列表由 `core/dashscope_models.py` 维护，可按需增删。

---

### GET /api/chat

获取对话接口使用说明，不发起请求。

**响应示例**

```json
{
  "usage": "POST /api/chat 或 POST /api/chat/stream",
  "body": {
    "message": "必填",
    "history": "[]",
    "teacher_id": "",
    "enable_thinking": "false",
    "model": "可选"
  }
}
```

---

### POST /api/chat

非流式：走 Agent 图（含工具如 get_current_time），一次请求返回完整回复。

**请求体（JSON）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message | string | 是 | 用户输入 |
| history | array | 否 | 历史消息，每项为 `{ "content": "..." }`，默认 `[]` |
| teacher_id | string | 否 | 教师 ID，预留，默认 `""` |
| enable_thinking | boolean | 否 | 是否开启思考模式（部分模型支持），不传则用配置默认值 |
| enable_web_search | boolean | 否 | 是否开启联网搜索；开启后优先用非联网工具，解决不了再联网，默认 `false` |
| model | string | 否 | 模型名（如 qwen-plus），不传则用配置默认 |

**响应体（JSON）**

| 字段 | 类型 | 说明 |
|------|------|------|
| reply | string | 助手回复正文 |
| reasoning | string \| null | 思考过程，仅当 `enable_thinking=true` 且模型支持时可能有值 |

**示例**

```bash
curl -X POST http://127.0.0.1:8002/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好", "history": []}'
```

---

### POST /api/chat/stream

流式：走**同一 Agent 图**（含工具），仅以 **Server-Sent Events (SSE)** 按块返回内容。

**请求体**  
与 `POST /api/chat` 相同（见上表）。

**响应**  
- `Content-Type: text/event-stream`
- 每行格式：`data: <JSON>`

**事件类型（`data` 解析后的 `type`）**

| type | 说明 |
|------|------|
| reasoning | 思考过程片段（仅当 `enable_thinking=true` 时可能出现），`content` 为当前片段 |
| content | 回复正文片段，`content` 为当前片段 |
| usage | 本次调用的 token 使用情况，`usage` 为对象（如 `prompt_tokens`, `completion_tokens`） |
| done | 流式结束，无附加字段 |

**示例（解析 SSE）**

```bash
curl -N -X POST http://127.0.0.1:8002/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "1+1等于几？", "history": []}'
```

客户端按行读取 `data:` 后的 JSON，根据 `type` 拼接 `content`、展示 reasoning 或 usage，收到 `done` 后结束。
