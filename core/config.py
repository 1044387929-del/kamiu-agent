"""
应用配置：dotenv 加载 config/*.env，pydantic-settings 解析。
"""
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
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
        populate_by_name=True,
    )

    dashscope_api_key: str = ""
    llm_model: str = "qwen-plus"
    enable_thinking_default: bool = False
    embedding_model: str = Field(default="text-embedding-v3", alias="EMBEDDING_MODEL")
    chroma_persist_dir: str = Field(default=str(BASE_DIR / "data" / "chroma"), alias="CHROMA_PERSIST_DIR")

    # 数据库（database.env 中 DB_* 变量）
    db_engine: str = Field(default="", alias="DB_ENGINE")
    db_name: str = Field(default="", alias="DB_NAME")
    db_user: str = Field(default="", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")
    db_host: str = Field(default="127.0.0.1", alias="DB_HOST")
    db_port: str = Field(default="3306", alias="DB_PORT")

    # Django 项目（可选，用于 ORM 内省与执行）
    django_settings_module: str = Field(default="", alias="DJANGO_SETTINGS_MODULE")
    django_project_path: str = Field(default="", alias="DJANGO_PROJECT_PATH")


settings = Settings()
