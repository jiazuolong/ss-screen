# 项目入口与配置

- 2026-11-14：[README](../../README.md) 和 [CMD 启动入口](../../start-10um.cmd) 支持双击自动准备私有 Windows Python；无需 py/PATH 手工配置，失败保留窗口与日志。固定运行时版本、签名校验及应用控制限制见[交付清单](../../docs/reproducibility/demo_v1_delivery.md)。

本目录导航仓库根部的权威入口文件。开始开发前，先通过这些文件确认规则、用途、依赖和许可证。

## 文件映射

| 真实路径 | 主要内容 | 何时阅读/更新 |
|---|---|---|
| [`AGENTS.md`](../../AGENTS.md) | 环境激活、读写边界、工作流程、日志规则 | 每次工作第一步；工作规则变化时更新 |
| [`README.md`](../../README.md) | 科学目标、安装、CLI 示例、当前状态 | 用户用法或能力边界变化时更新 |
| [`pyproject.toml`](../../pyproject.toml) | 包名、版本、依赖、extras、CLI、Ruff/Black/Pytest 配置 | 依赖、工具或命令入口变化时更新 |
| [`requirements.txt`](../../requirements.txt) | Ubuntu/Linux 开发安装入口，包含核心包、常用 workflow extras、GUI 和开发工具 | Linux 安装流程或可选依赖变化时更新 |
| [`LICENSE`](../../LICENSE) | MIT 许可文本 | 许可证变化时更新 |
| [`.gitignore`](../../.gitignore) | 环境、缓存、数据、秘密和大型文件排除 | 新增生成物或本地资产类型时更新 |
| [`.dockerignore`](../../.dockerignore) | 排除模型、运行数据、资料、秘密和本地构建缓存的容器上下文 | Web 镜像输入边界变化时更新 |

## 关键配置事实

- 包发布名：`ss-screen`
- Python 导入名：`ssscreen`
- 当前版本：`1.0`
- Python 要求：3.10 及以上；当前 WSL 环境为 3.11.15
- CLI 入口：`ss-screen = ssscreen.cli.app:cli`
- GUI 入口：`ss-screen-gui = ssscreen.gui.launcher:main`
- 核心依赖：pymatgen、pandas、numpy、monty、click、tqdm
- 常用 extras：`mp`、`wbm`、`condense`、`sqs`、`gui`、`mlp`、`phonon`
- `[mp]` 固定已验证的 `mp-api>=0.46.4,<0.47`；Stage 10 在线命令每次隐藏提示密钥且不落盘
- Stage 1 在线 MP 全量结构查询使用120秒单请求超时、500条稳定分页和单页3次重试；请求设置写入 provenance，密钥仅从标准配置发现且不落盘
- 离线 MP 使用 separately installed 的 `mp_offline 0.1.0` 和显式 SQLite 路径；当前环境验证 SQLAlchemy 2.0.51，数据库不进入仓库
- `[mlp]` 固定已验证的 MACE 0.3.14 / Torch 2.5.1 / ASE 3.26 兼容范围；CUDA wheel 按集群单独安装
- `[phonon]` 固定 Phonopy 4.x，并提供 SeeK-path、HDF5 和 matplotlib 频谱输出依赖；与 `[mlp]` 联用可直接计算 MACE 能量/力。
- 本地 MACE checkpoint 位于忽略的 `models/*.model`，[`models/README.md`](../../models/README.md) 跟踪来源、大小和 SHA-256
- 高精度带隙计算固定在外部执行；项目不提供 `dft` extra，也不依赖 AiiDA 运行时
- Stage 11 `RecommendationSettings` 集中管理混合焓、同 MLP 凸包和 gap 一致性初筛阈值；`ss-screen recommend` 可逐项覆盖并在 summary 中记录
- 根目录 `work/` 用于本地工作流运行与教学计算产物，并由 `.gitignore` 整体排除；可提交测试夹具仍只能放在 `tests/data/`
- Web 依赖保存在独立 [`web/backend/pyproject.toml`](../../web/backend/pyproject.toml) 和 [`web/frontend/package.json`](../../web/frontend/package.json)；根 `pyproject.toml` 不接收 Web 依赖。
- 桌面 GUI 依赖由根 `pyproject.toml` 的 `[gui]` extra 管理；GUI 只收集参数并调用真实 CLI，不替代科学实现。
- Web 的 Artifact、Attempt sandbox 和上传隔离根位于仓库外
  `/vepfs-mlp2/project-battery/zuolong/ss-screen-web-data`；ready 检查会按实际 UID 对三个目录执行
  无残留写入探针，禁止回退到 `work/`。
- Web Stage 1 MP 离线快照由 `MP_OFFLINE_DATABASE_PATH` 和不含路径的
  `MP_OFFLINE_DATABASE_REFERENCE` 在服务器配置；浏览器不能提交文件路径。数据任务进入独立 `cpu`
  队列，失联阈值由 `MP_DATASET_TASK_STALE_SECONDS` 设置。
- `SSSCREEN_CORE_REVISION` 提供可读的 Git/发布修订标识；production 禁止默认
  `development-worktree`。Web 同时计算实际核心 Python 源码 SHA-256，并要求源码版本与 editable/
  wheel distribution metadata 一致。

## 推荐阅读顺序

1. [`AGENTS.md`](../../AGENTS.md)
2. [`README.md`](../../README.md)
3. [`pyproject.toml`](../../pyproject.toml)
4. [项目文档与开发计划](../04_项目文档与开发计划/README.md)
5. [正式源码](../02_正式源码/README.md)

## 最近同步

- 2026-09-27：`.gitignore` 新增 `/gui-matterviz/node_modules/`；MatterViz 的 Svelte 源码、
  `package.json`、锁文件和构建配置继续跟踪，约 162 MB 的可重装 npm 依赖不进入版本库。
- 2026-09-11：WSL 下新增被忽略的 `.venv-mlp/`，安装 `torch 2.5.1+cu121`、`mace-torch 0.3.14`、
  `phonopy 4.5.0` 和项目 `[mlp,phonon]` 依赖；`.gitignore` 增加 `.venv-*/`，避免专用环境入库。
- 2026-09-07：新增 `requirements.txt` 作为 Ubuntu/Linux 开发安装入口；根包新增 `[gui]` extra 和
  `ss-screen-gui` 脚本，CLI 入口保持 `ss-screen` 不变。
- 2026-09-02：提交前将前端 `*.tsbuildinfo` 增量编译缓存加入 `.gitignore`；虚拟环境、缓存、
  模型权重、运行产物和 Web 构建输出继续保持仓库外或忽略状态。
- 2026-09-01：Web 配置新增 WBM 结构/摘要上传字节上限；必须为正值，并与仓库外 quarantine、
  API/CPU Worker 共享挂载及反向代理请求体上限保持一致。
- 2026-09-01：项目 `.venv` 的 editable `ss-screen` 元数据已从陈旧0.1.0校正为1.0；登记核心修订、
  源码SHA、ready/Run/Worker三重一致性门禁和production配置要求。
- 2026-09-01：登记 Web Stage 1 MP 离线快照的服务端配置、路径隔离、独立 CPU 队列和长任务失联阈值。
- 2026-08-31：Web 配置明确三个仓库外存储根、outbox 重投和演示任务失联阈值；逗号分隔的
  `CORS_ORIGINS` 可由环境变量稳定解析。
- 2026-08-28：README登记 Stage 1 在线 MP 的稳定分页、单页重试、超时和 provenance 记录；实际 API 密钥不进入仓库或运行产物。
- 2026-08-27：新增独立 Web 后端/前端依赖、容器上下文排除、仓库外 ArtifactStore 和开发身份安全配置。
- 2026-08-03：README 登记 Stage 1--11 CPU-only artifact-chain fixture；外部 gap 与 Stage 7/9/10 昂贵引擎由确定性测试记录替代。
- 2026-08-03：README 增加 Stage 11 `recommend` Bash 示例、L2--L6 证据等级、三类推荐和可选缺陷边界；推荐阈值统一由 `RecommendationSettings` 提供。
- 2026-08-03：`.gitignore` 新增 `/work/`，防止本地 SQS、MACE、声子和凸包计算产物进入版本控制。
- 2026-08-03：README 的 Stage 1 MP 示例增加 provenance sidecar；登记外部快照通过 SHA/完整性审计且完整数据库继续保留在仓库外。
- 2026-08-01：登记 Stage 10 `mp_offline` 独立安装、显式数据库路径和快照 SHA provenance。
- 2026-07-31：移除未实现的 `dft` extra，登记外部高精度带隙任务/结果契约边界。
- 2026-07-31：登记 Stage 10 使用的 `mp-api` 0.46.x 契约和逐次隐藏密钥提示边界。
- 2026-07-31：登记 `[phonon]` extra 和项目 `.venv` 中 Phonopy 4.4.0 / SeeK-path 2.2.1 环境。
- 2026-07-30：登记 `[mlp]` extra、本地模型资产规则和项目 Python 3.11.15 MACE 环境。
- 2026-07-22：根据当前根目录文件、Python 3.11 WSL 环境和 `pyproject.toml` 建立初始索引。
