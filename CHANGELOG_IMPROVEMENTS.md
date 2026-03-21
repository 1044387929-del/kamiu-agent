# Kamiu Agent 改进日志

本文档记录对照 DB-GPT 设计对 kamiu_agent 所做的功能与稳定性改进。

---

## 轮式对话防偏航（对齐 DB-GPT 历史截断）

**问题**：多轮对话时若把全部历史都塞进上下文，容易导致聊着聊着偏航、模型被早期或无关轮次干扰。

**DB-GPT 做法**：

- 使用 `BufferedConversationMapperOperator`，配置 `keep_start_rounds` 与 `keep_end_rounds`：只保留**开头 N 轮**（锚定主题）+ **最近 M 轮**（近期上下文），中间轮次截断。
- 配置项：`MESSAGES_KEEP_START_ROUNDS`（默认 0）、`MESSAGES_KEEP_END_ROUNDS`（默认 2）；ConversationComposer 中默认 `keep_end_rounds=10`。

**本次改动**：

- **配置**（`core/config.py`）：新增 `chat_keep_start_rounds`（默认 1）、`chat_keep_end_rounds`（默认 10），环境变量 `CHAT_KEEP_START_ROUNDS` / `CHAT_KEEP_END_ROUNDS`。
- **历史截断**（`core/agent.py`）：在 `chat_request_to_messages` 前对 `req.history` 做 `_trim_history_by_rounds`：按轮次分组后只保留前 `keep_start_rounds` 轮 + 后 `keep_end_rounds` 轮，逻辑与 DB-GPT 的 `_filter_round_messages` 一致（避免首尾重叠时保留全部）。
- **提示**（`prompts/assistant.py`）：在系统提示中增加一句「多轮对话时请紧扣用户当前问题与最近上下文作答，勿偏离主题。」

**涉及文件**：`core/config.py`、`core/agent.py`、`prompts/assistant.py`

---

## 禁止未查库就编造具体数据（防“瞎编”列表/主题）

**问题**：用户问「某老师最近十次讨论都是什么主题」时，模型有时不调用 `execute_readonly_sql`，而是根据 schema 或常识直接编造一列“主题”，与事实不符。

**思路（对齐 DB-GPT）**：凡需平台内数据验证的问题，必须基于工具返回结果作答，不得根据表名/字段名或常识编造任何具体数据。

**本次改动**：

1. **路由**（`graph/nodes.py`）：新增 `content_list_question` 判断——问题中出现「主题、都是什么、什么内容、列出、有哪些、标题、名称、具体」等时，与 `existence_question` 一样视为**必须查库**（`force_db_query=True`），走最严格的 DB 指令。
2. **DB 指令加强**（`graph/nodes.py`）：
   - 明确：禁止在未调用 `execute_readonly_sql` 或未收到工具返回前，编造任何具体数据（讨论主题、标题、人名、数量、列表项等）。
   - 若尚未执行 SQL 或工具返回为空，只能回答「需要先查库才能回答」或「未查到相关记录」，不得编造、推测或列举示例数据。
   - `force_db_query` 时追加：本问题必须通过 `execute_readonly_sql` 获取真实数据后再回答，禁止直接给出任何具体列表、主题、数量或统计结果。
3. **意图路由**（`graph/intent_router.py`）：LLM 路由说明中补充——询问「具体列表/主题/标题/都是什么/列出/有哪些」等需从库中取出的内容时，`force_db_query=true`。

**涉及文件**：`graph/nodes.py`、`graph/intent_router.py`

---

## 多步查库与图递归上限（对齐 DB-GPT ReAct 分步执行）

**问题**：用户问「我高姝睿参加过这些讨论中的任何一场吗」（前文刚聊过王明远老师最近十场讨论）时，模型只执行了一次 SQL（仅按姓名查参与表），未限定「那几场」讨论，就给出结论，导致结论与 SQL 不一致。

**DB-GPT 启发**：ReAct / 数据分析 Agent 通过提示约束「每步一个 Action、根据上一步结果再执行下一步、max_steps 内完成」，图本身支持 agent⇄tools 多轮循环。

**本次改动**：

1. **提示**（`graph/nodes.py`）：在 DB 指令中增加「多步查库」说明——若问题依赖前文或需多步验证（例如先查某老师/某主题的 discussion_id 列表，再查某人是否参与其中），必须分步执行多次 `execute_readonly_sql`，根据上一步结果决定下一步 SQL，直到有足够依据再给结论；不要在一次查询未覆盖全部条件时就下结论；并举例「是否参加过前面提到的那几场讨论」须先查出那几场的 discussion_id 再查参与表。
2. **图**（`graph/graph.py`）：`compile(recursion_limit=25)`，显式保证 agent⇄tools 可多轮执行，避免过早截断。

**涉及文件**：`graph/nodes.py`、`graph/graph.py`

---

## 轮式对话：当前目标与对话开场锚定（对齐 DB-GPT user_goal / historical_dialogues）

**DB-GPT 理念**：

- 每条会话记录有 **user_goal**（本轮用户输入），用于标识“当前对话在解决什么”。
- 新会话可携带 **historical_dialogues**：从历史会话中按 `keep_start_rounds` / `keep_end_rounds` 取若干条会话，每条会话只取首尾两条消息（首条≈开场问题、尾条≈该话题收尾），作为“过往话题摘要”注入首轮 agent 的上下文，便于多会话场景下不跑题。

**在 kamiu（单会话、LangGraph）内的复现**：

- 不落库、不跨会话，仅在**当前会话状态与提示**上做锚定：
  1. **current_goal**：路由节点从最后一条用户消息取出并写入 state，等价于 DB-GPT 的 user_goal / current_goal。
  2. **系统提示内显式写出“当前用户问题”**：在 agent 节点拼接系统提示时，若 state 中有 `current_goal`，则追加一行「当前用户问题：{current_goal}」，使模型每轮都看到本轮目标，减少偏航。
  3. **对话开场（供参考）**：当多轮（messages 超过 2 条）且首条用户消息与当前用户消息不同时，再追加一行「对话开场（供参考）：{首条用户消息前 300 字}」，相当于在单会话内用“开场一句”做主题锚定，与 DB-GPT 的 historical_dialogues 里保留“每条会话首条”的思路一致。

**本次改动**：

- **状态**（`graph/state.py`）：新增可选字段 `current_goal: str | None`。
- **路由**（`graph/nodes.py`）：`route_node` 将最后一条用户消息（截断至 500 字）写入 `current_goal`。
- **Agent 节点**（`graph/nodes.py`）：构建系统提示时，若存在 `current_goal` 则追加「当前用户问题：…」；若多轮且首条用户消息存在且与当前不同，则追加「对话开场（供参考）：…」（首条截断至 300 字）。

**涉及文件**：`graph/state.py`、`graph/nodes.py`

---

## 2025-03-18 17:33（本次改进）

### 概述

围绕 **Schema Linking / Text2SQL** 与 **提示与配置** 做三方面增强，与 DB-GPT 的 datasource/schema_link 行为对齐，减少“检索不到表”或“只查一张表就下结论”的问题。

---

### 1. Schema 检索失败时全量回退（对齐 DB-GPT）

**问题**：向量/词法检索若未命中（如 Chroma 未建索引、query 与表名无重叠），候选表为空，模型看不到任何表结构，易乱答或只查单表就断言“不存在”。

**DB-GPT 行为**：`get_schema_link` 在 `get_db_summary` 异常或返回空时，会执行 `conn.table_simple_info()`，即**回退为全表简单信息**。

**本次改动**：

- 在 `graph/schema_link.py` 的 `schema_link_node` 中，当合并后的 `candidates` 数量 **小于配置的 `schema_fallback_min_blocks`（默认 6）** 且存在 `blocks` 时，**不再使用空/过少候选**，改为使用**全量 schema 的前 `schema_max_blocks` 块**作为候选。
- 效果：检索失败或命中极少时，模型仍能拿到全库表结构，避免“看不到表”导致的错误结论。

**涉及文件**：`graph/schema_link.py`

---

### 2. 提示中显式写入数据库类型

**问题**：生成 SQL 时未告知模型当前数据库类型（如 MySQL），不利于按方言生成更准确的 SQL（如 `LIMIT`、函数名等）。

**DB-GPT 行为**：prompt 模板中包含 `db_type`，例如“数据库类型：{db_type}，相关表结构定义：{schemas}”。

**本次改动**：

- 在 `graph/nodes.py` 中构造 `schema_hint` 时，在【相关表结构】前增加 **“数据库类型：MySQL。”（或从 `settings.db_engine` 推导）**。
- 若未配置 `DB_ENGINE`，默认显示为 MySQL。

**涉及文件**：`graph/nodes.py`

---

### 3. Schema Linking 参数可配置

**问题**：top_k、最大候选块数、最大字符数等此前为写死常量，无法按库规模或 prompt 长度调优。

**DB-GPT 行为**：使用全局配置 `CFG.KNOWLEDGE_SEARCH_TOP_SIZE` 等控制检索与展示规模。

**本次改动**：

- 在 `core/config.py` 的 `Settings` 中新增（均可通过环境变量覆盖）：
  - `**SCHEMA_RETRIEVE_TOP_K`**（默认 12）：向量/词法检索的 top-k。
  - `**SCHEMA_MAX_BLOCKS**`（默认 20）：合并与业务扩展后最多保留的表块数。
  - `**SCHEMA_MAX_CHARS**`（默认 12000）：注入到提示中的 schema 文本最大字符数，超出则截断。
  - `**SCHEMA_FALLBACK_MIN_BLOCKS**`（默认 6）：候选数低于此值时触发全量回退。
- 在 `graph/schema_link.py` 中改为从 `settings` 读取上述四项，替代原硬编码。

**涉及文件**：`core/config.py`、`graph/schema_link.py`

---

### 变更文件一览


| 文件                     | 变更说明                                                                                                    |
| ---------------------- | ------------------------------------------------------------------------------------------------------- |
| `core/config.py`       | 新增 `schema_retrieve_top_k`、`schema_max_blocks`、`schema_max_chars`、`schema_fallback_min_blocks` 配置项及默认值。 |
| `graph/schema_link.py` | 使用上述配置；在候选数 < `schema_fallback_min_blocks` 时用全量 blocks 回退；去掉相关魔法数字。                                     |
| `graph/nodes.py`       | 在 DB 查询的 schema_hint 前增加“数据库类型：{db_type}。”。                                                             |


---

### 配置示例（可选）

在 `config/llm.env` 或 `config/database.env` 中可按需增加（均为可选）：

```env
# Schema linking 检索与回退（不配则用默认值）
SCHEMA_RETRIEVE_TOP_K=12
SCHEMA_MAX_BLOCKS=20
SCHEMA_MAX_CHARS=12000
SCHEMA_FALLBACK_MIN_BLOCKS=6
```

---

## 2025-03（老师/教师与“数据库全景”漏表修复）

### 问题

用户问“先看看王明远老师的 id 是多少，再去查有几个相关讨论”时，模型只看到了 `school_class_teacher` 等少量表，未看到 `school_teacher`（教师档案表，含 teacher_id、teacher_name），因而误判“无法获取 teacher_id”，与事实不符，属于未读取到数据库全景（漏表）。

### 改动

1. **老师/教师业务扩展（schema_link.py）**  
   当问题中包含“老师”“教师”“的id”“teacher”等时，强制将**所有**在内容中出现“老师/教师/teacher/teacher_id/teacher_name/school_teacher”的 schema 块加入候选，确保 `school_teacher` 与 `school_class_teacher`、讨论相关表等一起被注入，避免只看到班级-教师关联表而漏掉教师档案表。

2. **提高全量回退阈值（config.py）**  
   将 `SCHEMA_FALLBACK_MIN_BLOCKS` 默认值从 **2 改为 6**：当合并+业务扩展后候选块数仍 **&lt; 6** 时，直接使用**全量 schema**（前 `schema_max_blocks` 块）。这样在检索只返回 2～3 张表时，也会回退到全量，模型能看到更多表（如 school_teacher、讨论表等），减少“只根据部分表就下结论”的情况。

3. **提示词补充（nodes.py）**  
   在 DB 查询的系统提示中明确：若涉及“老师”“教师”“某老师的 id”或“相关讨论”，须同时考虑 **school_teacher**（教师档案 teacher_id、teacher_name）、**school_class_teacher** 及讨论相关表，不可只根据部分表就断言查不到。

### 涉及文件

- `graph/schema_link.py`：老师/教师关键词与 block 关键词扩展；使用新的 fallback 默认值。
- `core/config.py`：`schema_fallback_min_blocks` 默认值 2 → 6。
- `graph/nodes.py`：DB 指令中增加老师/教师与讨论相关表的说明。

---

### 验证建议

1. **全量回退**：清空 Chroma 索引（如删除 `data/chroma` 下对应库的 collection 或 `_schema_meta.json`），问一条需查库的问题，确认仍能拿到表结构并生成 SQL。
2. **数据库类型**：在提示或日志中确认出现“数据库类型：MySQL。”等字样，且生成 SQL 符合 MySQL 语法。
3. **可配置项**：修改 `SCHEMA_MAX_BLOCKS` 等后重启服务，观察 schema 注入长度与检索条数是否符合预期。

---

*本文档随项目迭代更新，若有新改进会追加到本文件。*