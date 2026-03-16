# 测试脚本

需先启动服务：在项目根目录执行 `./run.sh` 或 `uvicorn app:app --host 0.0.0.0 --port 8002`。

## api/ — 单接口测试

- **test_health.py** — GET /health 健康检查
- **test_chat_api.py** — GET /api/chat（说明）、POST /api/chat（非流式对话）
- **test_chat_stream.py** — POST /api/chat/stream（流式 SSE 对话）

## 运行方式（在项目根目录）

```bash
python scripts/test/api/test_health.py
python scripts/test/api/test_chat_api.py
python scripts/test/api/test_chat_stream.py
```
