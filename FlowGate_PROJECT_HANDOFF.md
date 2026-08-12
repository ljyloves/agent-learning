# FlowGate 高中生物智能组卷 Agent 项目交接

更新时间：2026-08-12（Asia/Shanghai）

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

当前阶段已完成领域数据、持久化基础设施、M2 离线组卷与教师审核闭环，以及 M3 的教师文件/白名单网页采集、题目解析、题图存储、混合检索、候选去重、LLM 标签标注、难度估计、基础题目质量审核、多约束优化组卷、教师可控调整、DOCX/PDF 文档导出质量门和 BIO-036 全链路验收；尚未进入教师金标校准。

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
| BIO-020 | 完成 | 实现教师文件上传；支持 PDF、DOCX、DOC 及常见图片，并保存文件快照、哈希和来源关系。 |
| BIO-021 | 完成 | 实现确定性题目解析与切分；可识别题干、选项、答案、解析和小问，并将结果写入结构化题目表。 |
| BIO-022 | 完成 | 建立题图归档、共享引用和完整性校验；图片原始字节不丢失，题目及资源引用可通过 API 恢复。 |
| BIO-023 | 完成 | 实现首个 OpenStax 白名单网站适配器；可采集指定 HTTPS 页面并保存 HTML 快照与来源。 |
| BIO-024 | 完成 | 实现 PostgreSQL 关键词与 Qdrant 向量混合检索；知识点和题型双侧硬过滤，可召回并融合候选题。 |
| BIO-025 | 完成 | 实现完全去重和语义去重；确定性验收样本的剩余重复率为 0%，低于 2%。 |
| BIO-026 | 完成 | 实现 LLM 知识点和核心素养标注；模型输出受动态 JSON Schema、Pydantic 和数据库有效标签三层约束。 |
| BIO-027 | 完成 | 实现难度估计；每次分析同时输出 1～5 级难度、预计正确率、置信度和理由，并追加保存分析历史。 |
| BIO-028 | 完成 | 实现题目质量审核；确定性规则与 LLM 联合识别缺图、缺答案、歧义和超纲，结果可审计且不覆盖原题。 |
| BIO-029 | 完成 | 使用 OR-Tools CP-SAT 完善约束优化算法；同时严格满足知识点覆盖、1～5 级难度配额、多样性、质量通过和重复题互斥。 |
| BIO-030 | 完成 | 实现持久化优化任务的锁题、换题和重新组卷；锁定题不会被替换，所有修改均重新执行完整硬约束求解，无可行解时保持原试卷。 |
| BIO-031 | 完成 | 制作 A4 学生卷 Word 模板与导出 API；题号连续、题图可恢复、长题自然分页，选项行不拆分，并提供 PAGE/NUMPAGES 页脚。 |
| BIO-032 | 完成 | 制作 A4 教师答案解析模板与导出 API；严格输出每题答案、解析、知识点名称、1～5 级难度和预计正确率，元数据不完整时拒绝导出。 |
| BIO-033 | 完成 | 制作 A4 答题卡模板与导出 API；与学生卷共享同一组卷题序，按题型生成选择区、填空线及综合题小问区。 |
| BIO-034 | 完成 | 实现学生卷、教师解析卷和答题卡的 DOCX/PDF 下载；PDF 从同一 DOCX 内容源经服务端 LibreOffice 转换，并自动校验正文一致性。 |
| BIO-035 | 完成 | 文档渲染自动检查接入 PDF 导出质量门；自动拒绝缺图、空页、答案泄漏和异常断页，并在下载响应中返回检查结果与图像计数。 |
| BIO-036 | 完成 | 固定高中生物 MVP 蓝图完成全链路组卷、PostgreSQL 检查点恢复、教师批准、六份 DOCX/PDF 导出和渲染检查；验收报告状态为 `passed`。 |

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

### BIO-020 教师文件上传里程碑

- `POST /api/paper-agent/sources/files` 使用 multipart 上传，支持 PDF、DOCX、DOC、PNG、JPEG、GIF 和 WebP。
- 文件同时校验扩展名、客户端 MIME 与真实文件签名；DOCX 还校验 ZIP 中的 Word 结构，拒绝伪装格式。
- 上传使用随机资源 ID 命名，拒绝路径文件名，限制最大字节数，并以临时文件加原子替换写入 `storage/paper_agent/uploads`。
- 每次上传保存 SHA-256、规范 MIME、原始文件名、`question_sources` 和 `question_resources` 关系；数据库失败时回滚并删除磁盘文件。
- 真实 HTTP 已分别上传 PDF、Word DOC 和 PNG，均返回 201、来源 ID、资源 ID、哈希和可追溯存储路径；DOCX 由自动化测试覆盖。

### BIO-021 题目解析与切分里程碑

- `POST /api/paper-agent/sources/resources/{resource_id}/questions` 从已上传文档抽取内容、切分题目、通过 Pydantic 校验并在同一事务中持久化。
- 规则解析器覆盖常见中文题库格式：数字题号、A-H 选项、`答案/参考答案`、`解析/答案解析`、`(1)/(2)` 小问及分行小问答案。
- DOCX 使用 OOXML 保留段落顺序和内嵌图位置；可提取文本的 PDF 使用 pypdf，旧 DOC 使用受限的 antiword 转文本。
- 题型根据选项、答案和填空标记确定为单选、多选、判断、填空、简答或复合题；默认难度可由请求指定。
- 解析失败、数据库失败或恢复校验失败时回滚事务，并删除本次已写入的题图文件。

### BIO-022 题图与资源存储里程碑

- Alembic `20260811_0006` 移除题图资源的一对一限制并增加普通索引，同一物理图片可被多道题或选项共享引用。
- 内嵌图片按随机资源 ID 写入 `storage/paper_agent/assets/{source_resource_id}`，保存规范 MIME、SHA-256、来源和题目/选项位置关系。
- `GET /api/paper-agent/questions/{question_id}` 可递归恢复选项、小问和题图；`GET /api/paper-agent/resources/{resource_id}/content` 在路径边界及 SHA-256 校验通过后返回原始文件。
- 聚焦测试使用同一张 DOCX 内嵌图绑定两道题，验证数据库仅保存一份资源、建立两条引用、原始 PNG 字节可恢复，篡改后读取被拒绝。
- 真实 HTTP 验收来源 `abe7965a-a4b2-447d-8f49-1a80c9f73fd7`：解析出 2 道主问题、2 个小问；题图资源 `0a0faa9a-b5ff-4417-a125-68b8865f2554` 恢复后 SHA-256 为 `efb2c6c14a06aeae34c08b8609d66dfd61b582e8679c91870bdab10dd65540cd`。

### BIO-023 OpenStax 白名单适配器里程碑

- 首个适配器固定支持 `openstax.org` 与 `www.openstax.org`，配置可进一步收窄白名单。
- 仅允许 HTTPS、无凭证、默认 443 端口；最多跟随 3 次同白名单重定向，跨域重定向会被拒绝。
- 仅接收 HTML/XHTML，流式限制响应大小，提取页面标题，并保存原始 HTML 快照、SHA-256、最终 URL 和来源关系。
- MockTransport 测试覆盖同域重定向、落库、快照、非白名单域名和跨域重定向拒绝。
- 真实 HTTP 已采集 `https://openstax.org/subjects/science`：来源 ID `65098122-7bb0-43ee-b3b3-f76679c3e925`，HTML 快照 12,410 字节，标题 `OpenStax`。

### BIO-024 关键词与向量混合检索里程碑

- 新增独立 Qdrant 集合 `paper_questions`，与通用 RAG 的 `knowledge_chunks` 隔离；payload 索引覆盖题目 ID、题型、难度和知识点代码。
- `POST /api/paper-agent/retrieval/questions/index` 从 PostgreSQL 读取题干、选项、答案、解析和知识点描述，生成可重建的题目向量索引；无标签或不存在的指定题目会被拒绝。
- `POST /api/paper-agent/retrieval/questions/search` 使用中文字符 n-gram/短语关键词分数与向量余弦召回，再通过加权 RRF 融合；默认关键词和向量权重均为 0.5。
- 知识点与题型同时在 PostgreSQL 和 Qdrant 过滤，向量结果返回 PostgreSQL 二次验证，Qdrant 过期或异常 payload 不会绕过业务过滤。
- 关键词候选池有上限；向量检索面向完整 Qdrant 过滤集合，不会被 PostgreSQL 按 ID 截断后再做近邻搜索。
- 内存 Qdrant 聚焦测试索引完整 BIO-016 题库，验证双侧过滤、融合排序、未知标签/无标签索引拒绝，以及向量候选不受关键词池截断。
- 真实 HTTP 已向 `paper_questions` 索引 101 道带标签题目；查询 `BIO-M1-K02 + single_choice + 细胞膜的选择透过性和磷脂双分子层` 时关键词与向量分支各召回 8 道，融合首位为细胞膜结构题 `ffff37e8-4e75-5548-ad91-28af50db02d7`。

### BIO-025 完全去重、语义去重与采集单元里程碑

- 混合检索默认在融合排序后执行两阶段候选去重：题型、规范化题干及有序选项生成 SHA-256 精确指纹，再以同题型、长度/表面相似度保护条件和 Embedding 余弦相似度识别高度相似题。
- 搜索请求支持关闭去重或调整语义阈值，默认阈值为 `0.94`；响应返回输入数、精确/语义剔除数、输出数、剩余重复率，以及被剔除题与保留题的审计映射。
- 检索候选新增 `source_id`，可从结果直接追溯来源；文件或网页解析请求可附加知识点代码，持久化时验证标签并建立题目关系，解析结果可以直接进入 BIO-024 索引流程。
- OpenStax 快照新增确定性 HTML 题目解析，覆盖题干和 A-H 选项，不调用 LLM；来源保存 `OpenStax` attribution 与 `CC BY-NC-SA` 许可标识。
- 去重聚焦样本同时含格式完全重复题、语义高度相似题和不同题，精确与语义重复各剔除 1 道，剩余重复率 `0%`，满足低于 `2%` 的验收标准。
- 真实单元里程碑验收：教师 DOCX 产生 2 道候选题，OpenStax Biology 2e Chapter 2 Review Questions 产生 10 道候选题；共 12 道均保存 `BIO-M1-K02` 标签且来源可追溯，验收数据随后清理。

### BIO-026 LLM 知识点与核心素养标注里程碑

- 新增 `POST /api/paper-agent/questions/{question_id}/taxonomy-annotation`，对已结构化题目执行知识点与核心素养标注，可选择是否替换已有标签。
- 每次调用从 PostgreSQL 加载当前激活的 32 个知识点和 4 类核心素养，并把实际代码写入严格 JSON Schema `enum`；禁止额外字段、重复代码、空标签和越界数量。
- 模型结果依次经过 JSON Schema 约束、`TaxonomyAnnotationLLMOutput` Pydantic 校验和数据库有效代码集合校验，未知或停用标签不会写入关系表。
- 题干、选项、小问、答案、解析及图片替代文本作为不可信分类材料；系统提示明确忽略题目中的指令，降低提示注入影响。
- 标签替换使用题目行锁和单事务写入；模型失败、输出无效、题目并发修改或关系冲突时保留原标签。`replace_existing=false` 会在调用模型前拒绝已有标签题，避免无效费用。
- OpenStax 来源在服务层默认禁止发送给生成式 AI，返回 403；只有后续建立明确授权机制后才能放开。
- 5 项聚焦测试覆盖动态标签枚举、严格 schema、提示注入隔离、标签排序落库、未知标签不污染、已有标签保护和 OpenStax 策略拦截；全量测试 `96/96` 通过。
- HTTP 验收确认 OpenAPI 已注册新接口；对已有标签题禁止覆盖时返回 409，且不会调用 LLM。真实外部模型调用仍依赖部署环境配置有效 `OPENAI_API_KEY`。

### BIO-027/028 难度估计与题目质量审核里程碑

- Alembic `20260811_0007` 新增追加式 `question_analyses` 表，按题目、分析类型和时间建立索引；难度与质量结果保留独立历史，不覆盖题目人工难度或原始内容。
- `POST /api/paper-agent/questions/{question_id}/difficulty-estimation` 同时输出 `difficulty_level=1..5`、`estimated_correct_rate=0..1`、置信度和理由；Pydantic 额外校验等级与正确率区间一致。
- `POST /api/paper-agent/questions/{question_id}/quality-review` 只允许 `missing_image`、`missing_answer`、`ambiguity`、`out_of_scope` 四类问题；缺图和缺答案由确定性规则兜底，歧义和超纲结合完整高中生物标签体系由模型判断。
- 两项分析都要求题目已有有效知识点与核心素养标签，并在持久化前锁定题目行；题目在模型调用期间变化时拒绝写入，OpenStax 来源继续受生成式 AI 策略拦截。
- 优先使用提供方原生 `response_format=json_schema`；仅当兼容网关明确拒绝该参数时，将同一 Schema 注入系统消息并取消该参数，最终仍由禁止额外字段的 Pydantic 契约严格校验，不合格结果不入库。
- 本机 `.env` 已增加 `PAPER_AGENT_MODEL=deepseek-v4-flash`，以匹配当前兼容网关；旧 `OPENAI_MODEL` 不会覆盖组卷模块配置，`.env` 仍由 Git 忽略。
- 真实 HTTP 验收题 `ffff37e8-4e75-5548-ad91-28af50db02d7`：难度分析 `417f99c4-b732-4433-8894-16e7a71b338d` 返回 2 级、预计正确率 `0.75`、置信度 `0.9`；质量分析 `e9f7040a-453c-44a3-b93d-baeb42225b82` 返回 `passed=true`。
- 聚焦测试覆盖等级/正确率一致性、严格问题枚举、提供方 Schema 兼容降级、分析前置标签、无效输出不落库、四类质量问题合并与分析历史持久化。

### BIO-029 多约束优化组卷里程碑

- 新增 `POST /api/paper-agent/papers/optimize`，独立于 M2 基础随机组卷接口；请求按“题型 + 1～5 级难度 + 数量 + 分值”定义精确配额，不改变旧任务和教师审核链路。
- 使用 OR-Tools CP-SAT 建立布尔选择模型：题型/难度配额、知识点最低题数与覆盖率、知识点/核心素养/来源多样性及单类上限均作为硬约束，无可行解时返回 `NO_FEASIBLE_PAPER`，不会自动放宽。
- 候选题必须同时具有有效知识点、核心素养、最新难度分析和最新质量审核；仅 `passed=true` 的质量结果可进入求解，响应保留难度/质量分析 ID 以便追溯。
- BIO-025 精确和语义重复匹配被转换为题目对互斥约束，使求解器可在重复组中选择更符合覆盖目标的题，而不是预先固定删除某一道。
- 目标函数在所有硬约束满足后优先增加知识点、核心素养和来源分散度，再考虑难度分析置信度与确定性种子破同分；求解限制为单线程 10 秒，结果可复现。
- 响应包含约束审计：覆盖率、覆盖/缺失知识点、知识点/核心素养/来源数量、质量通过数和已选重复对数量；响应契约再次拒绝未全部满足、质量未全通过或仍含重复对的结果。
- 8 项聚焦测试覆盖请求总量、重复配额、不可能多样性、最新审核、质量失败过滤、精确/语义重复互斥、无可行解和异常向量维度；4 题验收解达到 4 个知识点、4 类核心素养、2 个来源、质量通过率 100%、重复对 0。
- 真实 HTTP 使用题目 `ffff37e8-4e75-5548-ad91-28af50db02d7` 完成优化：1 题、2 级难度、覆盖率 `1.0`、质量通过数 1、重复对 0、`satisfied=true`。
- OR-Tools 放入独立 `requirements-optimization.txt` Docker 缓存层；干净 backend 镜像构建在 43 秒内成功，并已由新镜像重建服务。

### BIO-030 锁题、换题与重新组卷里程碑

- Alembic `20260812_0008` 为 `paper_jobs` 增加 `basic/optimized` 生成模式，为 `paper_job_questions` 增加持久化 `is_locked` 标记；旧任务自动保持 `basic`。
- 新增持久化优化任务 API，可创建并查询任务、批量锁定/解锁已选题、替换单题、重新组卷以及通过/驳回；优化任务复用 PostgreSQL LangGraph 教师审核中断。
- 单题替换将其余全部已选题设为必选、排除原题，并重新执行 BIO-029 的题型/难度、覆盖率、多样性、质量和重复互斥硬约束；教师也可指定候选池中的替换题。
- 重新组卷将锁定题设为必选、排除当前未锁定题后重新求解；全部题目锁定时明确拒绝，不会返回看似成功但未变化的结果。
- 新结果只有在锁题集合完整保留且完整约束审计通过后才写入；无可行替换不会放宽约束，数据库试卷和审核 checkpoint 均保持原选题。
- 每次成功修改会同步 `paper_jobs.assembly_result`、`paper_job_questions` 和教师审核 checkpoint；修改后仍停留在 `awaiting_review`，可继续调整或批准完成。
- 5 项聚焦测试覆盖锁题禁止替换、换题保留锁题与全部硬约束、重新组卷只替换未锁题、全锁拒绝、不可行指定替换不改变原选题，以及同步后继续批准。

### BIO-031 学生卷 Word 模板里程碑

- 新增版本化模板 `backend/templates/paper_agent/student_paper.docx` 和可重复构建脚本；版面为 A4 纵向，左右页边距 18 mm，并配置可自动更新的 PAGE/NUMPAGES 页脚。
- 新增 `POST /api/paper-agent/papers/student-word`；接口接收严格校验的基础组卷结果，从 PostgreSQL 恢复完整题目，从资源存储读取并校验题图，返回带 UTF-8 文件名的 DOCX 下载。
- 学生卷只输出题干、选项、小问、题图和作答空间，不输出答案与解析；题号跨大题全局连续，长选项自动改单列，选项行禁止跨页拆分，长综合题可自然跨页。
- 图片统一转为 Word 兼容 PNG，最大宽度 150 mm、最大高度 85 mm，保留替代文本；缺失、篡改或无法解码的图片会明确拒绝导出。
- 3 项专项测试和 126 项全量测试通过；真实接口使用三道含图真题生成 90,525 字节 DOCX，Microsoft Word 实际渲染为 2 页，题号、图片和分页经页面截图检查正确。

### BIO-032/033 教师卷与答题卡里程碑

- 新增版本化 `teacher_answer.docx` 和 `answer_sheet.docx`，与 BIO-031 学生卷模板共用 A4 页面、字体样式、页边距及 PAGE/NUMPAGES 页脚，并由同一脚本可重复构建。
- 新增 `POST /api/paper-agent/papers/teacher-answer-word`；批量读取题目知识点名称和最新有效难度分析，输出答案、解析、知识点编码/名称、1～5 级难度及预计正确率。
- 教师卷执行完整性门槛：主问题或小问缺答案/解析、主问题无知识点或无有效难度分析时返回冲突错误，不生成不完整文档。
- 新增 `POST /api/paper-agent/papers/answer-sheet-word`；学生卷、教师卷和答题卡共用 `ordered_assembled_questions` 作为唯一题序来源，答题卡按题型生成选择框、填空线和综合题小问作答区。
- 6 项文档专项测试和 129 项全量测试通过；两个真实 HTTP 接口均返回 DOCX，Microsoft Word 实际渲染均为 1 页 A4，教师卷四项信息完整，三题答题卡编号与 BIO-031 验收学生卷的 1～3 完全一致。

### BIO-034 DOCX/PDF 生成里程碑

- 保留 BIO-031～033 三个 DOCX 下载接口，并新增 `student-pdf`、`teacher-answer-pdf`、`answer-sheet-pdf` 三个 PDF 下载接口；六个接口均返回附件响应和 UTF-8 文件名。
- PDF 不维护第二套排版器，而是先调用对应 DOCX 服务，再由容器内 LibreOffice Writer 25.2.3.2 无界面转换；每次转换使用独立临时目录和用户配置目录，并设置 60 秒超时。
- 后端镜像安装 `libreoffice-writer`、`fontconfig` 和 `fonts-noto-cjk`，因此 PDF 生成不依赖 Windows 或本机 Microsoft Word；Docker 安装层配置下载重试并独立缓存。
- 转换完成后验证 `%PDF`/EOF、可读取页数，并提取 DOCX 与 PDF 文本；DOCX 中每个有效正文块必须出现在 PDF 中，否则拒绝下载。响应通过 `X-PDF-Page-Count` 返回页数。
- 转换专项测试覆盖真实中文 PDF 生成及故意错配拦截；全量测试 131 项通过。三类真实接口均返回 200，学生卷/教师卷/答题卡分别为 2/1/1 页，独立比对 27/12/10 个正文块，缺失数均为 0，页面截图检查无乱码、图片丢失或越界。

### BIO-035 文档渲染自动检查里程碑

- PDF 下载链路在正文一致性校验后执行强制渲染质量门；检查未通过时返回导出错误，不向教师提供缺陷文件。
- 图片检查验证 DOCX 内嵌资源可解码，并要求 PDF 图像对象数不少于 Word 图片引用数；允许转换器跨页复用图像对象，避免正常分页误报。
- 空页检查逐页排除页码页脚后判断有效文本或图像；答案泄漏检查仅作用于学生卷和答题卡，识别答案/解析标签及来自题目结构的长答案、解析片段。
- 异常断页检查拒绝孤立在页尾的章节标题、大题说明和独立题号；现有 keep-with-next、表格禁拆分与显式章节分页策略继续生效。
- PDF 响应增加 `X-Render-Check: passed`、`X-Expected-Image-Count` 和 `X-Rendered-Image-Count`，便于调用方及监控系统确认质量门结果。
- 7 个专项测试覆盖正常导出与缺图、空页、答案泄漏、异常断页故障注入；后端全量 137 个测试全部通过。
- 真实 API 验收：学生卷 2 页、预期图片 2/渲染图像对象 4；教师解析卷 1 页、0/0；答题卡 1 页、0/0。三类响应均为 200 且 `X-Render-Check=passed`，页面栅格化目视核对无缺图、空页或异常断页，学生卷与答题卡无答案标签。

### BIO-036 全链路测试和验收样卷里程碑

- 固定可重复的 MVP 蓝图：`BIO-M1 分子与细胞`、10 道单项选择题、每题 5 分、总分 50 分；难度配额为 2 级 4 道、3 级 4 道、4 级 2 道，覆盖 `BIO-M1-K01`～`BIO-M1-K07` 全部 7 个知识点。
- 全链路通过产品优化任务 API 运行，使用 PostgreSQL Checkpointer 持久化中断状态，由 `bio036-acceptance-teacher` 提交批准后恢复并完成任务；正式任务 ID 为 `595562de-bd74-4ab9-ae0b-55444e745967`，审核状态为 `approved`。
- 约束审计结果：覆盖率 100%、7 个不同知识点、2 类核心素养、10/10 质量审核通过、选中重复题对为 0，数量、分值、题型和难度配额全部严格满足。
- 同一已批准任务生成学生卷、教师答案解析卷、答题卡各 DOCX/PDF 一份；PDF 分别为 3/4/1 页，三个 PDF 的 `render_check` 均为 `passed`。目视核对确认学生卷和答题卡无答案泄漏，教师卷每题的题干、选项、答案、解析、知识点和难度保持完整题块。
- 最终产物位于 Windows `E:\Projects\FlowGate_BIO036_MVP_Acceptance\`，其中 `acceptance-report.json` 保存任务、教师审核、约束审计、文件大小和 SHA-256；容器内可通过 `PYTHONPATH=/app python /app/scripts/run_bio036_acceptance.py` 重复执行。
- 修正教师卷题块跨页及选项分页，并加强异常断页检测；同时修正旧优化测试的候选域隔离，避免数据库中新增合格题目污染测试夹具。最终后端全量 139 个测试全部通过，Alembic 无迁移漂移，Backend、PostgreSQL、Redis、Qdrant 均 healthy。
- 本验收使用可审计的 BIO-016 合成种子题与确定性验收分析（模型标记 `bio036-deterministic-acceptance-v1`），证明工程全链路可重复，不等同于真实真题教学质量或教师金标准确率认证。

### 真实题目整卷里程碑（待验收）

- 2026-08-12 盘点结论：暂不通过“真实题目能够按高中生物要求稳定组成一张合格试卷”的里程碑，不能用合成题功能测试替代真实题目验收。
- 当前 PostgreSQL 中有 100 道 BIO-016 合成题；仅 4 道文件来源结构化题，但均缺少知识点和核心素养标签，也未完成难度估计与质量审核。
- 当前唯一同时具备难度估计和质量审核的题目来自 BIO-016 合成题库；BIO-029 的真实 HTTP 验收也仅组出 1 道题，不能代表完整试卷的稳定性。
- 通过该里程碑前，必须先确定一份真实、授权且可追溯的高中生物题集和明确整卷蓝图；候选题需完成标签、难度和质量审核，并保留足够备选题用于重复组卷与换题。
- 正式验收至少应连续多次按同一蓝图组卷，逐次核对题量、总分、题型/难度配额、知识点覆盖、核心素养、来源多样性、质量通过、重复题互斥和来源追溯，并验证锁题、换题和重新组卷后仍满足全部约束。

## 5. 当前技术基线

- 后端：Python、FastAPI、SQLAlchemy、Alembic、LangGraph、langgraph-checkpoint-postgres、OR-Tools CP-SAT、psycopg、pypdf、antiword
- 前端：Next.js、React、TypeScript
- 数据服务：PostgreSQL 16、Redis 7、Qdrant
- 运行方式：Docker Compose
- 版本控制：本地分支 `flowgate`，跟踪远程 `https://github.com/ljyloves/agent-learning.git` 的 `origin/flowgate`
- Alembic 当前版本：`20260812_0008 (head)`
- 自动化测试：最近一次为 `139/139` 通过
- 2026-08-12 核查状态：Backend、PostgreSQL、Redis、Qdrant 均为 healthy；Frontend running

主要实现位置：

- `backend/app/modules/paper_agent/`
- `backend/app/modules/paper_agent/graph/state.py`
- `backend/app/modules/paper_agent/graph/contracts.py`
- `backend/app/modules/paper_agent/graph/checkpoint.py`
- `backend/app/modules/paper_agent/graph/workflow.py`
- `backend/app/modules/paper_agent/nodes/branches.py`
- `backend/app/modules/paper_agent/nodes/initialize.py`
- `backend/app/modules/paper_agent/nodes/teacher_review.py`
- `backend/app/modules/paper_agent/adapters/openstax.py`
- `backend/app/modules/paper_agent/schemas/checkpoint.py`
- `backend/app/modules/paper_agent/schemas/assembly.py`
- `backend/app/modules/paper_agent/schemas/task.py`
- `backend/app/modules/paper_agent/schemas/ingestion.py`
- `backend/app/modules/paper_agent/schemas/annotation.py`
- `backend/app/modules/paper_agent/schemas/analysis.py`
- `backend/app/modules/paper_agent/schemas/optimization.py`
- `backend/app/modules/paper_agent/schemas/optimized_task.py`
- `backend/app/modules/paper_agent/services/checkpoint.py`
- `backend/app/modules/paper_agent/services/assembly.py`
- `backend/app/modules/paper_agent/services/task.py`
- `backend/app/modules/paper_agent/services/taxonomy_annotation.py`
- `backend/app/modules/paper_agent/services/question_analysis.py`
- `backend/app/modules/paper_agent/services/optimization.py`
- `backend/app/modules/paper_agent/services/optimized_task.py`
- `backend/app/modules/paper_agent/services/file_ingestion.py`
- `backend/app/modules/paper_agent/services/web_ingestion.py`
- `backend/app/modules/paper_agent/services/document_extraction.py`
- `backend/app/modules/paper_agent/services/question_parser.py`
- `backend/app/modules/paper_agent/services/question_ingestion.py`
- `backend/app/modules/paper_agent/services/resource_storage.py`
- `backend/app/modules/paper_agent/services/retrieval.py`
- `backend/app/modules/paper_agent/services/deduplication.py`
- `backend/app/modules/paper_agent/services/webpage_question_parser.py`
- `backend/app/modules/paper_agent/schemas/retrieval.py`
- `backend/app/models/paper_agent.py`
- `backend/app/models/taxonomy.py`
- `backend/alembic/versions/20260810_0001_create_initial_schema.py`
- `backend/alembic/versions/20260810_0002_seed_biology_taxonomy.py`
- `backend/alembic/versions/20260811_0003_seed_molecular_cell_question_bank.py`
- `backend/alembic/versions/20260811_0004_add_question_difficulty.py`
- `backend/alembic/versions/20260811_0005_add_paper_job_assembly_payloads.py`
- `backend/alembic/versions/20260811_0006_allow_shared_question_resources.py`
- `backend/alembic/versions/20260811_0007_add_question_analyses.py`
- `backend/alembic/versions/20260812_0008_add_optimized_task_locks.py`
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
- `backend/tests/modules/paper_agent/test_teacher_file_upload.py`
- `backend/tests/modules/paper_agent/test_openstax_adapter.py`
- `backend/tests/modules/paper_agent/test_question_parser.py`
- `backend/tests/modules/paper_agent/test_document_extraction.py`
- `backend/tests/modules/paper_agent/test_question_resource_ingestion.py`
- `backend/tests/modules/paper_agent/test_hybrid_retrieval.py`
- `backend/tests/modules/paper_agent/test_question_deduplication.py`
- `backend/tests/modules/paper_agent/test_taxonomy_annotation.py`
- `backend/tests/modules/paper_agent/test_question_analysis.py`
- `backend/tests/modules/paper_agent/test_optimization_schema.py`
- `backend/tests/modules/paper_agent/test_paper_optimization.py`
- `backend/tests/modules/paper_agent/test_optimized_task.py`
- `backend/requirements-optimization.txt`
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
- `POST /api/paper-agent/papers/optimize`
- `POST /api/paper-agent/reviews/{thread_id}`
- `GET /api/paper-agent/reviews/{thread_id}`
- `POST /api/paper-agent/reviews/{thread_id}/actions`
- `POST /api/paper-agent/tasks`
- `GET /api/paper-agent/tasks/{job_id}`
- `POST /api/paper-agent/tasks/{job_id}/review`
- `POST /api/paper-agent/optimized-tasks`
- `GET /api/paper-agent/optimized-tasks/{job_id}`
- `PUT /api/paper-agent/optimized-tasks/{job_id}/locks`
- `POST /api/paper-agent/optimized-tasks/{job_id}/replace`
- `POST /api/paper-agent/optimized-tasks/{job_id}/reassemble`
- `POST /api/paper-agent/optimized-tasks/{job_id}/review`
- `POST /api/paper-agent/sources/files`
- `POST /api/paper-agent/sources/webpages`
- `POST /api/paper-agent/sources/resources/{resource_id}/questions`
- `GET /api/paper-agent/questions/{question_id}`
- `POST /api/paper-agent/questions/{question_id}/taxonomy-annotation`
- `POST /api/paper-agent/questions/{question_id}/difficulty-estimation`
- `POST /api/paper-agent/questions/{question_id}/quality-review`
- `GET /api/paper-agent/resources/{resource_id}/content`
- `POST /api/paper-agent/retrieval/questions/index`
- `POST /api/paper-agent/retrieval/questions/search`

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
3. `project-progress-plan.md` 仍以通用企业 Agent 路线为主，尚未完整反映已完成至 BIO-036 的实际进度，本文件暂时作为 BIO MVP 的事实来源。
4. BIO-036 已完成，后续 BIO 任务尚未由用户正式定义。继续编码前，应先确定下一任务及验收标准，不要根据旧对话擅自假设编号。
5. M2 已具备离线假题库完整闭环，M3 已完成文件/网页采集、题目抽取、候选检索、去重、严格标签标注、难度估计、基础质量审核、多约束优化组卷、持久化教师调整、学生卷/教师解析卷/答题卡 DOCX/PDF 导出及固定 MVP 全链路验收；逻辑上的下一阶段应围绕教师金标校准和评分细则拆分，但以用户确认后的任务表为准。
6. Checkpoint 当前尚未配置 TTL、归档或定期清理策略；在进入长期运行或多租户阶段前需要定义保留周期和清理责任。
7. Question 已支持难度筛选和候选去重，但仍无年级、教材版本、来源质量等检索字段；基础算法尚未支持知识点配额和跨题型动态分值。
8. BIO-019 与 BIO-030 均同步 checkpoint 和 `paper_jobs` 业务状态；BIO-030 对修改提交失败提供反向同步补偿，但两套存储仍不属于单一数据库事务，进入多实例生产环境前应增加幂等操作、故障注入测试和状态对账任务。
9. BIO-021 已完成 DOCX、可提取文本 PDF 和旧 DOC 的确定性结构解析；PDF 图片已按内容流顺序插回题目，并过滤跨页重复的页边水印，表格小数也不会再被误识别为题号。扫描 PDF、图片 OCR、复杂多栏 PDF、嵌套 Form XObject 和数学公式版式仍需专门 OCR/版面分析能力；新来源首次导入后仍需抽样核对题图语义。
10. BIO-023 当前只有 OpenStax 适配器；BIO-025 仅用确定性 HTML 解析内容。BIO-026 已在 LLM 标注服务中默认拦截 OpenStax 来源，但持续采集仍需定义授权状态、robots 检查、请求频率、缓存和失败重试策略。
11. BIO-024 的 Qdrant 题目索引是 PostgreSQL 的可重建派生数据，目前通过显式索引 API 同步；新增、修改或删除题目后需要触发增量/全量重建，后续应接入事务外盒或异步索引任务并监控索引滞后。
12. 混合检索默认权重和 RRF 常数已通过功能测试但尚未用教师标注集做 Recall@K、MRR、nDCG 评估；Embedding 模型或维度变更时必须创建新集合并重建索引，不能直接复用旧向量。
13. BIO-025 的 `0.94` 语义阈值通过确定性功能样本验证，尚未用真实教师重复标注集校准误杀率和漏检率；上线前应报告 Precision、Recall、F1，并按题型或语言分层调参。
14. BIO-026 已验证结构和标签集合严格性，但尚未用教师金标数据评估标注准确率；上线前需建立分层评测集，报告知识点与核心素养的 micro/macro Precision、Recall、F1，并设置低置信度人工复核阈值。
15. BIO-027 的难度等级和预计正确率当前是模型估计，不等同于真实作答统计；上线前需用分年级、知识点和题型的学生作答数据做校准，报告 MAE、RMSE、等级一致率及置信区间。
16. BIO-028 的歧义和超纲判断仍依赖模型；上线前需由高中生物教师建立四类问题金标集，报告各类别 Precision、Recall、F1，并对低置信度及冲突结果保留人工复核。
17. BIO-029 默认只允许已经完成标签、难度估计和质量审核的题目进入候选池；批量正式组卷前需增加分析队列、状态统计和失败重试，避免可用题库因分析缺失而被误判为无可行解。
18. BIO-029 当前在模块内加载合格候选并执行两两语义去重，规模较大时重复检测为 O(n²)；进入万题级题库前应先用检索条件/向量近邻缩小候选池，并监控候选数、Embedding 耗时、求解状态与 10 秒超时率。
19. BIO-030 在任务创建时冻结最多 1000 道合格候选 ID，保证后续调整可复现；任务创建后新入库或新完成分析的题不会自动进入该任务候选池，未来若需要动态扩池应增加显式刷新动作和审计记录。
20. BIO-031～033 当前提供学生卷、教师答案解析卷和答题卡 DOCX；评分细则、双栏密排和直接 PDF 导出仍需作为独立任务设计。历史测试资源中存在无法解码的伪图片，导出器会拒绝这类数据，正式题库应增加资源健康巡检。
21. BIO-032 将“知识点和难度完整”定义为主问题至少一个有效知识点、最新有效 1～5 级难度分析，以及主问题或全部小问均有答案和解析；对历史真实题库中只含参考答案但无解析的题，需先补齐解析后才能导出教师卷。
22. BIO-034 的 LibreOffice 与 Noto CJK 系统层会增加后端镜像体积和首次构建耗时；生产环境应监控转换耗时、并发数和临时磁盘，并在高并发阶段将转换任务迁移到独立 worker 队列。
23. BIO-035 的自动检查针对可提取文本和常规嵌入图片，不能替代人工审美、公式重排或像素级版面比较；进入生产前应增加带数学公式、复杂表格、扫描图和极端长题的回归样本，并记录质量门失败指标。
24. BIO-036 的固定 MVP 基线使用 BIO-016 合成题和确定性分析，适合持续集成和工程回归，但不能替代授权真题、多来源候选、教师金标质量审核或真实学生作答难度校准；进入教学试用前仍需另行完成这些验收。

## 8. 真实真题组卷验收（2026-08-12）

- 来源：2022 年广东省普通高中学业水平选择性考试生物学试题，中国教育在线公开 PDF。
- 本地原文件：`E:\Projects\2022-guangdong-gaokao-biology.pdf`，SHA-256 为 `7669C39F156310FE8E7C1E9A8DE9B3401CE6163BAD16F6DBB377438437C0F2A7`。
- 修正版来源 ID：`05b14f25-85ca-408c-abf2-df296d8922e9`；资源 ID：`1190b6cf-52d2-4c37-912b-19e8f8d885fd`。
- 正式导入得到 22 道主问题、13 个有效图片资源；前 16 道均恢复 4 个选项和参考答案，后 6 道小问数为 `3/3/3/4/4/4` 且答案完整。
- 图片人工核对确认原卷第 4、6、8、11、12、14、15、16 题分别关联图 1～8，重复水印没有入库；综合题图片也按内容流位置关联。
- 选择原卷第 4、7、8、9、10 题组成 5 题、25 分的“分子与细胞”诊断卷。5 题均完成标签、难度和质量审核；覆盖 `BIO-M1-K02/K05/K06` 与 `BIO-C1/C2/C3`，难度为 2 级 4 题、3 级 1 题。
- 随机种子 `202208/202209/202210` 三轮优化均满足：覆盖率 100%、质量通过 5/5、重复对 0、来源数 1；验收时显式排除了 125 道其他来源题。
- 正式持久化任务 ID：`eb9cb094-f439-4074-b4ec-e3644eab122c`，状态 `completed`，审核状态 `approved`。
- 验收样卷：`E:\Projects\FlowGate_2022广东生物真题_分子与细胞验收样卷.pdf`；该 PDF 由外部验收脚本生成，不代表产品内 Word/PDF 导出功能已经完成。
- 本轮修复了 DeepSeek 不支持 `response_format=json_schema` 时的提示词 JSON 降级、PDF 题图内容流定位、重复水印过滤、表格小数误判题号和动态真实语料下的检索测试脆弱断言。
- 结论只覆盖 5 题单元诊断卷，不等同于 100 分综合卷，也未验证多来源候选、真实替换余量和教师金标准确率。若要确认“完整真实试卷稳定组卷”，仍需扩充合法真题池并完成至少 30～50 题蓝图及换题压力测试。
- 首次错误图片导入来源 `be6f1f78-7a94-4263-b44c-32ef0a1ab68f` 及验收任务 `dbbe2e16-0e0b-4fdf-ab77-2d9266c41844`、`4d8a9a58-7d01-4762-8778-95798399b69c` 尚未删除；它们已被修正版取代，必须在获得明确删除授权后清理。

## 9. 推荐的跨账号持续方案

推荐优先级：

1. FlowGate 已初始化为 Git 仓库，并使用远程 `agent-learning` 的独立 `flowgate` 分支保存基线。
2. 每完成一个 BIO 任务，更新本文件和任务表，再创建一个小而明确的 Git 提交。
3. 在仓库根目录保留 `AGENTS.md`，记录长期不变的运行、测试、编码和安全约束；本文件只记录会变化的进度。
4. 数据库中的重要验收数据应配套可重复执行的 seed 或测试，不把本地 Docker volume 当作唯一副本。
5. 新账号打开同一 WSL 项目后，让 Codex先读取本文件、`AGENTS.md`、迁移目录和最近 Git 提交，再开始下一任务。

## 10. 新账号首条提示词

```text
请接手 /home/lijinyang/FlowGate 项目。先阅读仓库根目录的
FlowGate_PROJECT_HANDOFF.md、project-progress-plan.md、AGENTS.md（若存在），
然后检查 git status、docker compose ps、Alembic current/check 和自动化测试。
不要修改或删除现有成果，不要读取或输出 .env 中的密钥。
先向我汇报实际状态与交接文档是否一致，再继续执行我指定的下一个 BIO 任务。
```

## 11. 交接完成标准

新的 Codex 会话无需访问旧聊天记录，也能从仓库文件恢复以下信息：项目目标、已完成任务、数据库版本、验收样例、运行命令、已知风险和下一步决策点。
