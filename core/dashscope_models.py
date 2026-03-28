"""
DashScope/千问 API 可用模型名称列表。

百炼平台（DashScope）兼容 OpenAI 接口，可调用通义千问、DeepSeek 等模型。
此处集中维护模型 ID，供前端下拉选择与接口校验；按需增删。
参考：https://help.aliyun.com/zh/model-studio/getting-started/models
"""

# 通义千问系列
QWEN_MODELS = [
    "qwen-turbo",
    "qwen-plus",
    "qwen-max",
    "qwen-max-longcontext",
    "qwen-long",
]

# DeepSeek 等（百炼已接入）
OTHER_MODELS = [
    "deepseek-v2",
    "deepseek-v3",
    "deepseek-v3-0324",
    "deepseek-v3.2",
]

# 合并为前端与 API 使用的完整列表（顺序：千问优先，再其他）
DASHSCOPE_MODEL_IDS: list[str] = QWEN_MODELS + OTHER_MODELS

# 默认模型（与 config.llm_model 保持一致语义，此处仅作兜底）
DEFAULT_MODEL_ID = "qwen-plus"


def get_model_list() -> list[str]:
    """返回当前支持的模型 ID 列表，供 API 返回给前端。"""
    return list(DASHSCOPE_MODEL_IDS)


def is_valid_model(model_id: str | None) -> bool:
    """校验模型 ID 是否在允许列表中；None 或空视为未指定（合法）。"""
    if not (model_id or "").strip():
        return True
    return (model_id or "").strip() in DASHSCOPE_MODEL_IDS
