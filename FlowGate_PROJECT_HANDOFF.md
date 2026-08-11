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

当前阶段已完成领域数据、持久化基础设施、M2 轻量图状态、节点契约、可恢复条件分支主工作流、PostgreSQL checkpoint 持久化、首批 100 道“分子与细胞”合成测试题、严格约束的基础组卷算法、可中断恢复的教师审核和统一组卷任务 API；M2 本地假题库全流程验收已通过，尚未进入网络采集、质量评估和文档导出主链路。

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
| BIO-012 | 完成 | 定义严格轻量 `PaperGraphState`，状态仅包含 ID、结构化报告和执行状态；最小图与 smoke API 验收通过。 |
| BIO-013 | 完成 | 定义 Graph 节点输入输出契约；当前及后续注册节点必须使用 Pydantic 校验输入、输出和合并状态。 |
| BIO-014 | 完成 | 实现主工作流与条件边，可处理通过、失败、重试和换题；重试可恢复、换题可校验，重试耗尽自动失败。 |
| BIO-015 | 完成 | 接入 PostgreSQL Checkpointer；任务状态按 `thread_id` 持久化，backend 容器重启后可查询并继续执行。 |
| BIO-016 | 完成 | 建立可重复迁移的假题库；PostgreSQL 中包含 100 道“分子与细胞”结构化测试题。 |
| BIO-017 | 完成 | 实现基础组卷算法；数量、总分、题型和难度由请求契约、查询条件与响应契约三层严格校验。 |
| BIO-018 | 完成 | 实现教师审核中断与恢复；支持暂停、通过、驳回，以及换题后再次暂停并继续审核。 |
| BIO-019 | 完成 | 提供统一组卷任务 API；可创建任务、查看持久化状态并提交教师审核。M2 假题库完整组卷流程验收通过。 |

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

### BIO-012 M2 状态里程碑

- `PaperGraphState` 仅保存 `job_id`、`paper_id`、候选/已选题目 ID、受限结构化报告和执行状态。
- 状态模型禁止额外字段，题干、答案、来源、资源和 ORM 对象不能进入 checkpoint 状态。
- 报告只允许受限摘要、标量指标和问题代码，并限制 ID、报告、指标及问题集合大小。
- 选中题目 ID 必须来自候选题目 ID；失败执行状态必须包含错误代码。
- `POST /api/paper-agent/graph/smoke` 已返回可 JSON 序列化的轻量状态。

### BIO-013 M2 节点契约里程碑

- `GraphNodeContract` 为每个节点绑定完整 State、节点 Input 和节点 Output 三类 Pydantic 模型。
- `validated_node` 在节点执行前校验完整 State 与节点输入，执行后校验节点输出，并在返回前重新校验合并后的完整 State。
- 同步节点和异步节点使用同一契约机制。
- `add_contract_node` 拒绝注册未声明契约的节点，当前 `initialize` 节点已完整接入。
- `add_contract_node` 显式以完整 `PaperGraphState` 注册 LangGraph 输入，包装器再按节点 Input 投影字段，防止连续节点间状态字段丢失。
- `InitializeNodeInput` 只声明节点实际消费的字段，`InitializeNodeOutput` 只声明节点允许更新的字段。

### BIO-014 M2 主工作流里程碑

- 主图为 `START -> initialize -> decide -> 条件分支 -> END`，分支包括 `complete`、`fail`、`retry` 和 `replace_question`。
- 无 `quality_gate` 报告时默认通过；存在报告时由其 `decision` 标量选择 `pass`、`fail`、`retry` 或 `replace`。
- `pass` 进入 `completed` 终态；`fail` 进入带 `error_code` 的 `failed` 终态。
- `retry` 累加重试次数并以 `queued` 结束本次执行，等待外部触发下一次评估；最多允许 3 次，耗尽后以 `RETRY_LIMIT_EXCEEDED` 失败。
- `replace` 仅允许将已选题替换为候选池内且尚未选中的题目，替换后以 `queued` 结束，等待后续重新评估。
- 所有主工作流节点都声明独立 Pydantic 输入输出契约；非法决策和非法换题在节点执行前被拒绝。

### BIO-015 M2 Checkpointer 里程碑

- 使用官方 `AsyncPostgresSaver`、`psycopg` 和异步连接池，Graph runtime 由 FastAPI lifespan 创建并关闭。
- 应用启动时执行 Saver 自带 `setup()`，数据库包含 `checkpoints`、`checkpoint_blobs`、`checkpoint_writes`、`checkpoint_migrations` 四张库管表。
- Checkpointer 使用独立 psycopg DSN 与可配置连接池；SQLAlchemy 业务会话仍使用 `asyncpg`，两者生命周期互不混用。
- Checkpoint 序列化器显式允许项目 Enum，并已在 `LANGGRAPH_STRICT_MSGPACK=true` 下通过恢复测试。
- 新增按 `thread_id` 启动、读取和恢复任务的接口；重复启动返回冲突，不存在任务返回 404，仅 `queued` 状态允许恢复。
- 自动化测试会关闭第一套 Saver/Graph runtime，再创建第二套 runtime 读取并继续任务，模拟服务进程重启。
- 真实验收任务 `bio015-http-thread` 在 backend 容器重启后从 `queued/attempt=1` 恢复到 `completed/attempt=2`，`retry_count=1` 保持不变。
- LangGraph checkpoint 表由其内置 `checkpoint_migrations` 管理，Alembic autogenerate 已明确排除这些表，业务 schema 检查仍保持无漂移。

### BIO-016 假题库里程碑

- Alembic `20260811_0003` 使用稳定 UUID 写入 100 道合成测试题，新数据库升级到 head 后可重复获得同一题库。
- 题库由 25 个知识概念生成，每个概念包含 2 道单选、1 道判断和 1 道填空；共 50 道单选、25 道判断、25 道填空。
- 100 道题干均唯一，每题都有答案、解析、知识点、核心素养和可追溯来源；50 道单选题均有 4 个选项。
- 覆盖“分子与细胞”全部 7 个知识点，分布为 `16、16、12、12、16、16、12`。
- 合成来源 ID 为 `bio016-molecular-cell-mock-bank`，`external_id=BIO-016`，明确标记为非真实测评数据。
- downgrade 仅按稳定题目 ID 删除 BIO-016 数据，并通过级联关系清理选项与标签，不影响其他题目来源。

### BIO-017 基础组卷里程碑

- Alembic `20260811_0004` 为题目增加 `easy`、`medium`、`hard` 三档难度和数据库约束；BIO-016 假题库的每种题型均覆盖三档难度。
- 组卷请求按“题型 + 难度 + 数量 + 每题分值”定义分区，并要求声明的题目总数和总分与所有分区汇总严格一致。
- 分值属于本次试卷蓝图，不作为题目的永久属性；同一道题可在不同试卷中使用不同分值。
- 算法按课程模块、题型和难度从 PostgreSQL 取候选题，支持固定随机种子复现结果和排除题目 ID 进行换题。
- 任一分区库存不足时整次组卷以 `INSUFFICIENT_QUESTION_BANK` 失败，不返回不完整试卷。
- `POST /api/paper-agent/papers/assemble` 已真实返回 7 题、26 分，三组题型与难度配额全部精确匹配。

### BIO-018 教师审核里程碑

- 新增独立教师审核图：`initialize -> queue_teacher_review -> await_teacher_review`，使用 LangGraph `interrupt()` 在人工决策点真实暂停。
- 教师动作通过 `Command(resume=...)` 恢复，`approve` 进入完成终态，`reject` 以 `TEACHER_REJECTED` 进入失败终态。
- `replace` 复用严格换题节点，校验旧题已选、新题属于候选且尚未选中；换题后自动再次进入 `awaiting_review`，可继续换题、通过或驳回。
- 教师、意见、操作轮次和换题记录写入受限 checkpoint 报告；状态仍只保存 ID、报告和执行控制数据。
- 教师审核使用 `teacher-review:` 线程前缀与自动质量工作流隔离，并复用同一 PostgreSQL Saver；runtime 重建后仍可恢复中断。
- 真实 HTTP 验收任务已完成 `awaiting_review -> replace -> awaiting_review -> approve -> completed` 全链路，换题后题目从 `question-2` 更新为 `question-3`。

### BIO-019 任务 API 与 M2 验收里程碑

- Alembic `20260811_0005` 为 `paper_jobs` 增加 `assembly_request` 与 `assembly_result` JSONB，任务重启后仍可返回原始蓝图和当前试卷。
- `POST /api/paper-agent/tasks` 一次完成严格组卷、任务与题目关联落库、候选池建立和教师审核 interrupt，创建结果为 `awaiting_review/pending`。
- `GET /api/paper-agent/tasks/{job_id}` 返回业务状态、审核结果、当前试卷、题目数、总分和时间信息。
- `POST /api/paper-agent/tasks/{job_id}/review` 支持通过、驳回和换题；审核结果同步至 `paper_jobs.review_status/review_result`。
- 换题同时更新 checkpoint 所选题目、`paper_job_questions` 关联和持久化试卷 JSON，并再次通过 `PaperAssemblyResult` 校验数量、总分、题型和难度。
- M2 真实验收任务 `ef1845c3-8813-46dc-83d4-155c6372a589` 全程未访问互联网，仅使用 BIO-016 假题库完成 `create -> get -> approve -> get`；最终为 7 题、26 分、`completed/approved`。

## 5. 当前技术基线

- 后端：Python、FastAPI、SQLAlchemy、Alembic、LangGraph、langgraph-checkpoint-postgres、psycopg
- 前端：Next.js、React、TypeScript
- 数据服务：PostgreSQL 16、Redis 7、Qdrant
- 运行方式：Docker Compose
- 版本控制：本地分支 `flowgate`，跟踪远程 `https://github.com/ljyloves/agent-learning.git` 的 `origin/flowgate`
- Alembic 当前版本：`20260811_0005 (head)`
- 自动化测试：最近一次为 `77/77` 通过
- 2026-08-11 核查状态：Backend、PostgreSQL、Redis、Qdrant 均为 healthy；Frontend running

主要实现位置：

- `backend/app/modules/paper_agent/`
- `backend/app/modules/paper_agent/graph/state.py`
- `backend/app/modules/paper_agent/graph/contracts.py`
- `backend/app/modules/paper_agent/graph/checkpoint.py`
- `backend/app/modules/paper_agent/graph/workflow.py`
- `backend/app/modules/paper_agent/nodes/branches.py`
- `backend/app/modules/paper_agent/nodes/initialize.py`
- `backend/app/modules/paper_agent/nodes/teacher_review.py`
- `backend/app/modules/paper_agent/schemas/checkpoint.py`
- `backend/app/modules/paper_agent/schemas/assembly.py`
- `backend/app/modules/paper_agent/schemas/task.py`
- `backend/app/modules/paper_agent/services/checkpoint.py`
- `backend/app/modules/paper_agent/services/assembly.py`
- `backend/app/modules/paper_agent/services/task.py`
- `backend/app/models/paper_agent.py`
- `backend/app/models/taxonomy.py`
- `backend/alembic/versions/20260810_0001_create_initial_schema.py`
- `backend/alembic/versions/20260810_0002_seed_biology_taxonomy.py`
- `backend/alembic/versions/20260811_0003_seed_molecular_cell_question_bank.py`
- `backend/alembic/versions/20260811_0004_add_question_difficulty.py`
- `backend/alembic/versions/20260811_0005_add_paper_job_assembly_payloads.py`
- `backend/tests/modules/paper_agent/`
- `backend/tests/modules/paper_agent/test_mock_question_bank.py`
- `backend/tests/modules/paper_agent/test_assembly_schema.py`
- `backend/tests/modules/paper_agent/test_paper_assembly.py`
- `backend/tests/modules/paper_agent/test_question_persistence.py`
- `backend/tests/modules/paper_agent/test_teacher_review_schema.py`
- `backend/tests/modules/paper_agent/test_teacher_review_workflow.py`
- `backend/tests/modules/paper_agent/test_teacher_review_checkpoint.py`
- `backend/tests/modules/paper_agent/test_task_schema.py`
- `backend/tests/modules/paper_agent/test_paper_task.py`
- `backend/tests/models/test_metadata.py`

现有 Paper Agent 接口：

- `GET /api/paper-agent/health`
- `POST /api/paper-agent/graph/smoke`
- `POST /api/paper-agent/graph/tasks/{thread_id}`
- `GET /api/paper-agent/graph/tasks/{thread_id}`
- `POST /api/paper-agent/graph/tasks/{thread_id}/resume`
- `GET /api/paper-agent/taxonomy/biology`
- `POST /api/paper-agent/jobs/with-question`
- `POST /api/paper-agent/papers/assemble`
- `POST /api/paper-agent/reviews/{thread_id}`
- `GET /api/paper-agent/reviews/{thread_id}`
- `POST /api/paper-agent/reviews/{thread_id}/actions`
- `POST /api/paper-agent/tasks`
- `GET /api/paper-agent/tasks/{job_id}`
- `POST /api/paper-agent/tasks/{job_id}/review`

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
curl -fsS -X POST http://localhost:8000/api/paper-agent/graph/smoke
```

不要提交根目录 `.env`，只维护不含真实密钥的 `.env.example`。

## 7. 当前风险与待办

1. FlowGate 使用公开仓库 `ljyloves/agent-learning` 的独立 `flowgate` 分支；远程 `main` 属于另一套 Agent 学习代码，未经明确计划不要合并或覆盖。
2. `.gitignore` 已排除 `.env`、`*.orig`、`__pycache__`、虚拟环境、前端构建产物和运行时数据；每次提交前仍需执行密钥检查。
3. `project-progress-plan.md` 仍以通用企业 Agent 路线为主，尚未完整反映 BIO-001 至 BIO-019 的实际进度，本文件暂时作为 BIO MVP 的事实来源。
4. 后续 BIO 任务尚未由用户正式定义。继续编码前，应先确定下一任务及验收标准，不要根据旧对话擅自假设编号。
5. M2 已具备离线假题库完整闭环；逻辑上的下一阶段应围绕“题目导入/采集 -> 去重与质量评估 -> 扩展组卷约束 -> Word/PDF 导出”拆分，但以用户确认后的任务表为准。
6. Checkpoint 当前尚未配置 TTL、归档或定期清理策略；在进入长期运行或多租户阶段前需要定义保留周期和清理责任。
7. Question 已支持难度筛选，但仍无年级、教材版本、来源质量等检索字段；基础算法尚未支持知识点配额、跨题型动态分值和相似题去重。
8. BIO-019 已同步 checkpoint 与 `paper_jobs` 审核状态，但两套存储仍是应用层双写，不属于单一数据库事务；进入多实例生产环境前应增加幂等操作、失败补偿和状态对账任务。

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
