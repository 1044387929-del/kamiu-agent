"""
FastAPI 应用入口：教师智能助手服务。

- 对话：/api/chat、/api/chat/stream（routers/assistant）
- 健康检查：/health（routers/health）
- 测试前端：/ 、/static/index.html

启动: uvicorn app:app --host 0.0.0.0 --port 8002 --reload
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

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

# 测试前端：多轮对话聊天页
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def _index():
        return RedirectResponse("/static/index.html")
