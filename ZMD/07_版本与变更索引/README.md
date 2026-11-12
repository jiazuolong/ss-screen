# 版本与变更索引

- 2026-11-13：登记 10 μm 工作区一键创建与 GUI 启动入口，支持复用已导入的工程。

本页记录 ZMD 与真实工作区的同步历史。它不是 Git 历史的替代品；代码级差异仍以 Git 为准，跨会话决策仍以 [`docs/PROJECT_LOG.md`](../../docs/PROJECT_LOG.md) 为准。

## 当前基线

| 项目 | 当前值 |
|---|---|
| 初始同步日期 | 2026-07-22 |
| 工作区 | `/vepfs-mlp2/project-battery/zuolong/ss-screen-learning-20260722` |
| Git 分支 | 本地 `codex/web-platform`，跟踪远程 `origin/master` |
| 基线提交 | `33f9cc3` — `feat: add screening workflow and web platform` |
| 包版本 | `ss-screen 1.0` |
| Python 环境 | 项目本地 Python 3.11.15 |
| 导航范围 | 根入口、26 个科学源码文件、Web 控制层/前端/部署、核心与 Web 测试、docs/plans、models、11 个历史资料家族、scripts 和 CI |

### 2026-09-02 — 发布当前完整工作树到远程 master

- Git发布：将241个约定范围内文件提交为`33f9cc3`，通过SSH以非强制方式新建并推送
  `origin/master`；远程`main`保持在`33ddf40`，没有覆盖、重命名或删除。
- 范围与门禁：包含核心源码/测试、Web平台、脚本、项目文档、软著交付物、ZMD与配置；排除环境、
  缓存、构建输出、模型权重和运行数据。核心172项、Web后端54项、Vitest 1项及静态/构建门禁通过。

### 2026-09-02 — 恢复远程 Web 服务

- 运行状态：前端5173、API 8000、PostgreSQL、Redis和control/cpu Worker均已启动；针对交互会话结束
  后API退出导致的`Failed to fetch`，API/Worker已改为脱离会话的开发后台进程，ready六项检查通过。
- ZMD更新：同步项目日志、项目文档导航和本索引；无代码、schema或科学路线变更。

### 2026-09-01 — 实现 Web Stage 2 condensation

- 真实变更：新增condensation pipeline/StageRunner/CPU Worker，冻结Dataset与composition双输入身份，
  实现分批检查点、取消检查、逐材料失败、基础设施失败后Attempt续跑、实时进度和ZIP/index/failures/
  manifest/provenance五类制品；前端新增创建页和数据密集型进度/失败界面。
- ZMD更新：同步Web、测试、项目文档和本索引；核心172项、Web后端54项、Vitest 1项、四宽度
  Playwright 20项及静态/构建/OpenAPI/ready门禁通过；真实Robocrys两结构Web运行2/2成功。

### 2026-09-01 — 完善 composition Run 候选预览

- 真实变更：新增鉴权、有界的composition preview API；Run页显示冻结Dataset/阈值、零候选语义、
  前20行候选和完整CSV入口，Artifact页修正候选/科研provenance说明。
- ZMD更新：同步Web、测试、项目文档和本索引；Web后端52项、Vitest 1项、四宽度Playwright
  20项及静态/构建/OpenAPI/ready/视觉门禁通过，下一步转入Stage 2 condensation。

### 2026-09-01 — 实现 Web Stage 1a composition

- 真实变更：新增composition pipeline/StageRunner/CPU Worker，冻结Dataset Artifact身份和参数，
  发布候选CSV/provenance；前端Dataset页新增筛选入口与响应式参数表单；新增ADR-0007。
- ZMD更新：同步Web、测试、项目计划、开发指南和本索引；Web后端52项、Vitest 1项、四宽度
  Playwright 16项及完整静态/构建/视觉门禁通过。

### 2026-09-01 — 补齐 WBM 取消态隔离清理

- 真实变更：新增上传生命周期清理模块；草稿、排队和运行中取消均在数据库终态提交后幂等回收
  WBM隔离输入，失败输入保留用于retry；WBM启动前补齐科学核心身份门禁。
- ZMD更新：同步Web、测试、ADR、开发指南和本索引；Web后端51项pytest及Ruff/Black通过。

### 2026-09-01 — 实现 Web Stage 1 WBM 隔离上传

- 真实变更：新增 `stage-1-wbm-upload-v1` multipart API、仓库外 quarantine、严格 WBM StageRunner、
  CPU Worker、原始/规范/provenance Artifact、Dataset 登记与前端上传/审计页面；新增 ADR-0006。
- ZMD 更新：同步 Web、测试、项目文档和本索引；当前验证为核心172项、Web后端47项、Vitest 1项、
  四宽度Playwright 16项，Ruff/Black/ESLint/TypeScript/构建/OpenAPI生成和WBM页面视觉检查通过。

## 同步记录

### 2026-10-15 — 视图入口与工程操作同排

- 按用户反馈把“视图”改为工程工具栏中的即时下拉按钮，与“新建工程”同一行，取消单独顶层菜单栏。
- 保留“界面字号”子菜单、自动记忆与恢复默认；窗口较窄时入口随其他动作进入工具栏溢出菜单。
- 更新GUI说明与现有字体测试，验证入口位置及6项字体回归。

### 2026-10-15 — 将字号设置移到菜单栏

- 主窗口新增“视图 → 界面字号”，采用9--18 pt单选菜单并提供恢复默认动作，移除深色标题条的字号控件。
- Git历史确认`SS-SCREEN`标识从`900c758`最初GUI提交就存在，按用户要求保留。
- 更新字体回归测试与GUI说明；6项Windows Qt测试、Ruff和Python编译通过，检查主界面与字号菜单截图。

### 2026-10-14 — 字号设置与高 DPI 布局适配

- 新增 `src/ssscreen/gui/appearance.py` 与 `tests/test_gui_appearance.py`；主窗口提供9--18 pt字号设置，
  默认10 pt，自动记忆并支持恢复。样式中的像素字体统一转换为点数，保留标题层级。
- 工具栏采用Qt溢出菜单，中央/属性区提供滚动，表格行高/列宽与预览尺寸随字号变化；MatterViz同步缩放。
- 验证：Windows Qt在100/125/150/200%缩放各6项通过，WSL核心174项通过；实际截图检查小窗口大字号。

### 2026-09-28 — 修正结果表格与 MatterViz 布局

- 真实变更：Stage 11 表格改用填充式列宽，新增 28 条相记录计数，角色、目标标志和凸包距离使用中文/格式化显示。
- 真实变更：Stage 10 晶体视图从右侧半栏移到完整 MatterViz 标签页；Stage 10/11 WebEngine 视图使用扩展尺寸，
  内嵌前端的根容器与 canvas 同步填满可用空间。
- 验证：真实结果读取到竞争相 28 行、声子 3 行；1280×760 页面下两个 MatterViz 视图均为约 1256×691；
  Ruff、`py_compile`、2 项 `.ssproject` 测试和 MatterViz production build 通过。

### 2026-09-27 — 忽略 MatterViz npm 依赖目录

- 忽略规则：新增 `/gui-matterviz/node_modules/`，排除约 162 MB 的可重装 npm 依赖和 Vite 缓存。
- 保留范围：`gui-matterviz/src/`、`public/`、`package.json`、`package-lock.json` 及构建配置仍纳入版本管理，
  确保内嵌 MatterViz 可维护、可审计和可复现构建。

### 2026-09-27 — 集成桌面结果可视化与单文件项目

- 真实变更：GUI 新增 MatterViz 晶体浏览、声子 band/DOS/状态页、竞争相表格与三元组成图；MACE 默认
  设备改为 CPU，CLI 选项增加中文标签，SSH 增加只读环境探测且不提交远端作业。
- 真实变更：新增 `.ssproject` ZIP64 容器，保存 Stage 01--12、流程选择和 SHA-256 清单并安全回读；
  MP API Key 不进入项目文件。真实 01--12 算例打包为 187 个制品，原始 1,038,559 bytes，容器
  409,144 bytes，校验回读通过。
- 前端变更：新增 `gui-matterviz/` Svelte 构建工程和随 Python wheel 分发的 MatterViz 0.7.0 静态资源；
  高级控制面板因上游 `svelte-widgets` 初始化错误关闭，核心 WebGL 渲染与交互保留。
- 验证：核心 174 项 pytest、目标 Ruff、MatterViz production build 和 wheel 资源检查通过；真实浏览器
  可视验收确认 CaSe 晶胞非空并显示元素图例/复制控件。当前 WSL OpenSSH 可用，但尚无服务器账号，
  因而只验证了本地探测能力和命令边界。

### 2026-09-18 — 调整声子输入残余力默认阈值

- 真实变更：`src/ssscreen/config.py` 将 `PhononSettings.max_input_force` 从 `0.01` 调整为
  `0.02 eV/Angstrom`，CLI 和 GUI 声子命令预览同步继承新默认值。
- 真实变更：GUI 的 `stability phonon-run` preset 默认勾选 `--include-endmembers`，一步式声子任务会把
  已驰豫端元结构纳入计算。
- ZMD 更新：同步 GUI、stability 源码导航、本索引和项目日志。

### 2026-09-17 — 优化 GUI 后段流程与报告展示

- 真实变更：`src/ssscreen/gui/metadata.py` 隐藏 Stage 10 的声子拆分三步和 Stage 11 的竞争相拆分三步；
  GUI 当前只显示 `stability phonon-run` 与 `stability phase-diagram` 两个一步式后段命令，CLI 保留拆分命令。
- 真实变更：`src/ssscreen/gui/app.py` 的通用布尔选项显示不再展示正反双标签；`--include-endmembers`
  preset 默认勾选，并会正确出现在 MACE relax 命令预览中。
- 真实变更：新增 Stage 12 专用报告页，内嵌 `12_recommend/recommendation_report.md` Markdown 预览，
  并把 `recommendations.csv` 与 pair、SQS manifest、mixing、phonon、phase 证据合并为候选表。
- 真实变更：工具栏新增运行状态文字与不确定进度条，任务运行时显示“正在计算”和最新输出摘要。
- ZMD 更新：同步 GUI 源码导航、本索引和项目日志。
- 验证：WSL `.venv` 下 `python -m py_compile src/ssscreen/gui/app.py src/ssscreen/gui/metadata.py` 通过；
  Windows `C:\SoftWare\Python\python.exe` + PySide6 验证隐藏命令、`include-endmembers` 默认勾选且生成
  `--include-endmembers`，Stage 12 读取到 1 条推荐和 Markdown 报告。

### 2026-09-16 — 修正 GUI 阶段路径归一化

- 真实变更：`src/ssscreen/gui/app.py` 新增 GUI 子目录残留路径归一化，专用页面在显示、解析和运行时会把
  `src/ssscreen/gui/...` 下的阶段目录折回工程根目录相对路径；结构匹配页保存归档目录时也使用归一化后的
  `03_condensed/local`。
- 真实变更：左侧工程树 Stage 03/04 统计补充 `03_condensed/local`，使本地 POSCAR/CONTCAR 归档产物能被
  正确计入结构描述和结构匹配准备状态。
- 真实变更：右侧运行后端新增 WSL 自动选择模式；前中段和 SQS 使用 `.venv`，MACE relax、phonon 与
  phase-diagram 使用 `.venv-mlp`；误选 `.venv-mlp` 跑 SQS 时自动回退 `.venv`，避免 NumPy pickle
  跨环境不兼容。
- ZMD 更新：同步 GUI 源码导航和本索引；项目日志记录该 GUI 路径修复。
- 验证：WSL `.venv` 下 `python -m py_compile src/ssscreen/gui/app.py src/ssscreen/gui/metadata.py` 通过；
  Windows `C:\SoftWare\Python\python.exe` + PySide6 验证从 `src/ssscreen/gui` 启动时活动工程识别为仓库根，
  结构匹配命令预览为 `--condensed-dir 03_condensed/local`。
- 验证：Windows GUI 后端选择逻辑确认 SQS 预览使用 `.venv/bin/activate`、MACE relax 使用
  `.venv-mlp/bin/activate`；WSL `.venv` 实际复跑 `stability sqs-generate` 得到
  `written=1 skipped=0`。

### 2026-09-15 — 补跑 MP API 竞争相凸包

- 运行产物：第一次 `work/real-pbe-mace-20260914-run4/11_phase_api/` 因 MP API read timeout
  得到 `missing_elemental_reference`；第二次 `work/real-pbe-mace-20260914-run4/11_phase_api_retry/`
  使用 `--thermo-type GGA_GGA+U --api-timeout 180` 成功。
- 运行结果：MP API 查询 `Ca-Se-Te` 体系得到 25 个竞争相，25 个竞争相 MACE relaxation 可用；
  `phase_stability.csv` 中 CaSe-CaTe SQS 的 hull distance 为 `0.3497941494 eV/atom`，
  `hull_signal=unstable`，`competing_set_complete=True`，MP database version 为 `2026.04.13`。
- 推荐输出：新增 `work/real-pbe-mace-20260914-run4/12_recommend_api/`，推荐仍为
  `low-priority`，证据等级 L5，风险包含 `phase:above_low_priority_threshold`。
- 文档更新：`docs/real_vasp_mace_pipeline_2026-09-14.md` 记录真实 API hull 结果；
  `docs/gui_full_pipeline_runbook_2026-09-14.md` 和 `src/ssscreen/gui/metadata.py` 的 Stage 11
  默认参数补充 `GGA_GGA+U` 与 180 秒 API timeout。
- 验证：本次未运行 DFT、AiiDA 或 notebook；MP API Key 未写入源码、日志或文档。

### 2026-09-14 — 调整 GUI 默认参数并新增全流程操作单

- 真实变更：`src/ssscreen/gui/metadata.py` 和 `src/ssscreen/gui/app.py` 的默认路径/参数切换为
  CaS/CaSe/CaTe PBE relaxed 结构、真实 VASP task-id 结果、`data/mace-mpa-0-medium.model`、
  CUDA MACE、快速 phonon 和 MP API phase-diagram 演示链路。
- 真实变更：`src/ssscreen/cli/app.py` 的 Materials Project API Key 读取改为优先使用
  `MP_API_KEY` 环境变量，环境变量缺失时才交互提示；GUI 可通过右侧 Properties 注入 Key 后运行
  Stage 11。
- 真实变更：新增 `data/CaS_CaSe_CaTe_PBE_relaxed_CONTCAR/`，只保留同事 VASP 结果中的三个 PBE
  relaxed `CONTCAR` 结构，避免 GUI 递归扫描完整 VASP 目录时重复读取 `POSCAR` 和 `CONTCAR`。
- 真实变更：新增 `docs/gui_full_pipeline_runbook_2026-09-14.md`，列出 GUI 每一步具体选择、默认参数、
  后端切换和最终输出文件。
- ZMD 更新：同步 GUI 源码导航、项目文档导航和本页；项目日志记录该演示链路。
- 验证：默认前中段实际跑到 `gap-export`，得到 3 条 dataset、3 条候选、3 个 condensed JSON、
  1 个 structure group 和 3 个 gap task；新 task-id 与既有 VASP by-task 目录完全匹配。继续用
  默认 VASP 收集/校验/pair 得到 `success=3`、`accepted=3 rejected=0`、1 对 pair。相关 CLI 测试
  `pytest tests/test_cli.py -k "competing_export or phase_diagram"` 为 5 passed；GUI/CLI 文件
  `py_compile` 通过。

### 2026-09-14 — 校验 MP API Key 并更新真实流程文档

- 真实变更：更新 `docs/real_vasp_mace_pipeline_2026-09-14.md`，记录 `data/API Key.txt`
  可用于当前项目的在线 Materials Project 后端；明确 `dataset mp --backend api`、
  `stability phase-diagram --mp-backend api` 和 GUI 子进程环境注入的使用边界。
- ZMD 更新：`ZMD/04_项目文档与开发计划/README.md` 登记该文档状态修正；本页记录同步。
- 验证：确认当前 WSL `.venv` 为 Python 3.11、`ssscreen 1.0` 可导入，`mp_api.client.MPRester`
  可导入，Key 文件存在且非空；本次未重跑完整流程、phase-diagram、MACE、phonon、DFT 或 AiiDA。

### 2026-09-14 — 记录真实 VASP + MACE 流程验证

- 真实变更：新增 `docs/real_vasp_mace_pipeline_2026-09-14.md`，整理同事 PBE VASP 结果、
  `data/mace-mpa-0-medium.model`、PBE relaxed `CONTCAR` 输入、两种 gap 口径、MACE relaxation、
  混合焓、phonon、recommendation 和 phase 阻塞状态。
- 运行产物：最终有效目录为 `work/real-pbe-mace-20260914-run4/`；`run3` 保留为初始 POSCAR
  体积质量控制失败的对照。
- 验证：真实 VASP gap 收集/校验 `accepted=3 rejected=0`；MACE relaxation `success=3` 且均 usable；
  mixing enthalpy `success=1`；phonon `success=1` 且 dynamical status 为 `unstable`；recommendation
  输出 1 条 `low-priority`。

### 2026-09-12 — 修复 GUI 组成筛选路径与 WSL 日志可读性

- 真实变更：`src/ssscreen/gui/app.py` 组成筛选页只自动加入真实存在的 `01_dataset/*.df`，
  自动清理旧的 `src/ssscreen/gui/01_dataset/...` 残留默认项；发往 WSL 的相对路径统一转换为
  POSIX `/` 分隔；WSL localhost/NAT 启动乱码警告在 GUI 日志中压缩为英文说明。
- 忽略规则：`.gitignore` 增加工程根阶段输出目录 `01_dataset/` 至 `12_recommend/`，防止 GUI/CLI
  现场演示产物误进入版本控制。
- 验证：从错误子目录实例化 GUI 后，项目根自动识别为 `D:\WorkSpace\OtherProjects\ss-screen`；
  组成筛选命令预览为 `--df 01_dataset/local_structures.df`；按 GUI 默认相对路径实际跑通
  Stage 01 POSCAR 导入、Stage 02 composition、Stage 03 condense/validate、Stage 04 structure-match
  和 Stage 05 gap-export。

### 2026-09-12 — 修复 GUI 直接启动时 WSL 工程根目录识别

- 真实变更：`src/ssscreen/gui/app.py` 新增项目根目录识别逻辑；从 PyCharm 直接运行
  `src/ssscreen/gui/app.py` 时，会向上查找 `.ssscreen-project.json`、`.git` 或含 `src/ssscreen`
  的 `pyproject.toml`，避免默认工程停在 `src/ssscreen/gui` 导致 WSL 后端找不到 `.venv`。
- ZMD 更新：`ZMD/02_正式源码/gui.md` 记录该启动路径修复；本页记录同步。
- 验证：Windows Python 和 WSL `.venv` 下 `python -m py_compile src/ssscreen/gui/app.py` 通过；
  Windows Python 直接调用 `_find_project_root(D:\WorkSpace\OtherProjects\ss-screen\src\ssscreen\gui)`
  返回 `D:\WorkSpace\OtherProjects\ss-screen`。

### 2026-09-12 — 新增 GUI/WSL/POSCAR 现场演示 runbook

- 真实变更：新增 `docs/gui_wsl_poscar_demo_runbook_2026-09-12.md`，把 Windows GUI 启动、
  WSL 后端选择、本地 POSCAR 导入、组成筛选、结构描述、结构匹配、gap 任务导出、CLI 备用命令、
  同事材料清单和汇报话术整理为现场可执行步骤。
- ZMD 更新：`ZMD/04_项目文档与开发计划/README.md` 登记该 runbook 入口；本页记录同步。
- 验证：基于已存在的 `work/poscar-gui-cli-20260911` 产物和当前 `ss-screen --version`、
  `dataset structures --help` 检查整理；本次未运行 DFT、notebook、MACE、Phonopy 或 AiiDA daemon。

### 2026-09-12 — 整理当前能力与同事交接清单

- 真实变更：新增 `docs/current_capability_and_handoff_2026-09-12.md`，集中整理当前 GUI、
  WSL 后端、POSCAR 输入、前中段流程、PyTorch/CUDA/MACE/phonopy 环境、已测试方法和需同事提供材料。
- ZMD 更新：`ZMD/04_项目文档与开发计划/README.md` 登记该交接清单入口；本页记录同步。
- 验证：文档内容基于 2026-09-11 已完成的 POSCAR smoke、GUI/WSL smoke、18 项 pytest、
  Ruff 和 CUDA/MACECalculator 导入验证；本次仅新增文档。

### 2026-09-11 — 接入本地 POSCAR 数据源与 GUI/WSL 后端

- 真实变更：新增 `src/ssscreen/data/structures.py` 和 `ss-screen dataset structures`，支持递归读取
  POSCAR/CIF/vasp/json 文件夹为 Stage 1 DataFrame；`src/ssscreen/gui/app.py` 新增 Windows/WSL 运行
  后端选择、本地 POSCAR 数据源页、WBM 必填 `--xyz` 输入和结构归档递归文件夹扫描；`metadata.py`
  登记 `dataset structures`；新增 `tests/test_data_structures.py`，扩展 `tests/test_cli.py`。
- 文档更新：`README.md`、`docs/cli_front_mid_smoke_2026-09-10.md`、`ZMD/02_正式源码/data.md`、
  `ZMD/02_正式源码/cli.md` 和 `ZMD/02_正式源码/gui.md` 同步新入口、GUI 联动和 POSCAR smoke 结果。
- 验证：`data/CaS_CaSe_CaTe_POSCAR` 三个 POSCAR 从 `dataset structures` 跑到 Stage 12 推荐；
  GUI headless Qt 通过 `wsl.exe` 调用 `ss-screen --version` 和 `dataset structures` 成功；
  相关 py_compile、18 项 pytest 和 Ruff 通过。真实 MACE/Phonopy 计算仍缺 checkpoint。

### 2026-09-11 — 配置 WSL MLP/phonopy 专用环境

- 真实变更：新增本地忽略环境 `.venv-mlp/`，安装 `torch 2.5.1+cu121`、`mace-torch 0.3.14`、
  `phonopy 4.5.0`、项目 `[wbm,mp,condense,sqs,mlp,phonon]` extras 和 `pytest`；`.gitignore`
  增加 `.venv-*/`，避免专用虚拟环境被误加入版本控制。
- ZMD 更新：`ZMD/01_项目入口与配置/README.md` 登记 WSL MLP 专用环境和忽略规则；本页记录同步。
- 验证：WSL `nvidia-smi` 可见 RTX 4060；`torch.cuda.is_available()` 为 True；`mace.calculators.MACECalculator`
  导入成功；`uv pip check` 通过；`stability relax`、`phonon-run`、`phase-diagram` help 通过；
  `tests/test_e2e_pipeline.py`、`tests/test_stability_relax.py`、`tests/test_stability_phonon.py` 共 14 项通过。
  `mp_offline` 包和数据库仍需同事提供。

### 2026-09-10 — 整理 CLI 前中段流程验证交接单

- 真实变更：新增 `docs/cli_front_mid_smoke_2026-09-10.md`，按 Word 流程整理 WSL CLI 已跑通阶段、
  测试产物、操作流水和真实运行需补齐的数据源、MACE、phonopy、高精度 gap 结果。
- ZMD 更新：`ZMD/04_项目文档与开发计划/README.md` 登记该交接单入口；本页记录同步。
- 验证：基于本轮已完成的 WSL CLI smoke run 输出整理；未新增源码改动，未运行 notebook、DFT、
  MACE、Phonopy 或 AiiDA daemon。

### 2026-09-09 — GUI 支持 IDE 直接运行 app.py

- 真实变更：`src/ssscreen/gui/app.py` — 增加直接脚本运行时的 `src` 路径注入和绝对导入分支，
  保留包模式相对导入。
- ZMD 更新：`ZMD/02_正式源码/gui.md` — 记录 `app.py` 可由 PyCharm 直接启动，且 GUI 仍调用真实 CLI。
- 验证：`python -m py_compile src\ssscreen\gui\app.py` 通过；当前 Windows Python 未安装项目包和
  PySide6，未执行 GUI 视觉启动。

### 2026-09-01 — 固化 Web 科学核心版本与源码身份门禁

- 真实变更：新增科学运行时身份模块；Stage 1 Run冻结源码/distribution版本、部署修订和核心源码
  SHA-256，ready、启动和Worker执行前复核，最终身份进入provenance；Run/Dataset页面同步显示。
- 环境修复：仅在项目`.venv`重装editable根包，已安装`ss-screen` metadata由陈旧0.1.0更新为1.0，
  与源码一致；production新增`SSSCREEN_CORE_REVISION`强制配置。
- ZMD更新：同步入口配置、Web、测试、项目文档和本索引；已有不可变Dataset不回写。验证为核心
  169项、Web后端42项、Vitest 1项、四宽度Playwright 16项及完整格式/构建/链接/ready门禁通过。

### 2026-09-01 — 完成首个真实 Web Stage 1 MP 离线运行

- 运行结果：`max_e_hull=0.01 eV/atom` 得到46,675条记录；Run/Task/Attempt成功，Dataset已登记；
  430,317,793字节 `mp.df` 与1,185字节 provenance 的实测大小/SHA均与数据库一致，路径脱敏通过。
- 存储边界：2.22 GB输入快照和430 MB输出均保留在仓库外，临时 Attempt sandbox自动清理；服务
  ready五项保持正常，未运行notebook、DFT、MACE、Phonopy或AiiDA daemon。
- 已知环境项：provenance如实记录已安装editable distribution metadata为`ss-screen 0.1.0`，但源码
  和根`pyproject.toml`为`1.0`；后续科研运行前需重装项目editable metadata并增加版本一致性门禁。

### 2026-09-01 — 实现 Web Stage 1 MP 离线 Dataset 垂直切片

- 真实变更：新增 Dataset schema/API/UI、`stage-1-mp-offline-v1` StageRunner、独立 CPU Worker/队列、
  流式 Artifact 发布和长任务失联恢复；核心 MP loader 支持以稳定引用替代服务端绝对路径。
- ZMD 更新：同步 Web、入口配置、data 源码、测试、项目文档和本索引；新增 ADR-0005。当前边界
  明确为 MP 离线入口已完成，WBM/上传、Stage 1a--11、正式 OIDC 与 GPU/HPC 尚未实现。
- 验证：核心169项、Web后端36项、Vitest 1项、四宽度Playwright 16项通过；migration
  `up/down/up`、schema drift、OpenAPI重复生成、Ruff、Black、ESLint、TypeScript、构建、视觉与
  路径脱敏检查通过。外部2.22 GB快照未复制，未自动启动数百MB全量Web导出。

### 2026-09-01 — 启动本地 Web 控制层

- 运行状态：保留既有 PostgreSQL/Redis 容器，启动 Uvicorn API、Celery control Worker 和 Vite
  production preview；网页与 API 文档返回 HTTP 200，五项 ready 检查全部为 `ok`。
- ZMD 更新：同步项目文档导航和本索引；未修改功能、schema 或科学路线，未运行 notebook、DFT
  或 AiiDA daemon。Celery 的 root 身份仅限当前开发预览，生产部署仍需专用非 root 用户。

### 2026-08-31 — 加固并验收 Web 控制层 Phase 1

- 真实变更：ArtifactStore 增加真实写入 ready 探针与并发不覆盖发布；项目列表补充 owner/最近Run；
  Run/Task/Attempt 取消、重试和重复投递保持事务一致；控制层增加停滞 outbox 重投与演示 Worker
  失联恢复；前端补充 viewer 权限、邻近错误、下载 SHA 校验和四宽度响应式 E2E。
- ZMD 更新：同步 Web、入口配置、测试、项目文档和本索引；Stage 1--11 StageRunner 仍未接入，
  demo JSON 仍不是科研结果。
- 验证：核心169项、Web后端29项、Vitest 1项、Playwright 12项通过；真实 PostgreSQL migration
  `up/down/up` 与 schema drift 检查通过；Ruff、Black、TypeScript、ESLint、构建和四宽度视觉检查
  通过。临时 migration 审计数据库已删除，未运行 notebook、DFT 或 AiiDA daemon。

### 2026-08-28 — 生成第十五章现场演示截图

- 真实变更：在被 Git 忽略的 `work/chapter15-live/` 按完整 BASH 块执行第15.2节目录/环境命令和第15.3节在线数据/组成筛选；在线 MP 数据为45,624条、421.9 MB，得到4,408条候选和343个模板；截图和运行数据不纳入正式资产导航。
- 代码与ZMD同步：Stage 1 API 改为120秒超时、500条稳定分页和失败页3次重试，请求设置进入 provenance；更新配置、数据层、README、2项测试、入口/源码/测试/文档导航和本索引。
- 验证：数据库版本2026.04.13，45,624个ID无重复，API密钥在文本产物中零残留；完整168项pytest、`ruff check src tests`和现场图片人工检查通过。依赖快照含3条本地路径，外发前需脱敏；未运行VASP、DFT、MACE、Phonopy、notebook或AiiDA daemon。

### 2026-08-27 — 实现 Web 控制层 Phase 1 垂直切片

- 真实变更：新增 `web/backend` 独立 FastAPI/SQLAlchemy/Alembic/Celery 包、PostgreSQL 权威状态机、事务 outbox、开发身份与三角色权限、安全 ArtifactStore、SSE 和确定性 demo Worker；新增 `web/frontend` 五页 React 工作台、生成式 OpenAPI 类型客户端和响应式 UI；新增 Compose、四份 ADR 与本地开发文档。
- ZMD 更新：新增 Web 平台分区，更新总入口、工作区真实路径、目录树、资产、入口配置、测试、项目文档和本版本索引；demo JSON 明确不是科研结果，Stage 1--11 StageRunner 仍未实现。
- 验证：核心 166 项 pytest/Ruff 基线通过；Web 后端 19 项、Vitest 1 项、Playwright 4 项通过；真实 PostgreSQL migration `up/down/up` 和 schema drift 检查通过；375/768/1024/1440 页面无全局横向溢出。

### 2026-08-26 — 建立方案二 Web 平台开发基线

- 真实变更：新增 `docs/web_platform_development_guide.md`，固定 React/TypeScript + FastAPI + PostgreSQL + Redis/Celery + 外部 ArtifactStore 架构，定义领域实体、运行/科学双状态、StageRunner、API、页面、安全、测试、运维、四阶段路线和首批20项开发任务；`docs/PROJECT_PLAN.md` 增加 Web 扩展路线。
- ZMD 更新：同步项目文档导航、文件资产索引、工作区目录树和本版本索引，并把导航中的当前包版本及测试数修正为真实文件系统状态。
- 状态边界：当前只完成开发设计，没有创建 `web/` 运行时代码、数据库、队列、前端、容器或集群作业。

### 2026-08-24 — 补齐VASP批量收集审计契约

- 真实变更：`gap-collect-vasp` 接受方法元数据并写入设置哈希；缺失任务写入 `missing` 结果行；报告增加四状态零值计数、逐任务错误、已发现和未知目录；`--report` 可省略并自动生成。
- 文档同步：更新README、带隙算法说明、V1.0手册和CLI/pair/测试导航；单任务模式继续只用于调试与重试。
- 验证：完整166项pytest、Ruff、涉及文件Black和`pip check`通过；V1.0手册构建器`--check`通过，DOCX/PDF含37处图片。全库Black仅保留两个与本次无关的既有格式差异。

### 2026-08-24 — 新增VASP批量带隙结果收集命令

- 真实变更：新增 `pair/gap_collect_vasp.py` 和顶层 `gap-collect-vasp`，默认批量解析 `task_id/vasprun.xml[.gz]`，输出稳定结果CSV及成功、未收敛、失败、缺失审计报告；重复 `--task-id`用于单任务调试或选择性重试。
- 文档同步：更新README、Stage 3计划、带隙算法说明、V1.0手册第7章、CLI/pair/测试导航和本索引。
- 验证：Black、Ruff、完整165项pytest和`pip check`通过；登记版构建器通过，DOCX/PDF仍为37处图片引用和65页。无真实vasprun夹具，解析字段由模拟Vasprun对象测试，批量目录与状态由真实文件I/O测试覆盖。未运行VASP、DFT、AiiDA或其他昂贵任务。

### 2026-08-24 — 增加 gap-export 连续操作截图

- 真实变更：资产构建器使用真实教学结构组和数据集执行独立的VASP方法身份任务导出，新增四张输入、执行、任务/结构和模板检查终端图；第7章同步更新图7-1至图7-6并重建DOCX/PDF。
- 真实性边界：导出3条任务和9个JSON/CIF/POSCAR结构文件，但不运行VASP；原合成gap校验链保持不变。
- 验证：Black、Ruff和登记版构建检查通过；资产目录含36个不同图片文件，DOCX含37处内嵌图片引用且无外链，PDF 65页，第7章连续页面视觉检查通过。

### 2026-08-24 — 完善 V1.0 手册第六至十七章连续操作流程

- 真实变更：仅扩写 V1.0 操作手册第六至十七章，增加操作前后数据变化、阶段验收、下一章交接、端到端台账、结果反向审计和故障复验闭环；重新生成同名 DOCX/PDF。
- ZMD 同步：更新项目文档导航、文件资产索引、脚本自动化导航和本变更索引。
- 验证：构建器结构检查通过；DOCX含34个内嵌图片、无外链图片且ZIP完整，PDF 63页并完成代表页视觉抽查。第一至第五章、软件代码和项目路线未改动。

### 2026-08-24 — 增加 CLI ASCII 启动界面

- 真实变更：`ss-screen --version` 改为输出纯 ASCII `SS-SCREEN` Logo 和 `SS-Screen version 1.0`；更新 CLI 回归测试、V1.0 手册版本示例和真实启动截图。
- ZMD 更新：同步 CLI、测试、项目文档、脚本自动化和本版本索引；软件功能、科学算法、版本号及图片总数不变。
- 验证：完整测试、Ruff、相关文件 Black 和 `pip check` 通过；手册构建器 `--check` 通过，DOCX 内嵌 32 张图且无外链，PDF 为 55 页，启动图完成视觉检查。

### 2026-08-21 — 补齐 V1.0 手册主要任务操作界面

- 真实变更：新增环境检查、MP 数据、condense 归档、MACE 驰豫、混合焓、声子、凸包和完整验收 8 张 CLI 界面；CLI 图增至 18 张，手册总图数增至 32 张，编制日期统一为 2026 年 8 月 21 日。
- 真实性边界：环境、condense 和混合焓界面由本次实际轻量命令生成；MP、MACE、声子和凸包界面显示真实 `--help` 与已有教学结果字段，未伪装为本次重新计算。
- 验证：构建器 `--check` 通过；DOCX 内嵌 32 张图像，PDF 56 页；新增代表页视觉检查无裁切、重叠和空白图。

### 2026-08-18 — 完善 V1.0 软著图文操作手册

- 真实变更：更新 V1.0 操作手册 Markdown，嵌入 `assets/copyright-v1/` 的 24 张真实 CLI/设计/流程/结果图，补充界面导航、软件结构、模块函数、算法、接口、数据字典和运行恢复设计；重新生成同名 DOCX/PDF。
- ZMD 更新：同步项目文档、脚本自动化、文件资产、目录树和本版本索引；Markdown 作为内容权威来源，DOCX/PDF 作为同源交付物。
- 验证：构建器结构检查通过；DOCX 的 V1.0 元数据、24 个内嵌图像、零外链图像和 ZIP 完整性通过；PDF 51 页并完成代表页视觉抽查。当前环境无 LibreOffice，Word/WPS 最终分页仍需人工复核。

### 2026-08-18 — 生成无前置标号的源程序 Word 材料

- 真实变更：扩展 `scripts/build_copyright_source.py`，新增 `docs/copyright-source/SS-Screen_V0.1.0_source_front2500_back2500_unlabeled.docx`；沿用正式包路径排序和前后各 2500 行边界，Word 正文仅保留源代码文本。
- ZMD 更新：同步文件资产总索引、项目文档、脚本自动化和本版本索引，并更新源程序材料目录说明。
- 验证：DOCX 正文恰为 5000 个段落，与源代码前 2500 行加后 2500 行逐行完全一致；99 个强制分页点对应每 50 行一页，前置选段编号、原文件行号、路径和分隔符计数为零；ZIP 完整性、重复构建 SHA-256、Ruff、Black 和 ZMD 链接检查通过。当前环境无 LibreOffice，未做最终分页渲染。

### 2026-08-18 — 扩写软著申请表主要功能栏

- 真实变更：新增 `scripts/update_copyright_application.py` 和 `docs/copyright-application/计算机软件著作权登记申请表_主要功能扩写.docx`；原附件只读保留，工作副本的主要功能正文扩写为 1281 个非空白字符。
- ZMD 更新：同步工作区目录树、文件资产总索引、项目文档、脚本自动化和本版本索引；申请表工作副本纳入项目文档导航。
- 验证：扩写内容覆盖当前 Stage 1--11，未把外部 DFT 或未来缺陷执行写成软件内置能力；连同栏目标识共 1297 个非空白字符，符合 500--1300 字范围。DOCX 仍为 1 个表格、36 行，ZIP 完整性、Ruff 和 Black 检查通过；当前环境无 LibreOffice，未进行逐页渲染。

### 2026-08-05 — 生成软著源程序前后各 2500 行

- 真实变更：新增 `scripts/build_copyright_source.py` 和 `docs/copyright-source/`；从 25 个 `src/ssscreen/**/*.py` 文件的 9944 行正式源码中，按路径稳定排序生成前 2500 行与后 2500 行的 PDF、文本和 manifest。
- ZMD 更新：同步工作区目录树、文件资产总索引、项目文档、脚本自动化和本版本索引；测试、脚本、文档、历史参考与生成数据明确不进入源程序选取范围。
- 验证：文本恰为 5000 行；PDF A4 纵向、每页 50 行、共 100 页，前后段各 50 页且不重叠；页眉的软件全称和版本为“新材料计算筛选软件 V0.1.0”；Ghostscript 成功解析全部页面，首、中、末页已视觉复核；构建脚本 Ruff 和 Black 通过。

### 2026-08-05 — 增加窄带隙与红外探测研发背景

- 真实变更：在 `V0.1.0` 软著登记手册第一章开头新增“1.1 研发背景”，补充带隙的高通量计算价值、截止波长近似关系、中波/长波红外带隙范围、窄带隙的暗电流风险、固溶体调控路径及软件研发必要性；原 1.1--1.6 顺延为 1.2--1.7。
- 配套更新：文档编制日期更新为 2026 年 8 月 5 日，附录 C.2 保留初稿记录并增加本次修订行；使用既有构建器重新生成同名 DOCX/PDF，文件路径和软件功能未变。
- 验证：源稿 1737 行、41558 字符、158 个标题、29 个表格和 63 个代码块；构建器结构检查通过，PDF 由 36 增至 37 个物理页，37 页全部非空，目录、新增背景页、截止波长公式、顺延小节和附录日期已视觉/文本提取复核。完整 pytest、Ruff、Black、字节码、`pip check` 和 347 个 ZMD 本地链接通过。著作权人占位文字仍保留一处，未创建 Git 提交。

### 2026-08-04 — 软著登记软件全称变更

- 真实变更：将 `V0.1.0` 软著登记手册 Markdown 和 `scripts/build_copyright_manual.py` 中的软件全称由“固溶体可调带隙材料筛选软件”统一改为“新材料计算筛选软件”，并重新生成同名 DOCX/PDF；简称、包名和版本不变。
- ZMD 更新：项目文档、脚本自动化和本版本索引同步登记新全称；文件路径和职责未改变，因此不重命名 `SS-Screen_V0.1.0` 交付物。
- 验证：登记版构建器结构检查通过；当前 Markdown/生成器及生成 DOCX/PDF 旧全称零残留，DOCX 元数据与 PDF 页眉均使用新全称。PDF 保持 36 个物理页，全页渲染无空白页，封面、正文页眉和末页版本表已视觉复核。完整 pytest、Ruff、Black、字节码、`pip check` 和 347 个 ZMD 本地链接通过。著作权人占位文字仍保留一处，未创建 Git 提交。

### 2026-08-04 — 交付 V0.1.0 软著登记操作手册

- 真实变更：新增 `docs/user-guide/SS-Screen_V0.1.0_软件著作权登记操作手册.md` 及同名 DOCX/PDF，以及 `scripts/build_copyright_manual.py`；手册固定为 `ss-screen 0.1.0`，覆盖 Stage 1--11 真实 CLI、输入输出、成功标准、质量控制和常见问题，不收录未实现接口。
- ZMD 更新：同步工作区目录树、文件资产总索引、项目文档、脚本自动化和本版本索引；明确 Markdown 为内容源、DOCX 为可编辑交付物、PDF 为已排页鉴别材料。
- 验证：源稿 1718 行、40441 字符、157 个标题、29 个表格和 63 个代码块；生成器结构检查通过，PDF 共 36 个物理页并全页渲染检查无乱码、遮挡、裁切或空白页。`--rights-holder` 临时构建的 DOCX/PDF 均出现测试主体名称且占位文字计数为零。新脚本 Ruff、Black 和字节码检查、完整 pytest、`pip check`、DOCX 元数据/页眉字段与 347 个 ZMD 本地链接均通过。著作权人尚为一处可检测占位文字，正式提交前必须替换并重新生成。未运行 notebook、DFT、MACE、声子、在线 MP 或 AiiDA daemon，未创建 Git 提交。

### 2026-08-04 — 软著登记操作手册编制要求调研

- 真实变更：`docs/PROJECT_LOG.md` 登记中国版权保护中心现行文档鉴别材料要求、命令行软件登记版手册建议及现有完整功能版手册的适用性审查；未修改现有手册、正式源码、测试、算法、依赖或数据。
- ZMD 更新：本页登记调研结论和后续登记版手册方向；没有新增、删除或移动真实资产，其他导航职责说明经核对无需变化。
- 验证：2026-08-04 只读核对中国版权保护中心登记指南/问题问答、中国政府网《计算机软件著作权登记办法》、当前手册和 `ss-screen 0.1.0` 版本；项目 Python 3.11.15 可用。未运行 notebook、DFT、MACE、声子或 AiiDA daemon，未创建 Git 提交。

### 2026-08-03 — Stage 12 统一端到端 CI 夹具

- 真实变更：新增 `tests/test_e2e_pipeline.py` 和 `tests/data/e2e/`；以三端元合成 rock-salt 输入真实执行轻量 Stage 1--11 CLI 文件链，动态生成确定性 Stage 7/9/10 证据，并在两个临时目录核对相同推荐。路线图 Stage 12、项目计划、README 和导师汇报同步为完成的首个可复现基线。
- ZMD 更新：同步目录树、资产索引、入口 README、测试文件/数据/数量、项目文档状态和本版本索引；当前基线为 25 个源码文件、21 个测试文件和 158 项测试。
- 验证：新测试单独通过并在普通 CPU 上约 7.5 秒完成；完整 158 项测试、全库源码/测试 Ruff、新测试 Black 和 `pip check` 通过。夹具共 4.5 KB，测试源码未引用 MACE、Phonopy、MP API、Torch、AiiDA、网络或子进程；338 个 ZMD 本地链接零失效，导师报告 302 行且相对链接零失效，旧状态扫描和 diff 检查通过。未运行 notebook、真实 MACE、声子、在线 MP、DFT 或 AiiDA daemon，未创建 Git 提交。

### 2026-08-03 — 更新 Stage 11 导师汇报

- 真实变更：更新 `docs/software_status_report_2026-08-04.md`，补充 Stage 11 可审计分类、L2--L6、默认阈值、Stage 5 输入连接、教学自动分类和轻量现场复现命令；校正文档数量及 Stage 7--11 开发工作树表述。
- ZMD 更新：`ZMD/04_项目文档与开发计划/README.md` 登记本次汇报内容同步；本页记录变更范围。
- 验证：报告共 297 行、31 个标题和 10 个成对代码围栏；8 个相对链接零失效，现场 Stage 11 命令引用的 8 个教学文件全部存在，旧状态表述扫描和 diff 检查通过。仅修改文档与 ZMD，未运行测试、notebook、MACE、声子、在线 MP、DFT 或 AiiDA daemon，未创建 Git 提交。

### 2026-08-03 — Stage 11 可审计综合推荐

- 真实变更：新增 `src/ssscreen/stability/recommendation.py`、`tests/test_stability_recommendation.py` 和 `docs/algorithm_recommendation.md`；扩展集中配置、stability 公共入口、顶层 CLI 与 CLI 测试；同步 README、项目计划/路线图、中文手册 Markdown/Word 构建版本和导师汇报。
- ZMD 更新：同步主数据流、目录树、资产索引、入口配置、源码总览、stability、CLI、测试、文档、手册构建器和本版本索引；当前基线为 25 个源码文件、20 个测试文件和 157 项测试。
- 验证：完整 157 项测试、全库 Ruff、涉及 Python 文件 Black、`pip check`、CLI 帮助和教程 Stage 11 冒烟通过；CaSe-CaS 为 promising/L5，CaTe-CaS 为 low-priority/L5。中文手册 V1.4 生成 81272 字节 DOCX，112 个标题、18 个表、50 个代码块且结构检查通过；334 个 ZMD 本地链接零失效，diff 检查通过。未运行 notebook、DFT、MACE、声子计算或 AiiDA daemon，未创建 Git 提交。

### 2026-08-03 — 导师软件阶段性汇报

- 真实变更：新增 `docs/software_status_report_2026-08-04.md`，汇总 SS-Screen 的科学问题、核心环境匹配方法、Stage 1–12 状态、工程验证、教学案例、科学限制、目标带隙产品方向和下一阶段决策问题，并提供 Bash 现场演示命令。
- ZMD 更新：`ZMD/04_项目文档与开发计划/README.md` 增加报告入口和同步说明；本页登记报告创建、表述边界与验证结果。
- 验证：报告 263 行，全部相对文件链接存在；报告和 ZMD 页面 `git diff --check` 通过。仅修改文档和导航，未运行 notebook、在线请求、DFT、MACE、AiiDA daemon 或完整测试套件。

### 2026-08-03 — 目标带隙检索与用户数据双入口设计

- 真实变更：`docs/PROJECT_LOG.md` 登记当前固定 pair 阈值与目标带隙产品需求之间的差距，定义 MP×MP、用户×MP、用户×用户检索范围，端元覆盖/组分预测/显式计算验证三级证据及预计算索引 + 增量上传的数据流；未修改正式源码、测试、算法、依赖或数据。
- ZMD 更新：`ZMD/04_项目文档与开发计划/README.md` 记录目标带隙查询、通用上传 schema 和混合匹配 MVP 方向；本页登记同步结果。该设计待正式规范和测试验证，不构成项目计划变更。
- 验证：只读核对当前 pair、gap feedback、MP/WBM 规范化与 CLI 契约，并检查 ZMD 本地链接和文档 diff；未运行 notebook、DFT、MACE、AiiDA daemon 或完整测试套件。

### 2026-08-03 — 新用户 Stage 1 至 Stage 10 教学运行

- 真实变更：在本地 `work/new-user-tutorial/` 生成完整教学运行与 `12_report/README.md` 审计报告；`docs/PROJECT_LOG.md` 登记阶段结果、能量分支和科研限制；`.gitignore` 新增 `/work/`，确保 9.9 MB 生成结构与计算结果不进入 Git。
- ZMD 更新：`ZMD/01_项目入口与配置/README.md` 登记 `work/` 本地运行职责和忽略规则；`ZMD/04_项目文档与开发计划/README.md` 登记教学演练状态；本页记录同步。生成目录不属于正式导航资产。
- 验证：真实 MP 三材料教学子集完成 2 对 SQS；5/5 严格 MACE 弛豫、2/2 混合焓、21/21 声子力任务、46/46 凸包分支竞争相和 2/2 严格凸包成功。关键产物 SHA、离线数据库 SHA、模型 SHA、链接和结果 schema 已复核；`pip check`、Ruff 与完整 151 项测试通过；未运行 notebook、DFT 或 AiiDA daemon，未创建 Git 提交。

### 2026-08-03 — 开源工作流框架与成熟软件架构调研

- 真实变更：`docs/PROJECT_LOG.md` 登记对 atomate2/jobflow、AiiDA、pyiron、Dagster、Prefect、Maggma、Snakemake、DVC 和 OPTIMADE 的对比调研，以及 SS-Screen 的成熟化分层架构与 Stage 1–5 垂直切片建议；未修改正式源码、测试、算法、依赖或数据。
- ZMD 更新：`ZMD/04_项目文档与开发计划/README.md` 记录建议的工作流控制层、执行适配器和 metadata/artifact 存储方向；本页登记同步结果。该建议待 ADR/PoC 验证，不构成正式项目计划变更。
- 验证：只读核对当前源码/计划和各项目官方资料，并检查 ZMD 本地链接及文档 diff；未运行 notebook、DFT、MACE、AiiDA daemon 或完整测试套件。

### 2026-08-03 — Stage 1 接入外部 MP 离线快照

- 真实变更：扩展 `src/ssscreen/data/mp.py`、Stage 1 CLI 和既有测试，离线查询显式限制非负 hull 能、排除 deprecated、只投影必要字段，并为 API/离线 `mp.df` 写入 DataFrame attrs 和默认 JSON provenance sidecar；同步 README、项目计划和中文手册 Markdown/Word。
- ZMD 更新：同步 data/CLI/测试/项目文档/手册构建器职责和本索引；外部 2.22 GB SQLite 数据库保持只读且未复制。
- 验证：外部数据库 `quick_check=ok`、SHA-256 为 `d54bca48d1e00bdfd8db7c1e5a7b5844ccb755b948335930f09fe85444a7ebb8`、155361 条且 ID 无重复；非 deprecated `e_hull<=0.01` 为 46675 条，所需结构/组成/带隙无缺失。真实 `mp-1672` 冒烟正确得到 CaS、2.3819 eV 带隙和 0 eV/atom hull 能，provenance 随 pickle 重载保留；完整 151 项测试、全库 Ruff、相关 Python 文件 Black、`pip check`、CLI 帮助、Word 手册结构和 diff 检查通过。手册构建脚本仅有既有 Black 排版差异。

### 2026-08-03 — pairwise-screening WBM 数据入口核查

- 真实变更：`docs/PROJECT_LOG.md` 登记对指定只读快照的资产盘点、当前 WBM extxyz 入口契约和下游 group 产物可用性；未修改正式源码、测试、算法、依赖或数据。
- ZMD 更新：`ZMD/04_项目文档与开发计划/README.md` 记录该外部快照不能作为 Stage 1 WBM 入口及 binary group JSON 的下游定位；本页登记同步结果。
- 验证：外部目录中未找到 `wbm-dataset.xyz`、summary、五个原始 step、DataFrame/SQLite/Parquet；60,225 个结构 JSON 不含 gap/hull/step 元数据且 ID 稀疏。当前加载器成功读取 binary group 为 222 组、952 成员和 437 个唯一 WBM ID；ternary group 仍命中已知 `Compositions` 兼容缺口。未运行 notebook、在线请求、DFT、MACE 或 AiiDA。

### 2026-08-03 — Stage 1 MP/WBM 数据准备度审查

- 真实变更：`docs/PROJECT_LOG.md` 登记 MP/WBM 读取链路、当前依赖/凭据状态、外部数据资产缺失和 WBM 原始构建/schema/provenance 风险；未修改正式源码、测试、算法、依赖或数据。
- ZMD 更新：`ZMD/04_项目文档与开发计划/README.md` 补充 Stage 1 外部数据与 WBM 严格校验缺口；本页登记同步结果。
- 验证：项目 Python 3.11.15、`ssscreen 0.1.0`、`mp-api 0.46.4`、`mp-offline 0.1.0`、`ase 3.26.0` 和 `pip check` 正常；MP/WBM/CLI 聚焦测试与 Stage 1 CLI 帮助通过。当前可见路径中未找到 MP `default.db`、WBM extxyz/summary/原始 step，也未配置 MP 在线凭据；未运行在线 MP、notebook、DFT、MACE 或 AiiDA。

### 2026-08-03 — 当前软件逻辑画布

- 真实变更：`docs/PROJECT_LOG.md` 登记基于真实源码、CLI 和 Stage 1–10 文件契约的会话内架构梳理；未修改正式源码、测试、算法、依赖或数据，Codex 会话画布不纳入仓库正式资产。
- ZMD 更新：`ZMD/04_项目文档与开发计划/README.md` 记录当前主链汇合/分叉关系；本页登记同步结果，其他源码、CLI 和测试职责说明经核对无需变化。
- 验证：项目环境为 Python 3.11.15、`ssscreen 0.1.0`；核对 24 个正式源码文件和当前 CLI 命令树。Playwright 在 736 px/328 px 内容宽度及浅色/深色主题下验证三种画布视图，节点文字、控件和连线无越界、重叠或穿越无关节点，交互无浏览器错误；325 个 ZMD 本地链接失效数为 0。未运行 notebook、DFT、MACE、AiiDA daemon 或完整测试套件。

### 2026-08-01 — Stage 10 离线 MP 竞争相来源

- 真实变更：扩展 `src/ssscreen/stability/competing.py`、`src/ssscreen/data/mp.py`、Stage 10 CLI 和测试，新增显式 `mp_offline` SQLite 查询、SQLAlchemy Row 解包、数据库 SHA/scope provenance 和最终凸包来源贯通；同步 README、算法说明、计划、路线图和中文手册 Markdown/Word。
- ZMD 更新：同步主数据流、入口环境、stability/CLI 职责、测试覆盖、文档状态、脚本版本和本索引；外部 2.1 GB SQLite 数据库未复制或修改。
- 验证：完整 151 项测试、全库 Ruff、本次生产代码/测试 Black、`pip check`、CLI 帮助、Word 手册结构和 325 个 ZMD 链接通过。只读 2.1 GB 离线库 Li-O 冒烟在 `e_hull<=0.05 eV/atom` 下查询并写出 18/18 个竞争相，零失败，数据库 SHA-256 为 `d54bca48d1e00bdfd8db7c1e5a7b5844ccb755b948335930f09fe85444a7ebb8`；临时产物已清理，未运行 MACE、DFT、notebook 或 AiiDA。

### 2026-07-31 — 外部高精度带隙任务与结果契约

- 真实变更：扩展 `src/ssscreen/pair/gap_export.py`、`gap_feedback.py` 和 CLI，新增版本化确定性任务 ID、结构/设置哈希、JSON/CIF/POSCAR 导出、结果/方法模板、规范化结果、拒绝行和审计报告；移除未实现的 `dft` extra；同步 README、算法说明、计划、路线图和中文手册 Markdown/Word。
- ZMD 更新：同步主数据流、入口依赖、pair/CLI 职责、测试覆盖、文档缺口和本版本索引。
- 验证：完整 146 项测试、生产代码/测试 Black、全库 Ruff、`pip check`、两个 CLI 帮助、Word 手册结构检查和 325 个 ZMD 本地链接通过；未运行 notebook、DFT 作业或 AiiDA daemon。手册构建脚本存在既有 Black 排版差异，本次只改一行版本号，未扩大机械格式化范围。

### 2026-07-31 — Stage 10 MP 竞争相与同 MACE 凸包

- 真实变更：新增 `src/ssscreen/stability/competing.py`、`tests/test_stability_competing.py` 和 `docs/algorithm_competing_phase_hull.md`；扩展通用弛豫任务、集中配置、stability 公共入口、四个 CLI 和已验证的 `[mp]` 依赖范围；同步 README、项目计划/路线图和中文手册 Markdown/Word。
- ZMD 更新：同步主数据流、入口依赖、目录树、资产索引、源码总览、stability、CLI、测试、文档缺口和本版本索引；当前基线为 24 个源码文件、19 个测试文件。
- 验证：完整 134 项测试、生产代码/测试/脚本 Ruff、涉及文件 Black、`pip check`、字节码、CLI 帮助、手册结构和 325 个 ZMD 链接通过；密钥字面量命中为 0。真实 MP API Ca-S 冒烟读取数据库 `2026.04.13` 的 31 条近凸包记录，30 条在显式 100 原子门槛内成功导出，1 条 104 原子结构被准确记录为 skipped，临时产物已删除。

### 2026-07-31 — Stage 9 MACE 声子谱

- 真实变更：新增 `src/ssscreen/stability/phonon.py`、`tests/test_stability_phonon.py` 和 `[phonon]` 依赖；扩展 MACE 单点能量/力接口、集中配置、stability 公共入口与四个 CLI；同步 README、计划/日志/路线及中文手册 Markdown/Word。
- ZMD 更新：同步主数据流、入口依赖、目录树、资产索引、源码总览、stability、CLI、测试、文档缺口和本版本索引；当前基线为 23 个源码文件、18 个测试文件。
- 验证：完整 124 项测试、全库 Ruff、本次涉及文件 Black、`pip check`、字节码编译、CLI 帮助和手册结构检查通过；A100 真实 MACE/Phonopy 冒烟完成 2/2 力任务并生成非空频带/DOS，最低频率为数值零点量级，临时输出已删除。

### 2026-07-30 — Stage 9 声子谱实现调研

- 真实变更：`docs/PROJECT_LOG.md` 记录指定 PDF、参考工程真实 Phonopy/VASP 案例、当前依赖缺口和 Stage 9 实施方案；未修改源码、依赖、模型或计算数据。
- ZMD 更新：`ZMD/04_项目文档与开发计划/README.md` 登记 Phonopy 有限位移 + MACE 力、后端中立 manifest 和 mesh 判据；本页登记同步记录。
- 验证：已核对 PDF 全部 9 页、参考工程 120 原子/198 位移案例、Phonopy 4.3 产物和官方 Phonopy 4.4/SeeK-path API；未运行实际声子或 DFT 任务。

### 2026-07-30 — Stage 8 MLP 混合焓

- 真实变更：新增 `src/ssscreen/stability/thermodynamics.py` 和 `tests/test_stability_thermodynamics.py`；扩展 SQS 实际组分、Stage 7 元数据、stability 公共入口与 CLI；同步 README、项目计划/日志、长期路线及中文手册 Markdown/Word。
- ZMD 更新：同步主数据流、目录树、资产索引、源码总览、stability、CLI、测试、文档缺口和本版本索引；当前基线为 22 个源码文件、17 个测试文件。
- 验证：完整 115 项测试、全库 Ruff、本次涉及文件 Black、`pip check`、CLI 帮助和手册结构检查通过；302 个 ZMD 本地链接失效数为 0。当前容器无 LibreOffice，本次未做 Word 逐页渲染复检。

### 2026-07-30 — 稳定性计算路径调研

- 真实变更：`docs/PROJECT_LOG.md` 记录当前 `e_hull` 初筛、SQS、MACE 弛豫与未实现的混合焓/凸包/声子边界；未修改源码、模型或计算数据。
- ZMD 更新：`ZMD/04_项目文档与开发计划/README.md` 登记审计结论；本页登记同步记录。
- 验证：已核对正式源码、单元测试、历史反钙钛矿 notebook 和只读 `solid-solutions-all` MACE/eSEN 稳定性参考实现。

### 2026-07-30 — Stage 7 MACE 弛豫和项目环境

- 真实变更：重建忽略的 Python 3.11.15 `.venv` 并安装经验证的 MACE/CUDA 运行时；新增 `models/README.md` 和忽略的 `models/mace-mpa-0-medium.model`；新增 `src/ssscreen/stability/mlp.py`、`relax.py` 和 `tests/test_stability_relax.py`；扩展 SQS manifest、CLI、配置、依赖、README、路线图、计划和中文手册。
- ZMD 更新：同步总数据流、目录树、资产索引、入口配置、源码总览、stability、CLI、测试、文档缺口和本版本索引。
- 验证：MACE-MPA-0-medium SHA-256 与只读来源一致；A100 单点及真实 CLI 两步全晶胞 FIRE 冒烟均返回能量、力和应力；完整 106 项测试、全库 Ruff、本次涉及文件 Black、手册结构检查和 296 个 ZMD 本地链接通过。全库 Black 26 仍有 3 个未修改既有文件的格式差异，详见项目日志。

### 2026-07-22 — 交付完整功能版中文用户手册

- 真实变更：新增 `docs/user-guide/SS-Screen_完整功能版_用户使用手册.md`、同名 `.docx`、`scripts/build_full_user_manual.py` 和 `docs/superpowers/plans/2026-07-22-full-user-manual.md`；Markdown 是内容权威来源，Word 是正式交付物。
- ZMD 更新：同步文档计划、脚本自动化、文件资产、目录树和本版本索引；当前缺口不再列“完整 CLI 用户教程”。
- 验证：114 个标题、17 个表格、44 个代码块、16 个预期接口提示；Word 共 46 页，全部逐页复检；无障碍审计高/中/低风险均为 0，A4 分节与全部表格几何检查通过，独立编号列表均从 1 开始；97 项测试、生产代码 Ruff、diff 检查通过，285 个 ZMD 本地链接失效数为 0。

### 2026-07-22 — 完整功能版用户手册设计

- 真实变更：`docs/superpowers/specs/2026-07-22-full-user-manual-design.md` — 新增中文手册设计，定义科研用户受众、完整阶段数据流、当前/预期 CLI 边界、双格式交付和验收标准。
- ZMD 更新：`ZMD/04_项目文档与开发计划/README.md` — 增加设计文件入口并说明正式手册尚未创建；本页登记同步记录。
- 验证：检查设计中无 `TODO`/`TBD`，当前命令清单与 `src/ssscreen/cli/app.py` 和 CLI 导航一致，预期命令均标明当前尚未实现。

### 2026-07-22 — WSL 工作区运行验证

- 真实变更：未修改源码、测试或配置；CLI 冒烟测试输出写入 `/tmp/ss-screen-workspace-check.csv`。
- ZMD 更新：本页登记本次工作区运行验证结果，其他路径与职责说明无需变化。
- 验证：Python 3.11.15、`ss-screen 0.1.0`；核心及 MP/WBM/condense/SQS 可选依赖导入成功；`pip check` 无损坏依赖；实际 `pair` 命令生成预期的 CaS–CaSe 材料对；完整 97 项测试通过；Ruff 通过；277 个 ZMD 本地链接失效数为 0。

### 2026-07-22 — 建立 ZMD 导航

- 新建总入口、工作区目录树、资产索引、推荐阅读路径和同步规则。
- 建立入口配置、正式源码、测试、文档计划、历史资料、脚本自动化分区。
- 源码分区细化为 `data`、`pair`、`stability` 和 `cli`。
- 所有真实内容保持原路径，没有移动、重命名、复制或删除。
- `AGENTS.md` 加入“先读 ZMD、修改后同步 ZMD”的强制流程。
- 验证结果：17 个 Markdown 导航文件包含 277 个有效本地链接，失效链接为 0；34 个正式源码/测试 Python 文件均已登记；完整 97 项测试通过；Ruff 检查通过。

## 后续记录格式

每次真实文件发生变化后，在本页顶部的“同步记录”区域新增：

```markdown
### YYYY-MM-DD — <变更主题>

- 真实变更：`path/to/file` — <新增/修改/移动/删除及内容>
- ZMD 更新：`ZMD/...` — <更新了哪些路径、职责或状态>
- 验证：<链接检查、测试、Ruff 或其他证据>
```

同一天的同一主题可以合并；不同主题必须分开记录。不得只写“已同步”而不列出真实文件和导航页面。

## 版本命名规则

- 导航和文档避免“最新版”“最终版”“新版本”等会过时名称。
- 需要保留多版本时，使用 `v0-原型`、`v1-基础框架`、`v2-关键扩展` 等稳定语义。
- 当前主线通过 README 和索引明确指出，不依赖文件名中的“当前”。
- 历史资料已有的原始名称保持不变，ZMD 只负责解释其地位。

## 同步检查入口

- [ZMD 同步更新规则](../00_总览与使用规则/ZMD同步更新规则.md)
- [文件资产总索引](../00_总览与使用规则/文件资产总索引.md)
- [工作区目录树](../00_总览与使用规则/工作区目录树.md)
- [`docs/PROJECT_LOG.md`](../../docs/PROJECT_LOG.md)

### 2026-11-01 — Stage 13探测器性能评估（展示与预筛）

- 新增工程树Stage 13及GUI独立面板，保存和展示可追溯的带隙/截止波长结果；缺失器件数据时不造数。
- 新增测试`tests/test_detector.py`、文档`docs/gui_stage13_detector.md`，并更新GUI导航。源码提交由用户自行完成。
