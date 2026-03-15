"""
应用配置：dotenv 加载 config/*.env，pydantic-settings 解析为配置对象。
"""
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / "config" / "llm.env")
load_dotenv(BASE_DIR / "config" / "database.env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    dashscope_api_key: str = ""
    llm_model: str = "qwen-plus"


settings = Settings()
