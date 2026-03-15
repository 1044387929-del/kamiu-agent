"""教师助手相关接口：对话"""
from fastapi import APIRouter

from . import chat

router = APIRouter(tags=["assistant"])
router.include_router(chat.router)
