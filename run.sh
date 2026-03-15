#!/usr/bin/env bash
# 启动教师助手服务（LangGraph + FastAPI）
cd "$(dirname "$0")"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
exec uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
