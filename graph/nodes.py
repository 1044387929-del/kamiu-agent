"""
LangGraph 节点：每个节点接收 state，返回 state 的增量更新。
"""
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage

from core.llm import get_llm, get_openai_client
from core.config import settings
from graph.state import AgentState
from prompts import ASSISTANT_SYSTEM_WITH_TOOLS_TEMPLATE
from tools import get_tools_list
from graph.intent_router import llm_route

def _messages_to_openai(messages: list[BaseMessage]) -> list[dict]:
    """LangChain messages 转 OpenAI API 格式。"""
    out = []
    for m in messages:
        if isinstance(m, SystemMessage):
            out.append({"role": "system", "content": (m.content or "")})
        elif isinstance(m, HumanMessage):
            out.append({"role": "user", "content": (m.content or "")})
        elif isinstance(m, AIMessage):
            out.append({"role": "assistant", "content": (m.content or "")})
    return out


def route_node(state: AgentState) -> AgentState:
    """
    路由节点：根据最后一条用户消息决定下一步（可扩展为调用 LLM 做意图识别）。
    当前实现：根据 query 自动判断是否需要数据库只读查询工具（ORM/SQL）。
    """
    messages = state.get("messages") or []
    last_user = ""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            last_user = (m.content or "").strip()
            break
    if not last_user:
        return {"enable_db_query": False, "force_db_query": False}

    text = last_user.lower()

    # 强信号：出现 SQL 关键字/表字段/数据库指令
    strong_sql = bool(
        re.search(r"\b(select|from|where|join|group by|order by|having|limit|explain|desc|describe|show)\b", text)
    )
    strong_db_words = any(
        k in text
        for k in (
            "mysql",
            "数据库",
            "数据表",
            "表结构",
            "字段",
            "列名",
            "主键",
            "外键",
            "orm",
            "django",
            "models",
            "model",
            "queryset",
        )
    )

    # 业务“查数/统计”信号（中等强度）：如“统计/查询/报表/订单数/uv/pv/去重”等
    biz_query_words = any(
        k in last_user
        for k in (
            "查询",
            "统计",
            "报表",
            "汇总",
            "排名",
            "Top",
            "top",
            "明细",
            "订单",
            "用户数",
            "活跃",
            "uv",
            "pv",
            "去重",
            "分组",
            "聚合",
        )
    )

    # 平台核心业务实体信号（讨论/评论/发帖等）+ 时间/存在性问句：常见“昨天有新讨论吗”
    entity_words = any(
        k in last_user
        for k in (
            "讨论",
            "帖子",
            "贴子",
            "话题",
            "发言",
            "评论",
            "回复",
            "发布",
            "新增",
            "新",
            "创建",
        )
    )
    time_words = any(k in last_user for k in ("昨天", "今天", "近", "最近", "本周", "上周", "本月", "上月"))
    existence_question = any(k in last_user for k in ("有没有", "是否有", "有吗", "多少", "几条", "新增了", "出现吗"))

    enable_db_query_rule = bool(
        strong_sql
        or strong_db_words
        or biz_query_words
        or (entity_words and (time_words or existence_question))
    )
    force_db_query_rule = bool(entity_words and (time_words or existence_question) and not strong_db_words)

    # LLM 路由：当规则不够确定时，用结构化 JSON 做补充判定（模仿 DB-GPT IntentRecognition）
    llm_decision = llm_route(state)
    enable_db_query = bool(enable_db_query_rule or llm_decision.get("enable_db_query", False))
    force_db_query = bool(force_db_query_rule or llm_decision.get("force_db_query", False))
    return {"enable_db_query": enable_db_query, "force_db_query": force_db_query}


def _agent_node_impl():
    """返回带工具调用的 agent 节点（LLM 可返回 tool_calls）；支持思考模式时补采 reasoning；支持 stream_queue 时边生成边推送。

    重要：工具绑定根据 state 动态决定（路由结果 + 用户开关），实现“按 query 选择外挂工具”。
    """

    def agent_node(state: AgentState) -> dict:
        """
        回复节点：调用 LLM 根据当前 messages 生成助手回复。
        """
        messages = state.get("messages") or []
        if not messages:
            return {"messages": [AIMessage(content="你好，我是教师助手。有什么可以帮你的？")]}
        enable_thinking = state.get("enable_thinking", False)
        enable_web_search = state.get("enable_web_search", False)
        enable_db_query = state.get("enable_db_query", False)
        force_db_query = state.get("force_db_query", False)
        schema_link = (state.get("schema_link") or "").strip()
        model_override = (state.get("model") or "").strip() or None
        stream_queue = state.get("stream_queue")
        llm = get_llm(model=model_override)
        # 动态绑定工具：仅暴露当前需要的工具给 LLM
        dynamic_tools = get_tools_list(
            enable_web_search=enable_web_search,
            enable_db_query=enable_db_query,
        )
        if dynamic_tools:
            llm = llm.bind_tools(dynamic_tools)
        web_search_instruction = (
            "优先使用除 web_search 以外的工具（如 get_current_time）解决问题；"
            "仅当这些工具无法回答时再使用 web_search 进行联网搜索。"
            if enable_web_search
            else ""
        )
        db_query_instruction = (
            (
                "当用户提出与业务数据、统计、查询相关时，使用数据库只读工具：先调用 get_db_schema 了解表结构，再生成只读 SQL 并用 execute_readonly_sql 执行。禁止任何写操作。"
                if not force_db_query
                else
                "当问题属于平台内部可验证的数据（如讨论/帖子/评论在某天是否新增、数量是多少）时，你必须使用数据库只读工具来验证，禁止仅凭推断回答。流程：先调用 get_db_schema → 生成并展示只读 SQL（execute_readonly_sql）→ 执行并根据结果作答。若工具不可用或执行失败，说明原因并给出下一步排查信息。禁止任何写操作。"
            )
            if enable_db_query
            else ""
        )
        schema_hint = f"\n\n【相关表结构（已自动筛选）】\n{schema_link}\n" if (enable_db_query and schema_link) else ""
        system_text = ASSISTANT_SYSTEM_WITH_TOOLS_TEMPLATE.format(
            web_search_instruction=web_search_instruction,
            db_query_instruction=db_query_instruction + schema_hint,
        )
        full = [SystemMessage(content=system_text)] + list(messages)

        if stream_queue is not None:
            # 边生成边推送到 queue；若开启思考则用 raw 流式接口，先推 reasoning 再推 content
            if enable_thinking:
                client = get_openai_client()
                openai_messages = _messages_to_openai(full)
                content_parts = []
                reasoning_parts = []
                try:
                    completion = client.chat.completions.create(
                        model=model_override or settings.llm_model,
                        messages=openai_messages,
                        stream=True,
                        extra_body={"enable_thinking": True},
                        stream_options={"include_usage": True},
                    )
                    for chunk in completion:
                        if not chunk.choices:
                            continue
                        delta = chunk.choices[0].delta
                        if getattr(delta, "reasoning_content", None):
                            reasoning_parts.append(delta.reasoning_content)
                            stream_queue.put(("reasoning", delta.reasoning_content))
                        if getattr(delta, "content", None):
                            content_parts.append(delta.content)
                            stream_queue.put(("content", delta.content))
                    content = "".join(content_parts).strip()
                    reasoning = "".join(reasoning_parts).strip() or None
                    out = {"messages": [AIMessage(content=content)]}
                    if reasoning:
                        out["last_reasoning"] = reasoning
                except Exception:
                    # 降级：不用思考流式，走下面非思考的 stream
                    full_response = None
                    for chunk in llm.stream(full):
                        if getattr(chunk, "content", None):
                            stream_queue.put(("content", chunk.content))
                        full_response = chunk if full_response is None else full_response + chunk
                    out = {"messages": [full_response]}
            else:
                full_response = None
                for chunk in llm.stream(full):
                    if getattr(chunk, "content", None):
                        stream_queue.put(("content", chunk.content))
                    full_response = chunk if full_response is None else full_response + chunk
                out = {"messages": [full_response]}
        else:
            response = llm.invoke(full)
            out = {"messages": [response]}

        # 当用户开启思考模式且本次为最终回复（无 tool_calls）时，用流式请求补采 reasoning
        if enable_thinking and not getattr(out["messages"][0], "tool_calls", None):
            client = get_openai_client()
            openai_messages = _messages_to_openai(full)
            model = model_override or settings.llm_model
            try:
                completion = client.chat.completions.create(
                    model=model,
                    messages=openai_messages,
                    stream=True,
                    extra_body={"enable_thinking": True},
                    stream_options={"include_usage": True},
                )
                reasoning_parts = []
                for chunk in completion:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if getattr(delta, "reasoning_content", None):
                        reasoning_parts.append(delta.reasoning_content)
                reasoning = "".join(reasoning_parts).strip() or None
                if reasoning:
                    out["last_reasoning"] = reasoning
            except Exception:
                pass
        return out

    return agent_node


def reply_node(state: AgentState) -> AgentState:
    """
    回复节点：调用 LLM 根据当前 messages 生成助手回复。
    """
    messages = state.get("messages") or []
    if not messages:
        return {"messages": [AIMessage(content="你好，我是教师助手。有什么可以帮你的？")]}
    llm = get_llm()
    # 首条为系统提示，便于模型保持角色
    system_text = ASSISTANT_SYSTEM_WITH_TOOLS_TEMPLATE.format()
    full_messages = [SystemMessage(content=system_text)] + list(messages)
    response = llm.invoke(full_messages)
    content = getattr(response, "content", "") or ""
    return {"messages": [AIMessage(content=content)]}


def inject_system_node(state: AgentState) -> AgentState:
    """
    注入系统提示：在对话前插入角色与权限说明（可选）。
    """
    teacher_id = state.get("teacher_id") or ""
    system = (
        "你是教师智能助手。当前教师 ID：{teacher_id}。"
        "回答要简洁、专业。".format(teacher_id=teacher_id)
    )
    return {"messages": [SystemMessage(content=system)]}
