"""
教师助手相关提示词：用 LangChain 模板管理，便于后续加变量（如 teacher_id）。
"""
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate, SystemMessagePromptTemplate

# 基础角色与风格（无变量时可直接 .format() 得到字符串）
ASSISTANT_SYSTEM_TEMPLATE = PromptTemplate.from_template(
    "你是教师智能助手，回答简洁、专业、友好。"
)


# Agent 图用：基础 + 工具使用说明；{web_search_instruction}、{db_query_instruction} 按开关填入
ASSISTANT_SYSTEM_WITH_TOOLS_TEMPLATE = PromptTemplate.from_template(
    "你是教师智能助手，回答简洁、专业、友好。 "
    "多轮对话时请紧扣用户当前问题与最近上下文作答，勿偏离主题。"
    "若用户问当前时间、日期、今天几号、昨天或上周等与时间闻讯相关的，请先使用 get_current_time 工具获取后再推算回答。"
    "{web_search_instruction}"
    "{db_query_instruction}"
)

# ChatPromptTemplate（多轮 / 与 pyannote 一致，.invoke({}) 得 messages）：
ASSISTANT_CHAT_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(ASSISTANT_SYSTEM_TEMPLATE.template),
])
ASSISTANT_CHAT_PROMPT_WITH_TOOLS = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(ASSISTANT_SYSTEM_WITH_TOOLS_TEMPLATE.template),
])
