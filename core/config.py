"""
应用配置：dotenv 加载 config/*.env，pydantic-settings 解析。
"""
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

# 加载环境变量，配置大模型相关参数
load_dotenv(BASE_DIR / "config" / "llm.env")
# 加载数据库相关环境变量
load_dotenv(BASE_DIR / "config" / "database.env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    dashscope_api_key: str = ""
    llm_model: str = "qwen-plus"
    enable_thinking_default: bool = False


settings = Settings()
