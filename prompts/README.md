# 提示词模板（prompts）

与 `pyannote_diarization/prompts` 同风格，**用 LangChain 模板管理**，由各模块按需引用。

## 结构

- **assistant.py** — 教师助手对话
  - `PromptTemplate`：`ASSISTANT_SYSTEM_TEMPLATE`、`ASSISTANT_SYSTEM_WITH_TOOLS_TEMPLATE`，用 `.format()` 或 `.format(**kwargs)` 得到字符串。
  - `ChatPromptTemplate`：`ASSISTANT_CHAT_PROMPT`、`ASSISTANT_CHAT_PROMPT_WITH_TOOLS`，用 `.invoke({})` 得到 messages。

## 使用

```python
# 取系统提示字符串（无变量）
from prompts import ASSISTANT_SYSTEM_TEMPLATE, ASSISTANT_SYSTEM_WITH_TOOLS_TEMPLATE
system_text = ASSISTANT_SYSTEM_TEMPLATE.format()
system_with_tools = ASSISTANT_SYSTEM_WITH_TOOLS_TEMPLATE.format()

# 后续加变量时在模板中写 {teacher_id} 等，调用时传入
# system_text = ASSISTANT_SYSTEM_TEMPLATE.format(teacher_id="123")

# 或直接用 ChatPromptTemplate（多轮 / 与 pyannote 一致）
from prompts import ASSISTANT_CHAT_PROMPT_WITH_TOOLS
messages = ASSISTANT_CHAT_PROMPT_WITH_TOOLS.invoke({}).messages
```
