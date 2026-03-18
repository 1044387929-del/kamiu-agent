# 提示词模板（prompts）

与 `pyannote_diarization/prompts` 同风格：提示词集中在此目录，由各模块按需引用。

## 结构

- **assistant.py** — 教师助手对话
  - `ASSISTANT_SYSTEM`：基础系统提示（直连对话、流式等用）
  - `ASSISTANT_SYSTEM_WITH_TOOLS`：带工具说明（Agent 图用）

## 使用

```python
from prompts import ASSISTANT_SYSTEM, ASSISTANT_SYSTEM_WITH_TOOLS
# 或
from prompts.assistant import ASSISTANT_SYSTEM
```

后续若增加变量（如 `teacher_id`），可改为 `ChatPromptTemplate.from_messages` + `invoke({...})`，与 pyannote 的 `prompts/refine`、`prompts/eval_and_sug` 一致。
