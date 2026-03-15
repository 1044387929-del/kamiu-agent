"""
FastAPI 应用入口：教师智能助手服务。

- 对话：/api/chat、/api/chat/stream（routers/assistant）
- 健康检查：/health（routers/health）

启动: uvicorn app:app --host 0.0.0.0 --port 8002 --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import assistant, health

app = FastAPI(
    title="Kamiu Agent",
    description="教师智能助手：对话、查数、学科知识",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(assistant.router, prefix="/api")
