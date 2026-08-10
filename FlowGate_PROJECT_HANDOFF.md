# FlowGate 高中生物智能组卷 Agent 项目交接

更新时间：2026-08-11（Asia/Shanghai）

## 1. 文档用途

这是项目的跨会话、跨 Codex 账号交接入口。后续 Codex 应先读取本文件，再检查代码、数据库迁移和测试结果，不应只依赖聊天记录判断进度。

项目实际目录：`/home/lijinyang/FlowGate`（WSL 发行版：`Ubuntu-24.04`）

Windows 备份位置：`E:\Projects\FlowGate_PROJECT_HANDOFF.md`

## 2. 当前目标

FlowGate 的长期定位是企业级 Agent 工作流平台，底座包括 FastAPI、LangGraph、PostgreSQL、Redis、Qdrant、权限审批、可观测性与 RAG。

当前垂直 MVP 是“高中生物智能组卷 Agent”：

1. 教师输入题型、数量、难度、知识范围、分值等组卷要求。
2. 系统从合规网络来源、指定网站或本地题库获取题目。
3. 将题目规范化、去重、标注知识点和核心素养，并保留完整来源。
4. 在约束条件下智能组合试卷，进行质量检查和教师审核。
5. 输出可编辑 Word 以及打印版 PDF，包含试卷、答案和解析。

当前阶段仍在“领域数据与持久化基础设施”建设期，尚未进入网络采集、检索、智能组卷和文档导出主链路。

## 3. BIO 任务进度

| ID | 状态 | 已完成内容 / 验收结果 |
| --- | --- | --- |
| BIO-001 | 完成 | PostgreSQL 配置与连接；容器 healthy；后端 `SELECT 1` 成功。 |
| BIO-002 | 完成 | Backend、PostgreSQL、Redis、Qdrant 已纳入 Compose 并可通信。 |
| BIO-003 | 完成 | 创建 `paper_agent` 模块并由 FastAPI 正常加载。 |
| BIO-004 | 完成 | 安装 LangGraph 相关依赖；最小 Graph 可启动和执行。 |
| BIO-005 | 完成 | 增加组卷模型、存储路径和模板路径配置。 |
| BIO-006 | 完成 | 按任务记录继续完善组卷配置与环境变量，配置可由环境覆盖。 |
| BIO-007 | 完成 | 定义结构化 `Question`，支持题干、选项、小问、答案、解析和图片。 |
| BIO-008 | 完成 | 定义 `PaperJob` 及审核状态，可记录任务状态、失败原因和审核结果。 |
| BIO-009 | 完成 | 定义题目来源与资源模型，每道题和图片均可追溯来源。 |
| BIO-010 | 完成 | 编写 Alembic 初始迁移，新数据库可一键创建全部基础表。 |
| BIO-011 | 完成 | 初始化 5 个课程模块、32 个知识点、4 类核心素养，并提供查询 API。 |

注意：BIO-005 与 BIO-006 的任务描述在原对话中重复，后续重整任务表时应消除重复编号或明确两者边界。

## 4. BIO-011 里程碑

数据库已能同时保存一项组卷任务和一道结构化题目，并建立题目、知识点、核心素养、来源、资源及图片之间的关系。

主数据库保留以下验收样例：

- 任务 ID：`bio011-milestone-job`
- 题目 ID：`bio011-milestone-question`
- 题型：`single_choice`
- 选项数：3
- 图片数：1
- 知识点数：1
- 核心素养数：2

高中生物标签：

- 5 个课程模块：分子与细胞、遗传与进化、稳态与调节、生物与环境、生物技术与工程
- 32 个顶层知识点
- 4 类核心素养：生命观念、科学思维、科学探究、社会责任

## 5. 当前技术基线

- 后端：Python、FastAPI、SQLAlchemy、Alembic、LangGraph
- 前端：Next.js、React、TypeScript
- 数据服务：PostgreSQL 16、Redis 7、Qdrant
- 运行方式：Docker Compose
- 版本控制：本地分支 `flowgate`，跟踪远程 `https://github.com/ljyloves/agent-learning.git` 的 `origin/flowgate`
- Alembic 当前版本：`20260810_0002 (head)`
- 自动化测试：最近一次为 `20/20` 通过
- 2026-08-11 核查状态：Backend、PostgreSQL、Redis、Qdrant 均为 healthy；Frontend running

主要实现位置：

- `backend/app/modules/paper_agent/`
- `backend/app/models/paper_agent.py`
- `backend/app/models/taxonomy.py`
- `backend/alembic/versions/20260810_0001_create_initial_schema.py`
- `backend/alembic/versions/20260810_0002_seed_biology_taxonomy.py`
- `backend/tests/modules/paper_agent/`
- `backend/tests/models/test_metadata.py`

现有 Paper Agent 接口：

- `GET /api/paper-agent/health`
- `POST /api/paper-agent/graph/smoke`
- `GET /api/paper-agent/taxonomy/biology`
- `POST /api/paper-agent/jobs/with-question`

## 6. 恢复与验证命令

在 Windows 终端执行：

```powershell
wsl -d Ubuntu-24.04
cd /home/lijinyang/FlowGate
docker compose up -d --build
docker compose ps
docker compose exec backend alembic current
docker compose exec backend alembic check
docker compose exec backend python -m unittest discover -s tests -v
curl -fsS http://localhost:8000/api/health
curl -fsS http://localhost:8000/api/paper-agent/taxonomy/biology
```

不要提交根目录 `.env`，只维护不含真实密钥的 `.env.example`。

## 7. 当前风险与待办

1. FlowGate 使用公开仓库 `ljyloves/agent-learning` 的独立 `flowgate` 分支；远程 `main` 属于另一套 Agent 学习代码，未经明确计划不要合并或覆盖。
2. `.gitignore` 已排除 `.env`、`*.orig`、`__pycache__`、虚拟环境、前端构建产物和运行时数据；每次提交前仍需执行密钥检查。
3. `project-progress-plan.md` 仍以通用企业 Agent 路线为主，尚未完整反映 BIO-001 至 BIO-011 的实际进度，本文件暂时作为 BIO MVP 的事实来源。
4. BIO-012 尚未由用户正式定义。继续编码前，应先确定下一任务及验收标准，不要根据旧对话擅自假设编号。
5. 逻辑上的下一阶段应围绕“组卷请求规格 -> 题目导入/采集 -> 去重与质量评估 -> 约束组卷 -> 教师审核 -> Word/PDF 导出”拆分，但以用户确认后的任务表为准。

## 8. 推荐的跨账号持续方案

推荐优先级：

1. FlowGate 已初始化为 Git 仓库，并使用远程 `agent-learning` 的独立 `flowgate` 分支保存基线。
2. 每完成一个 BIO 任务，更新本文件和任务表，再创建一个小而明确的 Git 提交。
3. 在仓库根目录保留 `AGENTS.md`，记录长期不变的运行、测试、编码和安全约束；本文件只记录会变化的进度。
4. 数据库中的重要验收数据应配套可重复执行的 seed 或测试，不把本地 Docker volume 当作唯一副本。
5. 新账号打开同一 WSL 项目后，让 Codex先读取本文件、`AGENTS.md`、迁移目录和最近 Git 提交，再开始下一任务。

## 9. 新账号首条提示词

```text
请接手 /home/lijinyang/FlowGate 项目。先阅读仓库根目录的
FlowGate_PROJECT_HANDOFF.md、project-progress-plan.md、AGENTS.md（若存在），
然后检查 git status、docker compose ps、Alembic current/check 和自动化测试。
不要修改或删除现有成果，不要读取或输出 .env 中的密钥。
先向我汇报实际状态与交接文档是否一致，再继续执行我指定的下一个 BIO 任务。
```

## 10. 交接完成标准

新的 Codex 会话无需访问旧聊天记录，也能从仓库文件恢复以下信息：项目目标、已完成任务、数据库版本、验收样例、运行命令、已知风险和下一步决策点。
