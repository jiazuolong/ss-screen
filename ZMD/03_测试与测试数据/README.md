# 测试与测试数据导航

- 2026-11-14：[启动器回归](../../tests/test_start_10um.py) 验证解释器复用、损坏环境保留、错误版本/策略拦截及下载前失败；通过 WSL 调用 [PowerShell 合约](../../tests/test_windows_python.ps1)，覆盖无 Python 自动准备、显式选择失败、下载复用/中断/校验失败、错误签名和非自有目录保护。不访问网络或运行科学计算。

真实目录：[`tests/`](../../tests/)、[`web/backend/tests/`](../../web/backend/tests/) 和 [`web/frontend/tests/`](../../web/frontend/tests/)

当前有 23 个 Python 测试文件（含 `conftest.py`）；参数化展开后完整测试为 174 项。
Web 基线另有 54 项后端 pytest、1 项 Vitest 和 20 项 Playwright 四宽度测试。

## 测试文件映射

| 文件 | 主要覆盖对象 |
|---|---|
| [`conftest.py`](../../tests/conftest.py) | CeSe2 condensed fixture 等共享夹具 |
| [`test_cli.py`](../../tests/test_cli.py) | 所有分阶段 CLI 的参数、调用和文件输出合约 |
| [`test_condense_archive.py`](../../tests/test_condense_archive.py) | 原子写入、skip/resume、失败记录、index 和 archive validation |
| [`test_data_mp.py`](../../tests/test_data_mp.py) | MP 文档标准化、真实 SQLAlchemy Row 解包、offline deprecated/字段投影/SHA provenance、API 凭据发现、默认超时和失败页重试 |
| [`test_data_wbm.py`](../../tests/test_data_wbm.py) | WBM extxyz 规范化及严格 gap/hull、行数与 ID 对齐校验 |
| [`test_envmatch.py`](../../tests/test_envmatch.py) | `X` 替换、环境提取、分组和 StructureGroup 序列化 |
| [`test_filters.py`](../../tests/test_filters.py) | 元素排除、gap 多样性、大小和价态过滤 |
| [`test_grouping.py`](../../tests/test_grouping.py) | 二元/三元组成模板和 PBE gap 附加 |
| [`test_structure_match.py`](../../tests/test_structure_match.py) | 候选结构匹配和缺失/损坏描述报告 |
| [`test_gap_export.py`](../../tests/test_gap_export.py) | 确定性任务身份、JSON/CIF/POSCAR 结构、结果/方法模板、原子数门槛和严格 gap 校验/审计 |
| [`test_gap_collect_vasp.py`](../../tests/test_gap_collect_vasp.py) | VASP批量四状态、missing结果行、方法哈希、目录审计、单任务筛选、未知任务拒绝和pymatgen解析字段 |
| [`test_gap_feedback.py`](../../tests/test_gap_feedback.py) | gap 覆盖、未知 directness、重复拒绝、配对和方法比较 |
| [`test_pairing.py`](../../tests/test_pairing.py) | group/pair gap 判据、自配对排除和输出 schema |
| [`test_stability_sqs.py`](../../tests/test_stability_sqs.py) | random/icet SQS、跳过记录、实际 fraction 及非活性子晶格基线校验 |
| [`test_stability_relax.py`](../../tests/test_stability_relax.py) | 端元去重、完整 E/F/stress、状态、续跑指纹、失败和旧 manifest fallback |
| [`test_stability_thermodynamics.py`](../../tests/test_stability_thermodynamics.py) | 混合焓公式、实际组分优先级、旧记录回退、跨设备兼容、来源完整性和不可用端元状态 |
| [`test_stability_phonon.py`](../../tests/test_stability_phonon.py) | 自动超胞、位移/力/收集端到端、MACE 能量、续算、模型冲突和虚频阈值 |
| [`test_stability_competing.py`](../../tests/test_stability_competing.py) | API key 不落盘、离线子体系查询/快照 SHA、MP 查询失败、竞争相 provenance、凸包负裕量和不完整竞争集拒算 |
| [`test_stability_recommendation.py`](../../tests/test_stability_recommendation.py) | 完整/缺失证据分类、L2--L6、模型 SHA 冲突、可选/强制缺陷和阈值校验 |
| [`test_e2e_pipeline.py`](../../tests/test_e2e_pipeline.py) | Stage 1--11 轻量 CLI 文件链、跨阶段 ID/schema、确定性替身和双运行复现 |
| [`test_reference_curation.py`](../../tests/test_reference_curation.py) | 历史资料发现、脱敏、别名、manifest 和 tamper 检测 |
| [`test_project_config.py`](../../tests/test_project_config.py) | 开发依赖和 CI 配置约束 |
| [`test_gui_project_file.py`](../../tests/test_gui_project_file.py) | `.ssproject` 01--12 打包回读、元数据保持和 SHA-256 篡改检测 |
| [`test_gui_appearance.py`](../../tests/test_gui_appearance.py) | 6 项可选 Qt 测试：字号持久化/恢复、小窗口溢出、表格尺寸、后创建页面与无效设置 |

## Web 测试映射

| 文件 | 主要覆盖对象 |
|---|---|
| [`web/backend/tests/unit/test_mp_dataset_stage.py`](../../web/backend/tests/unit/test_mp_dataset_stage.py) | MP StageRunner 输出、脱敏 provenance、空数据拒绝 |
| [`web/backend/tests/unit/test_condensation_stage.py`](../../web/backend/tests/unit/test_condensation_stage.py) | Stage 2 分批、缺失材料失败、归档布局、逻辑路径与五类输出契约 |
| [`web/backend/tests/unit/test_artifacts.py`](../../web/backend/tests/unit/test_artifacts.py) | 路径安全、原子不覆盖、并发写入、上传大小限制和流式发布 |
| [`web/backend/tests/unit/test_settings.py`](../../web/backend/tests/unit/test_settings.py) | production 存储/MP 快照必须位于工作树外 |
| [`web/backend/tests/unit/test_scientific_runtime.py`](../../web/backend/tests/unit/test_scientific_runtime.py) | 核心版本一致性、源码 SHA 和 Run 后身份变化拒绝 |
| [`web/backend/tests/integration/test_control_plane.py`](../../web/backend/tests/integration/test_control_plane.py) | 状态机、权限、outbox、demo、MP/WBM Dataset、composition、condensation 检查点续跑/五制品、隔离上传与失联恢复 |
| [`web/frontend/tests/e2e/control-plane.spec.ts`](../../web/frontend/tests/e2e/control-plane.spec.ts) | 四宽度 demo 主链、Stage 1 草稿、Stage 1a 候选预览、Stage 2 创建/进度、下载 SHA、重试和全局溢出 |

## 测试数据

| 目录/文件 | 用途 |
|---|---|
| [`tests/data/cli/pair_groups.json`](../../tests/data/cli/pair_groups.json) | `pair` 命令微型 group 输入 |
| [`tests/data/cli/pair_gaps.csv`](../../tests/data/cli/pair_gaps.csv) | `pair` 命令微型 gap 输入 |
| [`tests/data/condensed/`](../../tests/data/condensed/) | 4 个真实 robocrys condensed JSON 样本 |
| [`tests/data/e2e/`](../../tests/data/e2e/) | 3 个合成 rock-salt 端元、最小 condensed JSON、外部 gap 值和预期推荐；不是科研数据 |

## 常用验证

激活环境后运行：

```bash
python -m pytest -q -p no:cacheprovider
ruff check src tests
python -m pytest web/backend/tests
npm --prefix web/frontend run test
npm --prefix web/frontend run test:e2e
```

新增功能或修复缺陷时，应先运行最小目标测试，再运行完整套件。不得以历史测试结果替代本次新鲜验证。

## 最近同步

- 2026-10-15：字号测试补查“视图”位于工程工具栏且不创建独立菜单栏；保留字号选择、记忆与恢复验证。
- 2026-10-15：更新字号回归测试，通过菜单操作验证单选状态、持久化和恢复默认，6项Windows Qt测试通过。
- 2026-10-14：Windows Qt 字体测试在100%、125%、150%、200%缩放分别6项通过；WSL核心174项通过，
  未安装PySide6的环境跳过新增Qt测试模块。截图检查1366×768/14pt与1024×768/18pt。
- 2026-09-27：新增 2 项 `.ssproject` 容器测试；核心完整套件为 174 项，并通过 GUI Ruff、MatterViz
  生产构建、真实 187 制品项目回读和 wheel 静态资源包含性检查。
- 2026-09-02：远程发布前重新运行核心172项pytest、Ruff、Black，Web后端54项pytest/Ruff/Black，
  以及前端ESLint、Vitest 1项、TypeScript typecheck和生产构建；全部通过。未重跑需要浏览器与
  运行中服务的Playwright，沿用同日最近一次20项通过记录。
- 2026-09-01：Web后端扩展为54项；Stage 2单元/集成链验证双输入冻结、逐材料失败、Worker中断后
  检查点保留、Attempt #2跳过已完成JSON、五类制品和检查点成功清理；Playwright四宽度20项
  增加Stage 2创建、冻结配置、进度摘要和无页面级横向溢出。
- 2026-09-01：Playwright扩展为四宽度20项；真实微型WBM链验证composition冻结配置、2条候选
  受限预览、完整CSV入口和无页面级横向溢出，后端集成同时验证预览limit/总行数/字段类型。
- 2026-09-01：Web后端扩展为52项；新增微型WBM Dataset到Stage 1a composition的真实集成链，
  验证冻结输入SHA、2条候选、双Artifact、科学状态和不重复登记Dataset。
- 2026-09-01：Web后端扩展为51项；覆盖WBM草稿双文件、排队Task、运行中Worker取消后的隔离
  清理，以及科学校验失败保留输入供显式重试。
- 2026-09-01：核心扩展为172项，Web后端扩展为47项；新增WBM严格schema/摘要对齐、流式上传
  限额、路径型文件名拒绝，以及隔离→二次SHA核验→Dataset/Artifact登记→成功清理集成覆盖。
- 2026-09-01：Web 后端扩展为42项，新增核心源码/distribution版本一致性、源码SHA、production修订、
  ready检查和Run创建后身份变化拒绝覆盖；Playwright继续为四宽度16项并检查Run显示Core 1.0。
- 2026-09-01：Web 后端扩展为36项，新增 Stage 1 MP StageRunner、Dataset/双Artifact、路径脱敏、
  流式发布、未配置503和长任务失联恢复覆盖；Playwright扩展为四宽度16项，检查Stage 1表单、
  固定数据源、阈值单位和服务器路径不泄露。核心完整收集保持169项。
- 2026-08-31：Web 后端扩展为29项，覆盖稳定校验错误、owner/最近Run、重复与过期投递、取消一致性、
  停滞 outbox 重投和 Worker 丢失恢复；Playwright 在375/768/1024/1440四宽度共12项，并校验下载
  SHA-256、确定性失败重试和全局溢出。核心完整收集为169项。
- 2026-08-28：新增 Stage 1 在线 MP 默认120秒超时和失败页原位重试测试；完整收集增至168项。
- 2026-08-27：新增 Web 状态机、身份并发、三角色权限、跨项目隔离、ArtifactStore 安全、乐观锁、成功/失败重试链后端覆盖；新增状态可访问性 Vitest 和桌面/移动主路径及溢出 Playwright。
- 2026-08-24：VASP收集器扩展为5个测试并保留1个CLI测试；当前完整收集为166项。
- 2026-08-24：CLI 版本测试固定 `SS-SCREEN` ASCII Logo、空行和 `SS-Screen version 1.0` 的完整输出契约。
- 2026-08-03：新增 Stage 1--11 统一 CPU 端到端测试和 `tests/data/e2e/`；真实运行轻量 CLI，使用确定性 Stage 7/9/10 契约记录，双运行结果一致；完整收集为 158 项。
- 2026-08-03：新增 5 个 Stage 11 聚合器测试和 1 个 CLI 调用测试；完整收集为 157 项。
- 2026-08-03：扩展 MP 数据层与 CLI 覆盖，验证 deprecated 查询、最小字段投影、默认 sidecar、数据库 SHA/build metadata 和 API 数据库版本 provenance；测试函数数量不变。
- 2026-08-01：新增 5 个 `mp_offline` Row/provider/CLI/混合来源拒绝测试；完整收集为 151 项。
- 2026-07-31：新增 9 个外部带隙契约测试并扩展 CLI/依赖契约覆盖；完整收集为 146 项。
- 2026-07-31：新增 6 个 Stage 10 竞争相测试（含参数化失败分支），扩展 3 个 CLI 和 1 个依赖契约测试；完整收集为 134 项。
- 2026-07-31：新增 5 个 Stage 9 声子测试，并扩展 3 个 CLI 和 1 个依赖契约测试；完整收集为 124 项。
- 2026-07-30：新增 6 个 Stage 8 热力学测试，并扩展 CLI、SQS 与弛豫元数据覆盖；连同 icet 组分边界回归，完整收集为 115 项。
- 2026-07-30：新增 7 个 Stage 7 弛豫测试并扩展 CLI、SQS 和依赖契约覆盖；当时完整收集为 106 项。
- 2026-07-22：根据当前测试收集结果和测试文件建立初始索引。
