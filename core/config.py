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
    # Query Rewrite：是否在 schema linking 前对用户问题做一次轻量级改写（仅优化表述，不改语义）
    query_rewrite_enabled: bool = Field(default=False, alias="QUERY_REWRITE_ENABLED")
    # 轮式对话防偏航：保留开头 N 轮（锚定主题）+ 最近 M 轮（近期上下文），中间截断（对齐 DB-GPT BufferedConversationMapperOperator）
    chat_keep_start_rounds: int = Field(default=1, alias="CHAT_KEEP_START_ROUNDS")
    chat_keep_end_rounds: int = Field(default=10, alias="CHAT_KEEP_END_ROUNDS")
    embedding_model: str = Field(default="text-embedding-v3", alias="EMBEDDING_MODEL")
    chroma_persist_dir: str = Field(default=str(BASE_DIR / "data" / "chroma"), alias="CHROMA_PERSIST_DIR")
    # Schema linking 可调参数（对齐 DB-GPT 的 KNOWLEDGE_SEARCH_TOP_SIZE）
    schema_retrieve_top_k: int = Field(default=12, alias="SCHEMA_RETRIEVE_TOP_K")
    schema_max_blocks: int = Field(default=20, alias="SCHEMA_MAX_BLOCKS")
    schema_max_chars: int = Field(default=12000, alias="SCHEMA_MAX_CHARS")
    schema_fallback_min_blocks: int = Field(default=6, alias="SCHEMA_FALLBACK_MIN_BLOCKS")

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
