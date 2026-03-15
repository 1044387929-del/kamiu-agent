# kamiu_agent

教师智能助手：LangGraph + FastAPI，与 Django 解耦，支持对话、查数、学科知识（规划中）。

## 项目结构

```
kamiu_agent/
├── app/
│   ├── main.py       # FastAPI 入口
│   └── config.py     # 配置（从 config/*.env 加载）
├── graph/            # LangGraph 图
│   ├── state.py      # 图状态
│   ├── nodes.py      # 节点逻辑
│   └── graph.py      # 图构建
├── tools/            # 工具（如调 Django 执行代码、向量检索）
├── api/
│   └── routes.py    # 接口：/api/chat 等
├── config/          # 环境配置（llm.env, database.env）
├── requirements.txt
└── run.sh            # 启动脚本
```

## 配置变量（需修改后才生效）

`config/*.env` 已被 git 忽略，需自行从示例复制并填写：

```bash
cd config
cp llm.env.example llm.env
cp database.env.example database.env
# 编辑 llm.env、database.env，填入实际值
```

| 文件 | 变量 | 说明 |
|------|------|------|
| **llm.env** | `DASHSCOPE_API_KEY` | 千问 API Key，必填 |
| **llm.env** | `LLM_MODEL` | 模型名，默认 `qwen-plus` |
| **database.env** | `DB_NAME` / `DB_USER` / `DB_PASSWORD` 等 | 数据库连接（若需连库） |
| **database.env** | `REDIS_URL` | Redis 地址（若需要） |

## 运行

```bash
# 安装依赖
pip install -r requirements.txt

# 确认 config/llm.env 等已配置后再启动（默认 8002 端口）
bash run.sh
# 或
PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

- 健康检查：`GET http://localhost:8002/health`
- 对话：`POST http://localhost:8002/api/chat`，body: `{"message": "你好", "teacher_id": "xxx"}`

---

#### 介绍
{**以下是 Gitee 平台说明，您可以替换此简介**
Gitee 是 OSCHINA 推出的基于 Git 的代码托管平台（同时支持 SVN）。专为开发者提供稳定、高效、安全的云端软件开发协作平台
无论是个人、团队、或是企业，都能够用 Gitee 实现代码托管、项目管理、协作开发。企业项目请看 [https://gitee.com/enterprises](https://gitee.com/enterprises)}

#### 软件架构
软件架构说明


#### 安装教程

1.  xxxx
2.  xxxx
3.  xxxx

#### 使用说明

1.  xxxx
2.  xxxx
3.  xxxx

#### 参与贡献

1.  Fork 本仓库
2.  新建 Feat_xxx 分支
3.  提交代码
4.  新建 Pull Request


#### 特技

1.  使用 Readme\_XXX.md 来支持不同的语言，例如 Readme\_en.md, Readme\_zh.md
2.  Gitee 官方博客 [blog.gitee.com](https://blog.gitee.com)
3.  你可以 [https://gitee.com/explore](https://gitee.com/explore) 这个地址来了解 Gitee 上的优秀开源项目
4.  [GVP](https://gitee.com/gvp) 全称是 Gitee 最有价值开源项目，是综合评定出的优秀开源项目
5.  Gitee 官方提供的使用手册 [https://gitee.com/help](https://gitee.com/help)
6.  Gitee 封面人物是一档用来展示 Gitee 会员风采的栏目 [https://gitee.com/gitee-stars/](https://gitee.com/gitee-stars/)
