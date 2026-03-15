"""
FastAPI 应用入口：教师智能助手服务。
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes

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

app.include_router(routes.router, prefix="/api", tags=["assistant"])


@app.get("/health")
def health():
    return {"status": "ok"}
