# 项目文档与开发计划导航

- [仓库首页](../../README.md) 和 [复现说明](../../docs/reproducibility/demo_v1_delivery.md) 提供 clone 后在 PowerShell 或 Ubuntu WSL 中启动演示的命令。

真实目录：[`docs/`](../../docs/) 和 [`plans/`](../../plans/)

## 当前权威文档

| 文件 | 作用 | 权威范围 |
|---|---|---|
| [`docs/PROJECT_LOG.md`](../../docs/PROJECT_LOG.md) | 最新进展、决策、下一步和阻塞项 | 当前状态第一来源 |
| [`docs/PROJECT_PLAN.md`](../../docs/PROJECT_PLAN.md) | 科学使命、目标结构、依赖和里程碑 | 长期范围与路线 |
| [`docs/algorithm_structure_grouping.md`](../../docs/algorithm_structure_grouping.md) | 组成模板与 robocrys 环境匹配算法 | grouping/envmatch 科学说明 |
| [`docs/algorithm_gap_backfill_pairing.md`](../../docs/algorithm_gap_backfill_pairing.md) | gap 来源、回填、压缩和 pair 判据 | pairing 科学说明 |
| [`docs/algorithm_competing_phase_hull.md`](../../docs/algorithm_competing_phase_hull.md) | MP 结构来源、统一 MLP 能量、凸包量和失败语义 | Stage 10 科学与文件契约 |
| [`docs/algorithm_recommendation.md`](../../docs/algorithm_recommendation.md) | 推荐单元、L2--L6、三类判定、排序和输入输出 | Stage 11 科学与文件契约 |
| [`docs/web_platform_development_guide.md`](../../docs/web_platform_development_guide.md) | React/FastAPI 多用户 Web 平台的架构、状态机、API、页面、任务、存储、安全、测试和分阶段实施 | Phase 1、Stage 1 MP/WBM 与 Stage 1a composition 已接入 |
| [`docs/web_platform_implementation_handoff.md`](../../docs/web_platform_implementation_handoff.md) | Phase 0/1 实施指令、schema、API、ArtifactStore、安全和验收清单 | 当前 Web 控制层实现的交付范围 |
| [`docs/gui_integration_notes.md`](../../docs/gui_integration_notes.md) | 可选 PySide6 桌面 GUI 的集成边界、保留的界面流程思路和后续串通 CLI 的原则 | GUI 必须调用真实 CLI，不替换科学实现 |
| [`docs/cli_front_mid_smoke_2026-09-10.md`](../../docs/cli_front_mid_smoke_2026-09-10.md) | WSL 中 CLI 前中段流程验证交接单，列出已跑通阶段、测试产物、操作流水和需同事提供的真实数据/模型/结果 | GUI 串接 CLI 前的后台流程核对材料 |
| [`docs/current_capability_and_handoff_2026-09-12.md`](../../docs/current_capability_and_handoff_2026-09-12.md) | 当前 GUI/CLI/WSL/POSCAR/PyTorch 能力、已测方法和需同事提供材料的对外交接清单 | 面向同事沟通当前软件能力与缺口 |
| [`docs/gui_wsl_poscar_demo_runbook_2026-09-12.md`](../../docs/gui_wsl_poscar_demo_runbook_2026-09-12.md) | Windows GUI 调 WSL 后端、导入 POSCAR 文件夹、导出 VASP gap 任务的现场演示步骤、字段选择和汇报话术 | 面向同事现场演示与下一步交接 |
| [`docs/real_vasp_mace_pipeline_2026-09-14.md`](../../docs/real_vasp_mace_pipeline_2026-09-14.md) | 使用同事 PBE VASP 结果和 `mace-mpa-0-medium.model` 跑通真实 gap 校验、pair、SQS、MACE relaxation、混合焓、phonon 和推荐报告的验证记录 | 当前真实数据链路能力和剩余阻塞 |
| [`docs/gui_full_pipeline_runbook_2026-09-14.md`](../../docs/gui_full_pipeline_runbook_2026-09-14.md) | 按 GUI 左侧流程逐步运行 CaS/CaSe/CaTe 真实 VASP + MACE + MP API 演示的具体点击顺序和默认参数说明 | 面向现场完整 GUI 演示 |
| [`docs/adr/`](../../docs/adr/) | Web/核心边界、元数据/制品分工、状态机、身份、Stage 1 数据源与 Stage 1a Artifact 输入决策 | 已接受架构决策 |
| [`docs/software_status_report_2026-08-04.md`](../../docs/software_status_report_2026-08-04.md) | 面向导师汇报的软件定位、完成度、教学证据、限制、下一步和决策问题 | 2026-08-04 阶段性软件汇报材料 |
| [`docs/review_upstream_completeness_2026-07-19.md`](../../docs/review_upstream_completeness_2026-07-19.md) | 逐研究家族比较已迁移/缺失能力 | 完整性与优先级审计 |
| [`docs/user-guide/SS-Screen_完整功能版_用户使用手册.md`](../../docs/user-guide/SS-Screen_完整功能版_用户使用手册.md) | 完整功能版中文用户手册的可维护内容源稿 | 手册内容权威来源 |
| [`docs/user-guide/SS-Screen_完整功能版_用户使用手册.docx`](../../docs/user-guide/SS-Screen_完整功能版_用户使用手册.docx) | 经结构审计和逐页复检的正式 Word 手册 | 面向用户的正式交付物 |
| [`docs/user-guide/SS-Screen_V0.1.0_软件著作权登记操作手册.md`](../../docs/user-guide/SS-Screen_V0.1.0_软件著作权登记操作手册.md) | 与 `ss-screen 0.1.0` 真实 CLI 冻结一致的登记版内容源稿 | 软著登记文档内容权威来源 |
| [`docs/user-guide/SS-Screen_V0.1.0_软件著作权登记操作手册.docx`](../../docs/user-guide/SS-Screen_V0.1.0_软件著作权登记操作手册.docx) | 可编辑的软著登记版 Word 手册 | 著作权人信息修订与归档 |
| [`docs/user-guide/SS-Screen_V0.1.0_软件著作权登记操作手册.pdf`](../../docs/user-guide/SS-Screen_V0.1.0_软件著作权登记操作手册.pdf) | 36 个物理页的 A4 纵向排版，封面后从逻辑第 1 页连续编号 | 待替换著作权人后的软著文档鉴别材料 |
| [`docs/user-guide/SS-Screen_V1.0_软件著作权登记操作手册.md`](../../docs/user-guide/SS-Screen_V1.0_软件著作权登记操作手册.md) | 包含操作截图、软件结构、接口、流程、数据字典和运行设计的 V1.0 内容源稿 | V1.0 软著操作手册内容权威来源 |
| [`docs/user-guide/SS-Screen_V1.0_软件著作权登记操作手册.docx`](../../docs/user-guide/SS-Screen_V1.0_软件著作权登记操作手册.docx) | 第六至十七章按输入、操作、数据变化、验收和交接组织，含37处内嵌操作/设计/流程/结果图的可编辑 Word 手册 | V1.0 正式 Word 交付物 |
| [`docs/user-guide/SS-Screen_V1.0_软件著作权登记操作手册.pdf`](../../docs/user-guide/SS-Screen_V1.0_软件著作权登记操作手册.pdf) | 65 个物理页的 A4 图文版鉴别材料 | 逐页检查与提交参考 |
| [`docs/copyright-source/README.md`](../../docs/copyright-source/README.md) | 源程序鉴别材料的生成范围、排序规则、交付文件和复现入口 | V0.1.0 源程序交付说明 |
| [`docs/copyright-source/SS-Screen_V0.1.0_source_front2500_back2500.pdf`](../../docs/copyright-source/SS-Screen_V0.1.0_source_front2500_back2500.pdf) | 正式 Python 包前后各 2500 行，每页 50 行，共 100 页 | 软著源程序鉴别材料 |
| [`docs/copyright-source/SS-Screen_V0.1.0_source_front2500_back2500_unlabeled.docx`](../../docs/copyright-source/SS-Screen_V0.1.0_source_front2500_back2500_unlabeled.docx) | 与 PDF 相同选段的 Word 版本，正文不含编号、原行号或路径前缀 | 可编辑软著源程序材料 |
| [`docs/copyright-application/计算机软件著作权登记申请表_主要功能扩写.docx`](../../docs/copyright-application/计算机软件著作权登记申请表_主要功能扩写.docx) | 基于用户提供申请表扩写主要功能栏，其他申请字段保持原样 | 软著申请表工作副本 |

## 设计与实施记录

| 目录/文件 | 内容 |
|---|---|
| [`docs/superpowers/specs/`](../../docs/superpowers/specs/) | CLI 教程、历史资料整理和 ZMD 的批准设计 |
| [`docs/superpowers/specs/2026-07-22-full-user-manual-design.md`](../../docs/superpowers/specs/2026-07-22-full-user-manual-design.md) | 面向材料科研用户的未来完整功能版中文手册设计、预期 CLI 和验收边界 |
| [`docs/superpowers/plans/`](../../docs/superpowers/plans/) | condensation archive、资料整理和 ZMD 的实施计划 |
| [`docs/superpowers/plans/2026-07-22-full-user-manual.md`](../../docs/superpowers/plans/2026-07-22-full-user-manual.md) | Markdown、Word 构建、审计、渲染与 ZMD 同步的实施步骤 |
| [`plans/2026-07-11-cli-first-implementation-v1.md`](../../plans/2026-07-11-cli-first-implementation-v1.md) | 第一版 CLI-first 实施计划 |
| [`plans/2026-07-11-next-task-breakdown-v1.md`](../../plans/2026-07-11-next-task-breakdown-v1.md) | 早期下一步拆解 |
| [`plans/2026-07-12-cli-long-term-screening-roadmap-v1.md`](../../plans/2026-07-12-cli-long-term-screening-roadmap-v1.md) | 长期分阶段筛选路线 |

## 阅读和冲突处理

1. 判断当前进度先读 `PROJECT_LOG.md`。
2. 判断是否在范围内再读 `PROJECT_PLAN.md`。
3. 修改科学算法前读对应 algorithm 文档和 `references/` 来源。
4. 旧计划与当前实现冲突时，以日志、当前代码和测试为准，并记录冲突。
5. 计划中的文件不等于已经实现；必须回到真实目录核实。

## 当前明确缺口

- 历史三元 `Compositions` 字段兼容。
- 可选 PBE fallback。
- 原始 WBM step 数据到 extxyz 的完整构建。
- Stage 1 完整数据不随仓库分发；外部 MP 离线快照已接入并验证，WBM 仍需另行提供经验证的 extxyz。
- WBM Web/核心已拒绝缺失或无效 gap/hull 并校验 summary 行数/ID；正式全量运行仍缺原始 step-to-extxyz provenance。
- 外部高精度带隙计算本身（已明确不在本包实现）；缺陷计算执行后端仍待设计。
- 缺陷计算/排序，以及 MatterSim/eSEN/TorchSim 批处理 MLP 后端。
- Stage 11 默认阈值仍需使用更多真实体系校准；当前结果是决策支持，不是稳定性或可合成性证明。

## 最近同步

- 2026-09-07：新增 `docs/gui_integration_notes.md`，记录同事 GUI 评审包中保留的阶段化工作台思路，
  并明确 GUI 作为可选前端调用真实 CLI。
- 2026-09-10：新增 `docs/cli_front_mid_smoke_2026-09-10.md`，整理 WSL CLI 前中段流程验证、
  产物目录、命令流水和需同事提供的真实数据/模型/外部结果。
- 2026-09-12：新增 `docs/current_capability_and_handoff_2026-09-12.md`，汇总当前 GUI/CLI/WSL/POSCAR
  与 PyTorch/MACE/phonopy 环境能力、已测方法和需同事提供的真实材料。
- 2026-09-12：新增 `docs/gui_wsl_poscar_demo_runbook_2026-09-12.md`，整理 GUI 现场演示顺序、
  每一步字段选择、CLI 备用命令和面向同事的汇报建议。
- 2026-09-14：新增 `docs/real_vasp_mace_pipeline_2026-09-14.md`，记录真实 PBE VASP gap、
  MACE relaxation、混合焓、phonon 和 recommendation 结果，以及缺 `mp_offline` 的 phase 阻塞。
- 2026-09-14：更新 `docs/real_vasp_mace_pipeline_2026-09-14.md`，补充 `data/API Key.txt`
  已验证可用于当前项目在线 Materials Project 后端；Stage 11 仍未补跑，离线 `mp_offline` 数据库仍缺。
- 2026-09-14：新增 `docs/gui_full_pipeline_runbook_2026-09-14.md`，并将 GUI 默认参数调整到
  CaS/CaSe/CaTe 真实 VASP + MACE + MP API 演示链路。
- 2026-09-15：更新 `docs/real_vasp_mace_pipeline_2026-09-14.md` 和
  `docs/gui_full_pipeline_runbook_2026-09-14.md`，记录 MP API Stage 11 竞争相凸包已补跑成功：
  25 个竞争相、hull distance `0.3497941494 eV/atom`、`hull_signal=unstable`。
- 2026-09-02：项目日志登记当前完整工作树以提交 `33f9cc3` 发布到新远程 `master`；远程 `main`
  保持在原基线，科学路线与下一步 Stage 3 structure-match 不变。
- 2026-09-02：远程前端保持运行；定位本地页面`Failed to fetch`为远程API进程退出，改用脱离交互
  会话的后台API与control/cpu Worker；ready六项和项目API正常，浏览器继续通过5173/8000转发访问。
- 2026-09-01：Web开发指南和项目计划登记Stage 2 condensation完成：双Artifact输入、分批检查点、
  逐材料失败、取消检查、显式重试续跑、进度/失败预览和五类不可变制品；下一步转入Stage 3
  structure-match。
- 2026-09-01：Web开发指南和项目计划登记Stage 1a Run冻结参数摘要、同项目鉴权的有界候选预览，
  并明确完整CSV仍是权威制品；下一步转入Stage 2 condensation批处理/失败分片契约。
- 2026-09-01：新增ADR-0007；Stage 1a composition冻结Dataset Artifact身份/阈值，输出候选CSV与
  provenance而不重复登记Dataset，Stage 2可继续按Artifact ID/SHA消费。
- 2026-09-01：新增 ADR-0006并完成WBM隔离上传垂直切片：流式限额、二次SHA、严格schema/
  summary对齐、原始与规范制品、脱敏provenance、Dataset登记及前端审计页面。
- 2026-09-01：ADR-0005和Web开发指南补充科学核心身份门禁：Run冻结版本、部署修订与实际源码SHA，
  ready/启动/Worker三处检查，历史不可变Dataset不回写。
- 2026-09-01：首个真实 Web Stage 1 MP 离线任务完成，生成46,675行、430,317,793字节 DataFrame
  和脱敏 provenance；项目日志登记 Run/Dataset/Artifact 身份、SHA 及 editable distribution metadata
  仍为0.1.0而源码为1.0的环境漂移，后续运行前需校正。
- 2026-09-01：Phase 2 首个 `stage-1-mp-offline-v1` 已实现；开发指南、项目计划和 ADR-0005
  同步服务端只读快照、核心 loader、双制品/Dataset、CPU 队列与路径脱敏边界。WBM/上传、
  Stage 1a--5 和完整 MVP 出口条件仍未完成。
- 2026-09-01：按用户请求启动已验收的 Web Phase 1 本地服务；网页、API 文档与包含数据库、Redis、
  三个外部存储根的 ready 检查均正常。仅记录运行状态，不改变 StageRunner 路线。
- 2026-08-31：Phase 1 交付按实施 handoff 完成加固验收；ADR 同步不可覆盖的原子 Artifact 发布、
  三目录 ready 写探针、Attempt 绑定投递、停滞 outbox 重投和 `worker.lost` 恢复语义。StageRunner
  仍未接入，路线未扩展。
- 2026-08-28：第15.3节现场演示改用在线 MP API，完整 BASH 块实际生成45,624条数据、4,408条候选和343个模板；421.9 MB运行数据与截图保留在被忽略的 `work/`，不纳入正式资产导航。
- 2026-08-28：按 V1.0 手册第15.2节执行原始 Bash；在被 Git 忽略的本地演示目录创建14个工作目录并进入 `screening-run`，随后按完整 BASH 代码块连续确认 Python 3.11.15、SS-Screen 1.0 和169行依赖快照；后续截图单位固定为 DOCX 中的完整 BASH 代码块，运行产物不纳入正式资产导航。
- 2026-08-27：Phase 1 控制层垂直切片已实现，Web 指南不再是“仅设计”；Stage 1--11 StageRunner 仍未接入。
- 2026-08-26：新增方案二 Web 平台开发指南，固定 React/TypeScript + FastAPI + PostgreSQL + Redis/Celery 架构、`Project/Run/Task/Attempt/Artifact/Event` 控制层、Stage 1--5 MVP、Stage 6--11 Worker 接入和生产化门禁；`PROJECT_PLAN.md` 登记为正式扩展路线，当前没有实现 Web 运行时。
- 2026-08-24：第7章增加 gap-export 输入检查、VASP任务导出、结构/任务检查和结果/方法模板检查四张连续真实操作图。
- 2026-08-24：V1.0 手册第六至十七章增加连续操作、数据变化、阶段验收与下一章交接，第十五章形成端到端台账，第十六、十七章补充反向审计和故障复验图文流程。
- 2026-08-24：V1.0 软著手册的启动界面改为真实 `ss-screen --version` ASCII Logo 输出，并同步重建 DOCX/PDF。
- 2026-08-21：V1.0 软著手册新增 8 张环境、数据、condense、MACE、混合焓、声子、凸包和完整验收界面，主要任务章节现均有对应操作图。
- 2026-08-18：V1.0 软著操作手册整合 24 张真实 CLI 截图、结构/接口/逻辑图和分阶段流程图，补充模块函数、算法、数据字典和运行设计。
- 2026-08-18：新增源程序前后各 2500 行的无前置标号 Word 版本，正文 5000 段并按每 50 行强制分页。
- 2026-08-18：将软著申请表“主要功能”扩写为 1281 个非空白字符，覆盖当前 Stage 1--11，并保留外部高精度计算与科研决策支持边界。
- 2026-08-05：生成 V0.1.0 正式包前后各 2500 行的源程序 PDF、可检索文本和 SHA-256 清单；范围只含 `src/ssscreen/**/*.py`。
- 2026-08-05：软著登记版第一章新增“1.1 研发背景”，说明带隙的材料设计价值、窄带隙与光伏型红外探测波段的关系、固溶体调控路径及软件研发必要性；第一章旧小节顺延为 1.2--1.7。
- 2026-08-04：软著登记版 Markdown/DOCX/PDF 的软件全称统一更新为“新材料计算筛选软件”；简称 `SS-Screen`、Python 包 `ss-screen` 和版本 `V0.1.0` 不变。
- 2026-08-04：新增 `V0.1.0` 软件著作权登记操作手册 Markdown/DOCX/PDF；只收录当前 Stage 1--11 真实命令与文件契约，不混入完整功能版的未实现接口。
- 2026-08-03：Stage 12 路线图基线完成；新增 Stage 1--11 统一 CPU CI 夹具，项目计划和导师汇报同步测试范围、昂贵引擎替身边界与 158 项测试状态。
- 2026-08-03：导师汇报补充 Stage 11 判定规则、L2--L6、默认阈值、Stage 5 到推荐器的数据流、教学自动分类和可现场复现的轻量 Bash 命令；校正算法文档数量与开发工作树范围。
- 2026-08-03：新增 Stage 11 推荐算法说明；项目计划、长期路线、中文手册 V1.4 和导师汇报同步为 Stage 1--11 当前能力。
- 2026-08-03：更新面向 2026-08-04 导师汇报的阶段性软件报告，汇总 Stage 1–11、教学演练、科学边界、目标带隙产品方向、Stage 12、缺陷和工作流成熟度，并给出 Bash 现场演示顺序。
- 2026-08-03：形成目标带隙与用户数据双入口产品设计；检索范围覆盖 MP×MP、用户×MP、用户×用户，结果区分端元覆盖、组分预测和显式计算验证三级证据。建议先建设 MP 预计算索引、通用上传 schema 和 `target_gap/tolerance` MVP，尚未形成正式计划变更。
- 2026-08-03：完成被 Git 忽略的 `work/new-user-tutorial/` Stage 1 至 Stage 10 新用户教学运行；`docs/PROJECT_LOG.md` 记录结果、科学边界和正式运行清单。本地产物及审计报告属于生成文件，不纳入 ZMD 正式资产导航。
- 2026-08-03：完成材料科学与通用开源工作流框架调研；建议保留当前科学内核和版本化文件契约，新增 Run/Task/Artifact 控制层、工作流 IR、执行适配器及元数据/制品存储，并以 Stage 1–5 可恢复垂直切片验证 jobflow 风格集成。该建议尚未形成正式计划变更。
- 2026-08-03：接入并只读审计外部 MP SQLite 快照；同步 Stage 1 deprecated 过滤、最小字段投影、数据库 SHA/query provenance 和手册 V1.3 文件契约。
- 2026-08-03：只读核查外部 `pairwise-screening/wbm-dataset`；其只有 60,225 个稀疏且缺少 gap/hull/step 元数据的结构 JSON，未包含 extxyz、summary、五个原始 step 或规范化 DataFrame，不能作为当前 Stage 1 WBM 入口。其历史 binary group JSON 可作为后续 pair 阶段复现产物，不等于 WBM 源数据。
- 2026-08-03：审查 Stage 1 MP/WBM 数据准备度；确认读取器、可选依赖与聚焦测试可用，但当前可见工作区未包含 MP 数据库或 WBM extxyz/原始数据，并登记 WBM 原始对齐与严格 schema/provenance 校验缺口。
- 2026-08-03：基于当前 24 个正式源码文件、CLI 命令树和 Stage 1–10 文件契约生成 Codex 会话内逻辑画布；确认组成筛选与 robocrys 描述在 Stage 3 汇合，Stage 8/9/10 从 Stage 7 并行分叉。画布不作为仓库正式资产，项目范围和实现状态未变化。
- 2026-08-01：Stage 10 增加离线 MP 快照来源，记录数据库 SHA、快照完整性边界并同步算法说明、计划、路线图和手册。
- 2026-07-31：固定高精度带隙的外部执行边界，完成版本化任务/结果契约，并同步算法说明、计划、路线图和中文手册。
- 2026-07-31：Stage 10 竞争相与凸包从计划接口转为当前能力；新增算法说明并同步 README、计划、路线图和中文手册。
- 2026-07-31：Stage 9 声子谱从计划接口转为当前能力；同步 README、项目计划、长期路线图和中文手册。
- 2026-07-30：完成指定声子谱教程、参考工程 Phonopy 4.3/VASP 实例和官方 4.4 API 调研；确定 Stage 9 采用 Phonopy 有限位移 + MACE 力、后端中立 manifest 和 mesh 稳定性判据。
- 2026-07-30：Stage 8 混合焓从计划接口转为当前能力；同步 README、项目计划、长期路线图和中文手册。
- 2026-07-30：完成稳定性计算路径审计；后续据此实现混合焓，竞争相凸包和声子判据仍属后续阶段。
- 2026-07-30：Stage 7 MACE 弛豫从预期接口转为当前能力；同步计划、路线图、README 和中文手册源稿。
- 2026-07-22：交付完整功能版中文用户手册 Markdown 权威源稿和 46 页正式 Word 文档，并登记设计与实施计划。
- 2026-07-22：根据当前 docs、plans 和完整性审计建立初始索引。
