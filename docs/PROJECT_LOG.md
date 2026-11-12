## 2026-11-13 — clone 后一键启动 10 μm 演示

**本次工作目标：** 在执行命令的目录准备独立工作区，自动打开 01。

**已完成：**
- 新增 start-10um.cmd、scripts/start-10um.ps1、scripts/start-10um.sh 和 scripts/start_10um.py。使用固定校验值获取发行附件，准备两个环境、解包 3,216 个工程文件及数据库，设置 WSL 后端并启动 GUI。同步 README、复现说明和路径导航。
- 实测 Windows 中文路径首次安装，验证 GUI 停在 01、数据库定位及 WSL 后端。WSL 再次调用复用同一数据库和工程，无现场计算。WSL 相关回归 9 通过。

**决策 / 计划变更：** 首次依赖联网及已配置的默认 Ubuntu WSL；Windows 使用非 editable 安装，避免中文路径的 .pth 编码问题。

**下一步：** 在接收方机器上按首页命令复现。

**阻塞项 / 上游问题：** 异机试用待进行。

## 2026-11-01 — 新增GUI Stage 13探测器性能预筛与演示

**本次工作目标：** 在现有Stage 12之后展示探测器应用性能指标及数据来源。

**已完成：**
- 新增`src/ssscreen/detector.py`和`src/ssscreen/gui/detector_page.py`；修改GUI阶段元数据、工程树和图标。
- 使用名义截止波长与现有稳定性证据做展示和预筛；器件级指标仅接受外部数据输入；演示示例明确标注非真实。
- 新增`tests/test_detector.py`及`docs/gui_stage13_detector.md`，同步ZMD页面。

**决策 / 计划变更：** Stage 13为GUI只读结果与外部器件证据关联，不新增科研计算CLI。

**下一步：** 在具有PySide6的项目环境中进行GUI交互冒烟测试，补充实际器件指标及来源数据。

**阻塞项 / 上游问题：** 当前归档未附带可运行的项目`.venv`及真实Stage 12结果，需在本地安装环境复核。

# PROJECT_LOG.md — Cross-session project log for `ss-screen`

> **Purpose:** Keep this long-running project on track across many sessions.
> Append a dated entry at the end of every work session (newest first).
> This file + `PROJECT_PLAN.md` + `AGENTS.md` are the single source of truth
> for *where we are* — do not rely on conversation history surviving.

**Read first at the start of every session:** `AGENTS.md` → this file → `PROJECT_PLAN.md`.

## 2026-10-15 — 视图入口放入工程工具栏

**本次工作目标：** 让“视图”与“新建工程”同一行，取消额外的顶层菜单行。

**已完成：**
- 更新`src/ssscreen/gui/app.py`：工具栏新增“视图”即时下拉按钮，承载原有字号子菜单。
- 更新现有字体测试以验证无独立菜单栏、入口位于工程工具栏；同步GUI使用说明和ZMD。

**决策 / 计划变更：** 以工具栏下拉菜单承载视图偏好，保留字号自动记忆与恢复功能。

**下一步：** 重启GUI，从与“新建工程”同排的“视图”选择字号。

**阻塞项 / 上游问题：** 无。

## 2026-10-15 — 调整字号设置入口

**本次工作目标：** 按用户样式反馈把字号设置移至菜单栏，核实并保留原有产品标识。

**已完成：**
- 更新`src/ssscreen/gui/app.py`：新增“视图 → 界面字号”9--18 pt单选菜单及恢复默认动作，移除标题条字号控件；持久化和布局联动继续生效。
- Git历史确认`SS-SCREEN`标识从`900c758`最初GUI提交已存在，本轮保持其样式。
- 更新`tests/test_gui_appearance.py`和`docs/gui_integration_notes.md`；6项Windows Qt测试、Ruff、Python编译通过，并检查菜单和主界面截图。

**决策 / 计划变更：** 本轮仅调整显示偏好的入口，不重新设计历史产品标识。

**下一步：** 重启GUI，通过“视图 → 界面字号”调整文字大小。

**阻塞项 / 上游问题：** 无新增阻塞；WSL实际工作副本仍为`/mnt/d/WorkSpace/OtherProjects/ss-screen`。

## 2026-10-14 — 可记忆的 GUI 字号与布局适配

**本次工作目标：** 提供不同屏幕上的字号设置，并同步处理大字号下的工具栏、表格和参数布局。

**已完成：**
- 新增 `src/ssscreen/gui/appearance.py`：9--18 pt范围、无效设置回退、字体层级转换、表格与控件尺寸适配。
- 更新 `src/ssscreen/gui/app.py`：顶部字号与恢复按钮、Qt设置持久化、工具栏溢出菜单、属性/工作区滚动、纵向属性表单；MatterViz同步缩放，并保留高DPI分数缩放。
- 新增 `tests/test_gui_appearance.py`；Windows Qt在100%、125%、150%、200%缩放下分别6项通过，核心174项通过；截图检查1366×768/14pt、1024×768/18pt。

**决策 / 计划变更：** 字号为本机显示偏好，不写入科学参数或`.ssproject`；宽结果表在大字号时使用滚动查看，保持数值可读性。

**下一步：** 用户重启GUI后在顶部调整字号，在实际不同显示器上复核清晰度与跨屏切换。

**阻塞项 / 上游问题：** 当前WSL `.venv`未安装PySide6，GUI检查使用已有Windows解释器；WSL实际副本仍为`/mnt/d/WorkSpace/OtherProjects/ss-screen`。截图验证无法替代不同物理显示器的清晰度检查。

## 2026-09-28 — 修正竞争相表格和 MatterViz 页面填充

**本次工作目标：** 解决 Stage 11 表格内容被挤压、视觉上近似空白，以及部分 MatterViz 只占半个工作区的问题。

**已完成：**
- 更新 `src/ssscreen/gui/visualization.py`：竞争相表格显示 28 条记录计数，结构 ID 列自适应填充，其他列使用稳定宽度，并格式化角色、目标标志和凸包距离。
- Stage 10 MatterViz 从右侧半栏调整为独立完整标签页；Stage 10/11 WebEngine 控件采用扩展尺寸和不可折叠布局。
- 更新 `gui-matterviz/src/style.css` 并重建 `src/ssscreen/gui/matterviz_dist/`，使根容器与 canvas 填满 QtWebEngine 可用区域。
- 1280×760 页面验证：竞争相 28 行、声子 3 行，两个 MatterViz 页面均获得约 1256×691 内容区域；Ruff、`py_compile`、项目文件测试和前端构建通过。

**决策 / 计划变更：** 结果页优先使用完整标签页承载三维晶体，避免与数据表或图像强制并排导致显示面积不足。

**下一步：** 用实际 Windows GUI 重新打开示例 `.ssproject`，人工检查不同窗口尺寸下的晶体交互和表格可读性。

**阻塞项 / 上游问题：** MatterViz 0.7.0 高级控制侧栏仍因上游 `svelte-widgets` 兼容问题保持关闭，不影响核心三维视图。

## 2026-09-27 — 排除 MatterViz 本地 npm 依赖

**本次工作目标：** 防止 `gui-matterviz` 本地安装依赖进入版本库，同时保留可复现构建所需源码。

**已完成：**
- 更新 `.gitignore`，新增 `/gui-matterviz/node_modules/` 精确忽略规则。
- 确认 Svelte 源码、`package.json`、`package-lock.json`、公共资源和 Vite 配置仍由 Git 发现。
- 同步更新 `ZMD/01_项目入口与配置/README.md` 与 `ZMD/07_版本与变更索引/README.md`。

**决策 / 计划变更：** 不忽略整个 `gui-matterviz/`，因为它包含内嵌 MatterViz 的权威前端源码和可复现依赖锁；只排除约 162 MB 的可重新安装依赖。

**下一步：** 提交代码时纳入 `gui-matterviz` 源码和 `src/ssscreen/gui/matterviz_dist` 分发资源，不纳入 `node_modules`。

**阻塞项 / 上游问题：** 无。

## 2026-09-27 — 集成 GUI 可视化、单文件项目与 SSH 探测

**本次工作目标：** 在不启动真实远端作业的前提下，完成桌面端结果可视化、CPU/GPU 选择、参数中文化和 `.ssproject` 单文件项目原型。

**已完成：**
- 新增 `src/ssscreen/gui/project_file.py` 与 `tests/test_gui_project_file.py`，实现 Stage 01--12 ZIP64 项目容器、SHA-256 清单、安全解包、原子保存及篡改检测；真实算例 187 个制品回读通过。
- 新增 `src/ssscreen/gui/visualization.py` 与 `gui-matterviz/`，Stage 08/10/11 可显示 MatterViz 晶体、声子状态/band/DOS、竞争相表格和三元组成图；MatterViz 构建资源已进入 wheel。
- 更新 `src/ssscreen/gui/app.py` 与 `metadata.py`：加入 `.ssproject` 打开/保存、中文参数标签、MACE CPU 默认设备、可视化路由和 SSH 只读环境探测。
- 核心 174 项 pytest、目标 Ruff、MatterViz production build、Windows headless GUI 数据加载和真实浏览器 WebGL 验收通过。

**决策 / 计划变更：** SSH 本轮只验证认证、远端 Python/`ss-screen` 和工程目录，不实现任务提交/轮询/停止/下载；`.ssproject` 不保存 API Key。MatterViz 0.7.0 高级控制面板因上游 `svelte-widgets` 多选默认值异常暂时关闭，保留核心三维交互。

**下一步：** 获得服务器测试账号后设计并验证远端作业 ID、状态文件、断线重连、增量日志、结果下载和安全停止协议；再补一条真实服务器端到端冒烟测试。

**阻塞项 / 上游问题：** AGENTS 指定的 `/home/zuolong/projects/ss-screen-learning-20260722` 在当前 WSL 不存在，本次按实际仓库 `/mnt/d/WorkSpace/OtherProjects/ss-screen` 的完整 `.venv` 工作；尚无 SSH 服务器地址/账号，无法验证真实远端认证和调度状态。

## 2026-09-18 — 调整声子输入残余力默认阈值

**本次工作目标：** 将声子流程的 `max-input-force` 默认值从 `0.01` 调整为 `0.02 eV/Angstrom`。

**已完成：**
- 更新 `src/ssscreen/config.py`：`PhononSettings.max_input_force` 默认值改为 `0.02`，CLI 与 GUI 的声子命令统一继承。
- 更新 `src/ssscreen/gui/metadata.py`：声子谱一步式运行页面的 `--include-endmembers` 默认勾选。
- 同步更新 GUI、stability 的 ZMD 导航与版本变更索引。

**决策 / 计划变更：** 仅放宽声子输入结构的残余力准入阈值，不改变虚频判据、位移幅度或 MACE 驰豫参数。

**下一步：** 重启 GUI 后确认声子一步式运行命令预览显示 `--max-input-force 0.02`。

**阻塞项 / 上游问题：** 无。

## 2026-09-17 — 优化 GUI 后段流程与推荐报告展示

**本次工作目标：** 按用户现场演示反馈，简化 GUI 后段命令、修正端元驰豫选项歧义，并增强运行状态与推荐结果可读性。

**已完成：**
- 更新 `src/ssscreen/gui/metadata.py`：隐藏 Stage 10 的 `phonon-export`、`phonon-forces`、`phonon-collect` 和 Stage 11 的 `competing-export`、`competing-relax`、`convex-hull`，GUI 只保留当前演示使用的一步式 `phonon-run` 与 `phase-diagram`。
- 更新 `src/ssscreen/gui/app.py`：布尔选项不再显示 `--include-endmembers / --no-include-endmembers` 双选项标签；`--include-endmembers` preset 默认勾选并会正确写入命令。
- 新增 Stage 12 结果报告页：读取 `12_recommend/recommendation_report.md` 进行 Markdown 预览，并把 `recommendations.csv` 与 `06_pair`、`07_sqs`、`09_mixing`、`10_phonon`、`11_phase` 关键证据合并成候选表，展示材料对、结构文件、gap、混合焓、声子、凸包、风险和下一步建议。
- 工具栏新增运行状态文本和不确定进度条；任务运行时显示正在计算和最新输出摘要，结束后隐藏进度条。

**决策 / 计划变更：**
- GUI 面向当前整套演示流程隐藏拆分调试命令；CLI 仍保留这些命令供开发或排错使用。

**下一步：** 重启 PyCharm GUI 后，从 Stage 08 起默认端元驰豫会勾选；Stage 12 可直接查看 Markdown 报告和合并证据表。

**阻塞项 / 上游问题：** 本次未改变科学算法，未运行 DFT、AiiDA 或 notebook。

## 2026-09-16 — 修正 GUI 阶段默认路径归一化

**本次工作目标：** 解决 GUI 中结构匹配等阶段仍可能带入 `src/ssscreen/gui/...` 旧子目录路径，导致后端找不到阶段产物的问题。

**已完成：**
- 更新 `src/ssscreen/gui/app.py`：新增工程路径显示/解析归一化，若界面残留 `src/ssscreen/gui/01_dataset`、`03_condensed` 等旧路径，会自动折回项目根目录下的 `01_dataset`、`03_condensed`。
- 结构匹配页的默认归档路径和旧路径追加场景均验证为 `03_condensed/local`；从 `src/ssscreen/gui` 启动 GUI 时活动工程仍识别为仓库根目录。
- 左侧工程树 Stage 03/04 状态统计补充 `03_condensed/local`，避免本地结构归档已经生成但界面仍显示未准备。
- 运行后端新增 WSL 自动选择模式：前中段和 SQS 默认使用 `.venv`，MACE relax、phonon 和 phase-diagram 使用 `.venv-mlp`；若误选 `.venv-mlp` 运行 SQS，GUI 会自动改用 `.venv`，避免 NumPy 2 pickle 在 NumPy 1.26 MACE 环境中读取失败。
- 已用 `.venv` 复跑 `stability sqs-generate`，输出 `SQS input summary: written=1 skipped=0 manifest=07_sqs/sqs_manifest.jsonl`。

**决策 / 计划变更：**
- 无科学流程变化；本次只修正 GUI 层路径展示、解析和状态统计。

**下一步：** 重启 PyCharm 中的 GUI 后，右侧运行后端保持默认“WSL Python / 自动选择”；从 Stage 08 MACE 驰豫开始会自动切到 `.venv-mlp`。

**阻塞项 / 上游问题：** WSL 启动时仍会打印非致命 localhost/NAT 编码警告；本次未运行 MACE、phonon、MP API 或 DFT。

## 2026-09-15 — 补跑 MP API 竞争相凸包

**本次工作目标：** 在不重跑前面阶段的前提下，基于已有 MACE relaxation 结果补跑 Stage 11 在线 MP API 竞争相与同 MACE 能量基准 convex hull。

**已完成：**
- 第一次使用默认 API 超时输出到 `work/real-pbe-mace-20260914-run4/11_phase_api/`，MP 查询 `Ca-Se-Te` 体系 read timeout，结果为 `missing_elemental_reference`，未得到可用 hull。
- 第二次使用 `--thermo-type GGA_GGA+U --api-timeout 180` 输出到 `work/real-pbe-mace-20260914-run4/11_phase_api_retry/`，MP API 查询成功，获取 25 个竞争相，25 个竞争相 MACE relaxation 均可用。
- 得到真实 `phase_stability.csv`：CaSe-CaTe SQS 的同 MACE 能量基准 hull distance 为 `0.3497941494 eV/atom`，`hull_signal=unstable`，`competing_set_complete=True`，MP database version 为 `2026.04.13`。
- 使用真实 API hull 证据重新生成 `work/real-pbe-mace-20260914-run4/12_recommend_api/` 推荐报告，结果仍为 `low-priority`，证据等级提升为 L5，风险包含 `phase:above_low_priority_threshold`。
- 更新 `docs/real_vasp_mace_pipeline_2026-09-14.md` 和 `docs/gui_full_pipeline_runbook_2026-09-14.md`；GUI Stage 11 默认参数补充 `--thermo-type GGA_GGA+U --api-timeout 180`。

**决策 / 计划变更：**
- 当前演示链路不再把 `mp_offline` 作为硬阻塞；在线 MP API 已能补齐真实竞争相凸包证据。离线数据库只作为后续可复现/批量运行优化。

**下一步：** 从 GUI 按全流程操作单复跑时，Stage 11 使用 `.venv-mlp`、MP API Key、`GGA_GGA+U` 和 180 秒 API timeout；汇报时说明 CaSe-CaTe 目前同时有 phonon unstable 和 hull unstable 两个负向信号。

**阻塞项 / 上游问题：** Stage 11 在线结果依赖 Materials Project 当前数据库和网络状态；未运行 DFT 或 AiiDA。缺陷证据仍未接入。

## 2026-09-14 — 调整 GUI 默认参数并生成全流程操作单

**本次工作目标：** 将 GUI 默认选项调整为当前 CaS/CaSe/CaTe 真实 VASP + MACE + MP API 演示链路可直接使用的参数，并生成逐步操作 Markdown。

**已完成：**
- 更新 `src/ssscreen/gui/metadata.py` 与 `src/ssscreen/gui/app.py`：默认本地结构输入切换到 PBE relaxed 结构，结构描述归档默认 `03_condensed/local`，gap / pair / SQS / MACE / mixing / phonon / phase / recommend 默认路径统一为当前可跑通链路；MACE 默认使用 `data/mace-mpa-0-medium.model`、`cuda:0`、`float32`，phase 默认 `--mp-backend api`。
- 更新 `src/ssscreen/cli/app.py`：Materials Project API Key 读取改为优先使用 `MP_API_KEY` 环境变量，缺失时才交互提示；GUI 右侧 Properties 注入 Key 后可运行 Stage 11，不会卡在隐藏输入提示。
- 新增 `data/CaS_CaSe_CaTe_PBE_relaxed_CONTCAR/`，只放三个 PBE relaxed 结构，避免完整 VASP 结果目录中的 `POSCAR` 和 `CONTCAR` 被递归重复导入。
- 新增 `docs/gui_full_pipeline_runbook_2026-09-14.md`，列出 PyCharm 启动、WSL 后端切换、每个 GUI 节点的具体选择、默认参数和最终输出文件。
- 更新 `ZMD/02_正式源码/gui.md`、`ZMD/04_项目文档与开发计划/README.md` 和 `ZMD/07_版本与变更索引/README.md`。

**决策 / 计划变更：**
- 当前 GUI 现场演示以 repo 根目录作为活动工程，使用 `01_dataset` 到 `12_recommend` 作为被 `.gitignore` 忽略的阶段输出目录。
- 真实 VASP gap 收集默认读取已整理好的 `work/real-pbe-mace-20260914-run4/05_gap/vasp_by_task_id`，因为新默认导出的 task-id 已验证与该目录完全匹配。

**下一步：** 用户可按 `docs/gui_full_pipeline_runbook_2026-09-14.md` 从 GUI 完整跑一遍；若 Stage 11 因网络或 MP 服务失败，可单独重跑 `phase-diagram --mp-backend api`，不需要重跑前面阶段。

**阻塞项 / 上游问题：** 本次没有重跑 GPU MACE、phonon 或 MP API phase 全流程；只验证前中段默认链路和 gap 收集/校验/pair。Stage 11 在线运行仍依赖 MP API 服务和本地网络。

## 2026-09-14 — 校验 MP API Key 可用于当前项目

**本次工作目标：** 只检查当前项目中涉及 Materials Project API 的入口，不重跑完整流程，并更新真实 VASP + MACE 流程记录。

**已完成：**
- 检查 `data/API Key.txt`：文件存在、内容非空；未在日志或文档中记录具体 Key。
- 确认当前 `.venv` 中 `mp_api.client.MPRester` 可导入；此前最小 live 查询 `CaSe` 返回 2 条 MP summary 文档，说明该 Key 可用于当前项目在线 MP 后端。
- 审计 MP API 使用位置：`src/ssscreen/data/mp.py` 的 `dataset mp --backend api`、`src/ssscreen/stability/competing.py` 的 `--mp-backend api`、`src/ssscreen/cli/app.py` 的隐藏 Key 提示，以及 `src/ssscreen/gui/app.py` 的当前子进程环境注入。
- 更新 `docs/real_vasp_mace_pipeline_2026-09-14.md`，将 Stage 11 状态修正为“`mp_offline` 仍缺失，MP API Key 已验证可用，但本轮尚未补跑 API 后端 phase-diagram”。

**决策 / 计划变更：**
- 在线 MP API 现在可作为下一步补跑 Stage 10/11 竞争相与 convex hull 的可用路径；若需要离线可复现，仍需同事提供 `mp_offline` SQLite 数据库。

**下一步：** 用户确认后，可只基于 `work/real-pbe-mace-20260914-run4/08_relax/relaxation_results.jsonl` 补跑 `stability phase-diagram --mp-backend api`，不需要重跑前面所有阶段。

**阻塞项 / 上游问题：** 本次未重跑 phase-diagram、MACE、phonon、DFT、notebook 或 AiiDA daemon；当前报告中的 convex hull 证据仍是缺失状态，直到 API 后端 phase-diagram 实际跑完。

## 2026-09-14 — 真实 VASP + MACE 流程验证

**本次工作目标：** 使用同事提供的 PBE VASP 带隙结果和 `data/mace-mpa-0-medium.model` 重新跑通真实 gap 校验、MACE 后段和推荐报告，并整理交接文档。

**已完成：**
- 校核 `data/CaS_CaSe_CaTe_PBE_final_bandgap_calculations/`：CaS/CaSe/CaTe 均有 `vasprun.xml`、`OUTCAR`、`EIGENVAL`、`CONTCAR` 等；VASP 均收敛，PBE、`ENCUT=550`、`ISPIN=1`、无 SOC。
- 使用 `work/real-pbe-mace-20260914-run4/` 从 PBE relaxed `CONTCAR` 重新跑通 Stage 01--05、VASP gap collect/validate、manifest gap validate、pair、SQS、MACE relaxation、mixing enthalpy、phonon 和 recommendation。
- 结果：manifest 口径得到 CaSe-CaTe 一对；MACE relaxation 三条记录均 `usable_for_thermodynamics=True`；混合焓 `26.9009 meV/atom`；phonon 判定 `unstable`；推荐报告给出 `low-priority`。
- 新增 `docs/real_vasp_mace_pipeline_2026-09-14.md`，并更新 `ZMD/04_项目文档与开发计划/README.md` 与 `ZMD/07_版本与变更索引/README.md`。

**决策 / 计划变更：**
- 后续真实稳定性链路应使用 VASP PBE relaxed `CONTCAR`，而不是最初 POSCAR；初始 POSCAR 在 MACE relaxation 后体积质量控制失败。
- CaTe gap 采用同事 manifest 口径：`gap_eV=0.0`、`signed_gap_eV=-0.0143`；直接解析 `vasprun.xml` 会得到小正 gap `0.0064 eV`，仅作为对照保留。

**下一步：** 使用已验证的 MP API Key 补跑 Stage 10 competing phase / convex hull，或获取 `mp_offline` SQLite 数据库后走离线后端；对 CaSe-CaTe 的 phonon 虚频用更大超胞或 DFT 进一步复核。

**阻塞项 / 上游问题：** `mp_offline` 数据库仍缺失；MP API Key 已验证可用，但真实 API 后端 convex hull 尚未补跑；缺陷证据仍未接入。本次未运行 DFT 作业或 AiiDA daemon，只读取同事已有 VASP 结果。

## 2026-09-12 — 修复 GUI 组成筛选路径与 WSL 日志可读性

**本次工作目标：** 解决组成筛选页继续带入旧 `src/ssscreen/gui/01_dataset/...` 路径、缺失 `mp.df/wbm.df` 路径报错，以及 WSL 日志乱码影响阅读的问题。

**已完成：**
- 更新 `src/ssscreen/gui/app.py`：组成筛选页只自动加入真实存在的 `01_dataset/*.df`，刷新时清理旧子目录默认路径；发往 WSL 的相对路径统一把 `\` 转成 `/`；WSL localhost/NAT 启动警告在日志中压缩为英文提示。
- 更新 `.gitignore`，忽略工程根下 `01_dataset/` 到 `12_recommend/` 的 GUI/CLI 运行产物目录。
- 更新 `docs/gui_wsl_poscar_demo_runbook_2026-09-12.md`、`ZMD/02_正式源码/gui.md` 和 `ZMD/07_版本与变更索引/README.md`。

**决策 / 计划变更：** GUI 默认不再把不存在的 `mp.df/wbm.df` 加入组成筛选命令；没有 DataFrame 时应先完成 Stage 01 或手动添加真实文件。

**下一步：** 在 GUI 中重启后从 Stage 01 到 Stage 05 按默认路径演示；后续收到真实 VASP 结果后再验证 gap 回填和后段稳定性流程。

**阻塞项 / 上游问题：** OpenBabel Python bindings 仍是可选缺口，condense 会显示非致命 warning；真实 VASP gap、MACE checkpoint 和 `mp_offline` 仍需同事提供。

## 2026-09-12 — 修复 GUI 直接启动时 WSL 工程根目录识别

**本次工作目标：** 解决 PyCharm 直接运行 `src/ssscreen/gui/app.py` 后，GUI 在 WSL 后端误从 `src/ssscreen/gui` 子目录激活 `.venv` 的问题。

**已完成：**
- 更新 `src/ssscreen/gui/app.py`，新增 `_find_project_root()`；启动默认工程和 WSL 自动工程路径都会向上识别 `.ssscreen-project.json`、`.git` 或含 `src/ssscreen` 的 `pyproject.toml`。
- 更新 `ZMD/02_正式源码/gui.md` 和 `ZMD/07_版本与变更索引/README.md`，记录 PyCharm 直接启动与 WSL 后端路径修复。

**决策 / 计划变更：** 无科学路线变化；该修复只改变 GUI 默认工程根目录推断，仍然由真实 CLI 执行后端流程。

**下一步：** 重新启动 GUI 后，保持右侧 `WSL 工程路径` 为空，使用 `WSL Python / .venv` 再运行本地 POSCAR 导入；预期命令会进入 `/mnt/d/WorkSpace/OtherProjects/ss-screen` 后再激活 `.venv`。

**阻塞项 / 上游问题：** WSL 仍会输出一段 localhost/NAT 编码警告，但此前已验证命令 exit code 为 0 时不影响流程。

## 2026-09-12 — 整理 GUI/WSL/POSCAR 现场演示 runbook

**本次工作目标：** 将当前可实际运行和可向同事汇报的 GUI + WSL + POSCAR 流程整理为可照着操作的过程文件。

**已完成：**
- 新增 `docs/gui_wsl_poscar_demo_runbook_2026-09-12.md`，记录 PyCharm 启动 GUI、WSL 后端选择、本地 POSCAR 导入、组成筛选、结构描述、结构匹配、gap 任务导出、CLI 备用命令、同事材料清单和汇报建议。
- 更新 `ZMD/04_项目文档与开发计划/README.md` 和 `ZMD/07_版本与变更索引/README.md`，登记该现场演示 runbook。

**决策 / 计划变更：**
- 现场演示建议停在真实 gap 任务导出交接点；Stage 06 以后可展示已联调产物，但必须明确当前后段结果是 fixture，不作为真实材料结论。
- 当前 WSL 实际演示路径使用 `/mnt/d/WorkSpace/OtherProjects/ss-screen`；历史 AGENTS.md 中的 `/home/zuolong/projects/ss-screen-learning-20260722` 当前不存在，后续若迁移到 WSL 原生目录需同步文档。

**下一步：** 等同事提供 VASP gap 结果、计算方法说明、可选 metadata、MACE checkpoint 和 MP 离线/API 数据后，重新从 gap-validate 开始跑真实后段流程。

**阻塞项 / 上游问题：** 缺真实 VASP gap 结果、MACE checkpoint、`mp_offline` 包/数据库；当前未运行 DFT、notebook、MACE、Phonopy 或 AiiDA daemon。

## 2026-09-12 — 整理当前能力与同事交接清单

**本次工作目标：** 将当前 GUI/CLI/WSL/POSCAR/PyTorch 能力、已测试方法和需同事提供材料整理为 Markdown 交接文档。

**已完成：**
- 新增 `docs/current_capability_and_handoff_2026-09-12.md`，列出 GUI 可运行范围、GUI 调 WSL 后端、POSCAR 文件夹 Stage 01 输入、POSCAR 流程跑通范围、PyTorch/CUDA/MACE/phonopy 环境、具体测试方法、仍非真实科研结果的部分和需同事提供的 VASP/metadata/MACE/mp_offline/WBM/OpenBabel 材料。
- 更新 `ZMD/04_项目文档与开发计划/README.md` 和 `ZMD/07_版本与变更索引/README.md`，登记该交接文档入口和同步记录。

**决策 / 计划变更：** 无科学路线变化；该文档是对 2026-09-11 已验证状态的沟通整理，不新增代码能力。

**下一步：** 根据同事返回的真实 VASP 结果、metadata、MACE checkpoint 和 `mp_offline` 数据继续做真实计算链路验证。

**阻塞项 / 上游问题：** 当前真实 gap、真实 MACE、真实 phonopy 和离线 MP 竞争相仍依赖外部材料提供。

## 2026-09-11 — 接入本地 POSCAR 数据源与 GUI/WSL 后端

**本次工作目标：** 让 `data/CaS_CaSe_CaTe_POSCAR` 作为 Stage 01 输入参与初筛，并把 Windows GUI 与 WSL CLI 后端连通。

**已完成：**
- 新增 `src/ssscreen/data/structures.py` 和 `ss-screen dataset structures`，支持递归读取 POSCAR/CIF/vasp/json 文件夹或单文件，生成规范化 Stage 1 DataFrame；无 metadata 时可用显式默认 `band_gap` 和 `e_hull` 做流程联调。
- 更新 `src/ssscreen/gui/app.py`：右侧连接设置新增 Windows Python、WSL `.venv`、WSL `.venv-mlp` 后端；WSL 后端通过 `wsl.exe bash -lc` 进入工程目录并执行 `ss-screen ...`；数据源页新增本地 POSCAR 导入页；WBM 页补齐必填 `--xyz`；结构归档页递归扫描子目录 POSCAR。
- 更新 `src/ssscreen/gui/metadata.py`、`README.md`、`docs/cli_front_mid_smoke_2026-09-10.md`、相关 ZMD 导航和版本索引；新增 `tests/test_data_structures.py`，扩展 `tests/test_cli.py`。
- 使用 `data/CaS_CaSe_CaTe_POSCAR` 完成 `dataset structures`、`composition-screen`、`condense`、`condense-validate`、`structure-match`、`gap-export`、fixture `gap-validate`、`pair`、`sqs-generate`、fixture `mixing-enthalpy` 和 fixture `recommend`，产物位于 `work/poscar-gui-cli-20260911/`。
- 使用 headless Qt 验证 Windows GUI 可通过 WSL 后端调用 `ss-screen --version` 和 `dataset structures`，并生成 `work/gui-wsl-link-20260911/01_local_structures.df`。

**决策 / 计划变更：** 本地 POSCAR 数据源作为 Stage 01 的本地结构导入入口，不替代 MP/WBM 真实数据；无 metadata 默认 gap/hull 只用于流程联调，真实筛选必须提供 gap/hull 来源。GUI 仍只调用真实 CLI，不实现第二套科学逻辑。

**下一步：** 等同事提供真实 VASP gap 结果、POSCAR metadata、MACE checkpoint 和 `mp_offline` 包/SQLite 数据库后，运行真实 gap 收集、真实 MACE 单结构冒烟和离线 MP/竞争相流程。

**阻塞项 / 上游问题：** 当前缺真实 `mace-mpa-0-medium.model` checkpoint、`mp_offline` 包和数据库，以及 POSCAR 对应真实 `band_gap/e_hull` metadata；robocrys 仍提示缺少 OpenBabel Python bindings，但本轮无机结构 condense 可成功。未运行 notebook、DFT、真实 MACE 驰豫、真实 Phonopy 后处理或 AiiDA daemon。

## 2026-09-11 — 配置 WSL MLP/phonopy 专用环境

**本次工作目标：** 在不破坏已跑通轻量 CLI `.venv` 的前提下，为 MACE/Torch/phonopy 建立 WSL 专用运行环境。

**已完成：**
- 在 `/mnt/d/WorkSpace/OtherProjects/ss-screen/.venv-mlp` 创建 CPython 3.11.16 环境，安装 `torch 2.5.1+cu121`、`mace-torch 0.3.14`、`phonopy 4.5.0`、项目 `[wbm,mp,condense,sqs,mlp,phonon]` extras 和 `pytest`。
- 验证 WSL 可见 RTX 4060，`torch.cuda.is_available()` 为 True，CUDA runtime 为 12.1，`mace.calculators.MACECalculator` 可导入，`uv pip check` 通过。
- 验证 `ss-screen stability relax --help`、`ss-screen stability phonon-run --help`、`ss-screen stability phase-diagram --help` 可启动；`tests/test_e2e_pipeline.py`、`tests/test_stability_relax.py`、`tests/test_stability_phonon.py` 共 14 项通过。
- 更新 `.gitignore` 增加 `.venv-*/`，避免 `.venv-mlp/` 等专用虚拟环境进入版本控制；同步 `ZMD/01_项目入口与配置/README.md` 和 `ZMD/07_版本与变更索引/README.md`。

**决策 / 计划变更：** 无科学路线变化；保留轻量 `.venv` 作为前中段 CLI 环境，新增 `.venv-mlp` 作为 MACE/phonopy/GPU 专用环境，以避免 `numpy 2.x` 与 MACE 所需 `numpy<2` 冲突。

**下一步：** 等同事提供 MACE checkpoint 和 `mp_offline` 包/SQLite 数据库后，执行真实 MACE 单结构冒烟、离线 MP 数据读取和小真实数据端到端验证。

**阻塞项 / 上游问题：** 当前未发现本地 `mp_offline` 包或数据库；`models/` 目录仅有 README，缺少 `mace-mpa-0-medium.model` 等真实 checkpoint。本次未运行 notebook、DFT、真实 MACE 驰豫、Phonopy 后处理或 AiiDA daemon。

## 2026-09-10 — 整理 CLI 前中段流程验证交接单

**本次工作目标：** 将 WSL CLI 前中段 smoke run 的可运行范围、操作流水和真实运行缺口整理成可交给同事核对的 Markdown。

**已完成：**
- 新增 `docs/cli_front_mid_smoke_2026-09-10.md`，按 Word 手册流程列出已跑通阶段、产物目录、关键命令、模拟数据边界和需同事提供的真实 MP/WBM 数据、高精度 gap 结果、MACE/Torch/模型、phonopy 与 OpenBabel 可选依赖。
- 更新 `ZMD/04_项目文档与开发计划/README.md` 和 `ZMD/07_版本与变更索引/README.md`，登记该交接单入口和同步记录。

**决策 / 计划变更：** 无科学路线变化；本次文档明确当前 CLI 主链路可运行，真实阻塞在数据源、外部高精度计算结果和 GPU/MLP/phonon 依赖。

**下一步：** 根据同事提供的最小真实数据包，执行一轮“小真实数据”端到端 CLI 验证，再把 GUI 节点绑定到对应命令、输入和输出。

**阻塞项 / 上游问题：** 当前无真实 MP/WBM 数据源、真实 gap 返回结果、MACE 模型/Torch 环境和 phonopy 环境；本次未运行 notebook、DFT、MACE、Phonopy 或 AiiDA daemon。

## 2026-09-10 — 配置 WSL 后台 CLI 环境

**本次工作目标：** 在 WSL 中为 `ss-screen` 创建可运行后台 CLI 的 Python 3.11 环境。

**已完成：**
- 在 WSL Ubuntu 26.04 用户目录安装 `uv`，并在 `/mnt/d/WorkSpace/OtherProjects/ss-screen/.venv` 创建 CPython 3.11.16 虚拟环境。
- 使用 `uv pip` 安装 editable `ss-screen` 及 `[wbm,mp,condense,sqs]` 常用非 GPU 可选依赖，另安装 `pytest` 用于轻量端到端验证。
- 验证 `ssscreen` 1.0、核心/可选模块导入、`ss-screen --version`、`ss-screen condense --help`、`ss-screen stability sqs-generate --help`、`uv pip check` 和 `tests/test_e2e_pipeline.py` 通过。

**决策 / 计划变更：** 无科学路线变化；当前 WSL 环境先覆盖后台 CLI 与非 GPU 阶段，MACE、phonopy 和 GPU 相关依赖后续按需单独安装。

**下一步：** 评估是否把仓库复制到 WSL 原生 `/home/sipesc/projects/` 目录以提升依赖安装和测试 I/O 性能，再将 GUI 命令执行目标连接到该 WSL 后台解释器。

**阻塞项 / 上游问题：** Ubuntu 26.04 系统 Python 为 3.14.4，未提供 `python3.11` 命令；已通过用户级 `uv` 下载 CPython 3.11.16 规避。当前虚拟环境位于 Windows 挂载盘 `/mnt/d`，`uv` 无法 hardlink 并回退 copy，首次安装耗时较长。

## 2026-09-09 — GUI 支持 PyCharm 直接运行 app.py

**本次工作目标：** 让 `src/ssscreen/gui/app.py` 被 IDE 直接作为脚本运行时不再因相对导入失败退出。

**已完成：**
- 修改 `src/ssscreen/gui/app.py`：在 `__package__` 为空时自动把项目 `src/` 加入 `sys.path`，并改用绝对导入；包模式运行时继续使用原相对导入。
- 更新 `ZMD/02_正式源码/gui.md` 和 `ZMD/07_版本与变更索引/README.md`，登记该 IDE 兼容入口。

**决策 / 计划变更：** 无科学路线变化；`ss-screen-gui` 和 `python -m ssscreen.gui.app` 仍是正式包入口，直接运行 `app.py` 只是面向 IDE 的兼容方式。

**下一步：** 在安装 `.[gui]` 的项目解释器中从 PyCharm 运行 `app.py`，检查窗口启动和 CLI 子进程调用。

**阻塞项 / 上游问题：** 当前 Windows Python 未安装项目包和 PySide6，因此本次只做语法级验证，不做 GUI 视觉启动。

## 2026-09-02 — 发布当前完整工作树到远程 master

**本次工作目标：** 将当前工作副本中经约定纳入版本控制的源码、测试、Web 平台、文档与 ZMD 发布到 `bonan-group/ss-screen` 的新远程 `master` 分支。

**已完成：** 核对远程仅有 `main` 且位于基线 `33ddf40`；使用已授权的 GitHub SSH 身份，将 241 个文件组成的完整变更提交为 `33f9cc3`（`feat: add screening workflow and web platform`），并以非强制方式新建并推送 `origin/master`。远程 `main` 未修改。提交前排除虚拟环境、缓存、前端构建输出、TypeScript 增量缓存、模型权重、运行产物和大型数据，并完成常见 Token/私钥模式扫描。

**决策 / 计划变更：** 无科学路线变化；远程发布分支按用户要求命名为 `master`，本地 `codex/web-platform` 设置为跟踪 `origin/master`。`origin` 使用等价 SSH URL 以复用现有 GitHub 密钥认证。

**下一步：** 在 GitHub 检查 `master` 分支内容和 CI；功能开发继续实现 Stage 3 structure-match。

**阻塞项 / 上游问题：** 无。GitHub 推送成功；未使用强制推送，未修改远程 `main`。

**验证：** Python 3.11.15、`ssscreen` 1.0；核心 172 项 pytest、Ruff、Black，Web 后端 54 项 pytest/Ruff/Black，前端 ESLint、Vitest 1 项、TypeScript typecheck 和生产构建通过。提交前扫描未发现常见 GitHub/OpenAI/AWS/Slack Token 或私钥模式；最大新增文件约 4.4 MB。未运行 notebook、DFT、MACE、Phonopy 或 AiiDA daemon。

## 2026-09-02 — 重启 Web API 与 CPU Worker

**本次工作目标：** 恢复远程 Web 服务并给出本地浏览器访问方法。

**已完成：** 确认前端 5173 仍在运行、PostgreSQL/Redis 正常；定位页面 `Failed to fetch` 为远程 API 进程退出，随后以脱离交互会话的后台进程重新启动 FastAPI 8000 与 Celery control/cpu Worker，并确认 ready 六项和项目 API 检查通过。

**决策 / 计划变更：** 无；远程访问继续使用 SSH 本地端口转发，不开放额外公网端口。

**下一步：** 用户通过本地 `localhost:5173` 验收 Stage 2；开发路线继续实现 Stage 3 structure-match。

**阻塞项 / 上游问题：** 当前后台进程已脱离交互会话，但仍是开发态运行；生产环境仍应改由 Compose/systemd 等正式服务管理器托管。

## 2026-09-01 — 实现 Web Stage 2 condensation 垂直切片

**本次工作目标：** 从成功的 composition Run 启动可恢复、可取消、逐材料可审计的 Robocrys 结构凝聚。

**已完成：**
- 新增 `stage-2-condensation-v1` pipeline、Condensation StageRunner 和 CPU Worker；Run 创建时同时冻结规范 Dataset、候选 CSV 和 composition provenance 的 Artifact ID/SHA、候选数、批大小及科学核心身份，配置不保存 Artifact key 或服务器路径。
- Worker 物化三份输入并复核大小/SHA，按 1--100 条分批调用核心 `condense_dataframe`；每批发布 `stage.progress`、检查取消并把完整逐材料 JSON 写入 Task 检查点。基础设施失败保留检查点，显式重试在新 Attempt 中跳过已完成 JSON，成功发布后清理检查点。
- 单材料加载/Robocrys/schema 错误进入逐材料失败记录，不阻断其他结构；最终发布 `condensed-structures.zip`、`condensation-index.csv`、`condensation-failures.csv`、JSONL manifest 和 provenance 五类不可变制品，manifest 仅使用逻辑相对路径。
- 新增 Stage 2 创建页、composition 成功页入口、冻结双输入摘要、六指标批进度、Attempt/批次、失败预览和制品说明；新增鉴权 preview API，草稿/运行期读进度 Event，完成后读同一 Attempt provenance/失败 CSV。
- 新增 StageRunner 单元测试和 WBM→composition→condensation 集成链；集成测试模拟第二批 Worker 中断，核对 Attempt #1 检查点、显式重试、Attempt #2 `skipped=1`、五类制品与成功清理。四宽度 E2E 覆盖 Stage 2 创建、冻结配置、进度界面和横向溢出。

**决策 / 计划变更：** 延续“一 Run 一 Task、多 Attempt”控制层，以批内逐材料记录和 Task 级持久检查点实现恢复，不为每个材料创建数据库 Task；科学单材料失败属于成功 Attempt 的显式输出，基础设施失败才触发 Task retry。ZIP 用于下载运输，manifest/index 仍保留逐材料身份与 SHA。

**下一步：** 实现 Stage 3 structure-match StageRunner，安全解包/校验 Stage 2 ZIP 或按 manifest 物化 condensed JSON，与 Stage 1a candidates 汇合并发布环境分组与缺失/损坏统计。

**阻塞项 / 上游问题：** 当前正式全量 WBM extxyz 仍未提供，Stage 2 Web 的真实验收仅使用两个微型 WBM 结构；Robocrys 对无 OpenBabel Python bindings 发出可选分子命名警告，但本次无机 NaCl/KCl 结构凝聚不受影响。未运行 notebook、DFT、MACE、Phonopy 或 AiiDA daemon。

**验证：** 核心 172 项 pytest、Web 后端 54 项 pytest、Vitest 1 项、四宽度 Playwright 20 项、Ruff、Black、ESLint、TypeScript、前端生产构建、OpenAPI 重复生成和 ready 六项检查通过；真实 Web Worker 对 2 个 WBM 候选完成 Robocrys condensation，2/2 成功并登记五类 Artifact，Stage 2 页面完成 1440px 视觉检查。

## 2026-09-01 — 完善 composition Run 参数摘要与候选预览

**本次工作目标：** 让用户在组成筛选 Run 内直接核对冻结输入/阈值，并安全预览候选结果。

**已完成：**
- 新增同项目鉴权的 `GET /api/v1/runs/{run_id}/composition-preview`；只读取已登记的同一 Attempt 候选 CSV/provenance，返回服务端限制的前 1--100 行、总行数和 Artifact ID，不暴露存储 key 或绝对路径。
- Run 页面新增 Stage 1a 冻结配置摘要、Dataset 反向链接、零候选合法语义、前 20 行候选表和完整 CSV 入口；修正 composition/WBM 被误描述为 demo/MP 的文案。
- 新增四宽度真实浏览器链：微型 WBM 上传、Dataset 登记、composition Worker、2 条候选预览和无页面级横向溢出；同步 OpenAPI、README、开发指南与 ZMD。

**决策 / 计划变更：** Run 内预览保持有界且只读，完整 CSV 继续作为权威不可变制品；当前不引入候选数据库表，待 Stage 5 候选查询需要服务端分页/筛选时再建领域模型。

**下一步：** 实现 Stage 2 condensation StageRunner 的批处理、逐分片失败记录、resume/取消检查点和 Artifact 输入输出契约。

**阻塞项 / 上游问题：** 当前预览只支持 Stage 1a 已验证 CSV；尚无 Stage 2 Web 批处理资源估算与正式全量 WBM 输入。未运行 notebook、DFT、MACE、Phonopy 或 AiiDA daemon。

**验证：** Web 后端 52 项 pytest、Vitest 1 项和四宽度 Playwright 20 项通过；Ruff、Web 后端 Black、ESLint、TypeScript、前端生产构建、OpenAPI 重复生成、ready 六项检查及 375/1440 视觉检查通过。

## 2026-09-01 — 实现 Web Stage 1a composition 垂直切片

**本次工作目标：** 让用户从已登记 MP/WBM Dataset 启动可审计的二元/三元组成模板筛选。

**已完成：**
- 新增 `stage-1a-composition-v1` pipeline、Composition StageRunner 和 CPU Worker；Run 创建时冻结 Dataset/Artifact ID、SHA-256、科学核心身份、默认排除元素和全部数值阈值。
- Worker 只从 ArtifactStore 逻辑 key 物化输入并复核大小/SHA，调用核心 `screen_composition_candidates`，发布 `composition-candidates.csv` 与 provenance JSON；零候选是合法科学结果，输出不会误登记为新 Dataset。
- 前端 Dataset 详情页新增“组成筛选”入口，新增二元/三元、最大 gap/hull 和折叠高级分组条件表单；viewer 不显示写入口，异步错误与 loading 状态邻近呈现。
- 新增 WBM 两盐微型 Dataset → composition 的真实集成链，核对 2 条候选、科学状态、双 Artifact、输入身份脱敏和 Dataset 数量不变；同步 OpenAPI、README、ADR、开发指南和 ZMD。

**决策 / 计划变更：** Stage 1a 产物先作为 Run Artifact，而不是派生 Dataset；后续 Stage 2 直接引用其不可变 Artifact。沿用通用 Dataset worker 事务骨架，但用 `register_dataset=False` 明确区分转换输出与数据源登记。

**下一步：** 完善 composition Run 参数摘要与候选预览，然后实现 Stage 2 condensation StageRunner 的批处理/失败分片契约。

**阻塞项 / 上游问题：** 大型 MP Dataset 的全量 composition Web 运行尚未由用户启动；当前真实集成使用微型 WBM 夹具。未运行 notebook、DFT、MACE、Phonopy 或 AiiDA daemon。

**验证：** Web 后端 52 项 pytest、Vitest 1 项和四宽度 Playwright 16 项通过；Ruff、Web 后端 Black、ESLint、TypeScript、前端生产构建、OpenAPI 生成及 375/1440 页面视觉检查通过。

## 2026-09-01 — 补齐 WBM 上传取消态生命周期清理

**本次工作目标：** 确保 WBM 隔离输入在草稿、排队和运行中取消后都被安全回收，同时保留科学校验失败后的重试能力。

**已完成：**
- 新增 `application/upload_lifecycle.py`，只解析 `stage-1-wbm-upload` 的结构/摘要逻辑 key，并通过 ArtifactStore 路径门禁执行幂等、尽力而为的隔离文件删除。
- Run/Task 取消先提交 PostgreSQL 权威终态，再清理草稿或排队输入；运行中取消由 Worker 到达安全检查点、提交 `CANCELLED` 后清理，已发布但未登记的 Artifact 同步删除。
- WBM 科学校验失败继续保留隔离输入供显式 retry；MP 与 demo pipeline 不受 WBM 清理逻辑影响。WBM 启动前补齐与 MP 相同的冻结科学核心身份检查。
- 新增草稿双文件取消、排队 Task 取消、运行中 Worker 取消和失败保留输入四项集成回归。

**决策 / 计划变更：** 文件删除必须发生在数据库终态提交之后；清理失败记录日志但不把已提交的取消响应改成 500。失败输入不自动删除，后续生产化阶段应增加有保留期的 quarantine 垃圾回收策略。

**下一步：** 以现有 MP/WBM Dataset 的不可变 DataFrame Artifact 为输入，实现 Stage 1a composition StageRunner、输出 Artifact 与可审计 provenance。

**阻塞项 / 上游问题：** 尚未实现失败上传的保留期/管理员清理任务；正式部署仍需定义容量告警和垃圾回收周期。未运行 notebook、DFT、MACE、Phonopy 或 AiiDA daemon。

**验证：** Web 后端 51 项 pytest 全部通过；Web 后端 Ruff 与 Black 通过。

## 2026-09-01 — 实现 Web Stage 1 WBM 隔离上传垂直切片

**本次工作目标：** 为用户提供不接受服务器路径的 WBM 上传入口，并经隔离、完整性与科学 schema 校验登记为可审计 Dataset。

**已完成：**
- 核心 `load_wbm_dataset(strict=True)` 新增非空、结构/摘要行数、ID 对齐、重复 ID，以及 gap/hull 缺失、非数值、非有限和负值拒绝，同时保留 CLI 默认兼容行为。
- 新增 multipart 上传 API、仓库外不可信隔离区和流式大小/SHA-256 记录；只接受白名单扩展名/MIME，拒绝路径型文件名，Run 仅保存逻辑 key 与显示元数据。
- 新增 `stage-1-wbm-upload-v1` StageRunner 与 CPU Worker：执行前重新核验大小/SHA，严格解析并发布原始结构、可选摘要、`wbm.df` 和脱敏 provenance；成功后登记 `wbm-upload` Dataset 并清理隔离输入。
- 前端新增项目“上传 WBM”入口、可访问上传表单、处理边界/字段要求说明及 WBM Dataset 审计视图；同步 OpenAPI、容器 WBM 依赖、部署大小配置、README、ADR 和 ZMD。

**决策 / 计划变更：** 首个切片以 Run configuration 作为不可变上传 manifest，不新增独立 Upload 表；失败输入保留以支持显式重试，成功输入转存为不可变 Artifact 后删除隔离副本。浏览器和 provenance 均不暴露服务器绝对路径。

**下一步：** 让草稿/排队取消也回收 WBM 隔离文件，并以统一 Dataset 输入实现 Stage 1a composition StageRunner。

**阻塞项 / 上游问题：** 尚无可分发的 WBM 全量 extxyz/summary，本次只用微型合成结构验证真实解析链；反向代理部署时仍需同步请求体上限。未运行 notebook、DFT、MACE、Phonopy 或 AiiDA daemon。

**验证：** 核心 172 项 pytest、Web 后端 47 项 pytest、Vitest 1 项和四宽度 Playwright 16 项通过；Ruff、涉及文件 Black、ESLint、TypeScript、前端生产构建、OpenAPI 客户端生成及 375/1440 视觉检查通过。

## 2026-09-01 — 固化 Web 科学核心版本与源码身份门禁

**本次工作目标：** 消除真实 Stage 1 运行发现的 editable distribution 元数据漂移，并防止科学 Run 在核心代码身份变化后继续执行。

**已完成：**
- 在项目 `.venv` 中按根 `pyproject.toml` 重装 editable `ss-screen`，确认 `ssscreen.__version__` 与 `importlib.metadata.version("ss-screen")` 均为 `1.0`；没有安装到系统环境。
- 新增 `application/scientific_runtime.py`，统一生成 distribution、源码/distribution 版本、部署修订和实际 `ssscreen/**/*.py` 内容 SHA-256；版本不一致、元数据缺失或 Run 创建后身份变化返回稳定错误。
- Stage 1 Run 创建时由服务端冻结科学核心身份，ready、Run 启动与 Worker prepare 三处复核；同一身份进入 Attempt `settings_hash` 和最终 Dataset provenance，pipeline 版本同时登记。
- Run/Dataset 页面显示核心版本、修订与源码 SHA；production 配置必须提供非默认 `SSSCREEN_CORE_REVISION`，部署示例、README、ADR、开发指南和 ZMD 已同步。

**决策 / 计划变更：** 使用实际安装包源码内容 SHA-256 作为精确代码身份，服务端修订标识作为可读的 Git/发布标签；两者共同记录，避免只依赖可能陈旧的版本号。已有不可变 Dataset 不回写，新建 Run 才应用新门禁。

**下一步：** 实现 Stage 1 WBM/用户上传的 quarantine、文件大小/路径安全、schema/provenance 校验和 Dataset 登记，然后以统一 Dataset 输入接入 Stage 1a composition。

**阻塞项 / 上游问题：** 首个既有 Dataset 的 provenance 继续如实保留运行时 `ss-screen 0.1.0` distribution metadata，不覆盖历史制品；新运行已消除漂移。正式部署仍需注入真实 Git commit/发布标识。未运行 notebook、DFT、MACE、Phonopy 或 AiiDA daemon。

**验证：** 核心 169 项 pytest、Web 后端 42 项 pytest、Vitest 1 项和四宽度 Playwright 16 项通过；Ruff、Black、ESLint、TypeScript、前端构建、OpenAPI 重复生成、418 个 ZMD 本地链接、`pip check` 与 ready 六项检查通过。

## 2026-09-01 — 完成首个真实 Web Stage 1 MP 离线运行

**本次工作目标：** 按用户确认启动并持续监控首个真实 `stage-1-mp-offline-v1` 全量任务，核验 Dataset 与不可变制品。

**已完成：**
- 启动 Run `82e8adeb-3bcb-407c-ba37-727ebec14aa6`，以 `max_e_hull=0.01 eV/atom` 读取服务器端 2.22 GB 只读快照；CPU Worker 在约 295 秒内成功完成，Run/Task/Attempt 均为 `SUCCEEDED`，科学状态为 `dataset_ready`。
- 登记 Dataset `26518269-ee45-44c4-ad4a-90ddb0691ec7`，包含 46,675 条非 deprecated 记录；数据库引用为 `mp-offline-2024-06-04`，SHA-256 为 `d54bca48d1e00bdfd8db7c1e5a7b5844ccb755b948335930f09fe85444a7ebb8`。
- 发布 430,317,793 字节 `mp.df`（SHA-256 `a41cabadaeeed1e014a2cb9b5a80a7640bc9ab7af69794aacbe26323f724aaa8`）和 1,185 字节 provenance JSON（SHA-256 `a4c72de516e70e8d0f73521b53c958bd48dc912993b80c5349ec1e210c72b3d1`）；实测文件大小/SHA 与 PostgreSQL 登记一致，Attempt sandbox 已自动清理。

**决策 / 计划变更：** 无路线变化；全量产物继续保存在仓库外 ArtifactStore，不复制到 Git 工作树。运行中 Ne/Ar/He 的 Pauling 电负性缺失警告与既往核心运行一致，不影响成功状态。

**下一步：** 在开始 WBM/上传入口前校正项目 `.venv` 的 editable distribution metadata，使 `importlib.metadata.version("ss-screen")` 与源码 `1.0` 一致，并把核心版本/工作树身份作为 Web provenance 门禁。

**阻塞项 / 上游问题：** 本次 provenance 如实记录当前已安装 distribution metadata 为 `ss-screen 0.1.0`，而源码 `ssscreen.__version__` 和根 `pyproject.toml` 为 `1.0`；这是 editable 安装元数据陈旧问题，不影响本次 46,675 行内容与文件完整性，但后续科研运行前必须消除该环境漂移。未运行 notebook、DFT、MACE、Phonopy 或 AiiDA daemon。

## 2026-09-01 — 实现 Web Phase 2 Stage 1 MP 离线数据垂直切片

**本次工作目标：** 在已验收的 Web 控制面上接入第一个真实科学 StageRunner，使用户可通过浏览器准备可审计的 MP 离线 Dataset。

**已完成：**
- 新增版本化 `stage-1-mp-offline-v1` pipeline、StageRunner 协议与 MP 离线实现；CPU Worker 调用核心 `load_mp_dataset_offline`，校验非空结果、记录数、数据库 SHA 和脱敏 provenance，并流式原子发布 `mp.df` 与 provenance JSON。
- 新增 Dataset PostgreSQL 模型、可逆 Alembic migration、项目列表/详情 API、权限隔离和来源 Run/Artifact 关联；任务支持 Attempt 绑定、取消、重试、失败清理和独立的长任务 `worker.lost` 恢复。
- 前端新增“准备数据集”、Dataset 列表与详情页面，固定显示数据源、`max_e_hull` 单位、快照引用/SHA、pickle 信任提示和离线覆盖范围；浏览器不接收或显示服务器绝对路径。
- 拆分 Celery `control`/`cpu` exchange 与 routing key，Compose 以只读方式挂载外部 SQLite 与 `mp_offline` 包；同步 OpenAPI、部署示例、README、ADR 和 ZMD。

**决策 / 计划变更：** Phase 2 先交付单一 MP 离线入口；数据库路径仅由服务器配置，Run 只保存数据集名称与具名阈值。只有两个制品都发布并通过验证后才登记 Dataset。WBM、用户上传、在线 MP 和 Stage 1a--5 保持后续独立实现。

**下一步：** 优先实现 Stage 1 WBM/用户上传的 quarantine、schema/provenance 校验和 Dataset 登记，再以统一 Dataset 输入接入 Stage 1a composition StageRunner。

**阻塞项 / 上游问题：** 外部 2.22 GB MP SQLite 与 `mp_offline` 包继续只读保留在仓库外；本次未通过 Web 启动全量快照导出，以免无明确用户操作时生成约数百 MB 制品，真实 loader 能力已有既往 45,624 行运行证据。正式 OIDC、非 root 容器权限和 WBM 完整来源仍待处理；未运行 notebook、DFT、MACE、Phonopy 或 AiiDA daemon。

**验证：** 核心 169 项 pytest、Web 后端 36 项 pytest、Vitest 1 项和 375/768/1024/1440 四宽度 Playwright 16 项通过；真实 PostgreSQL migration `up/down/up`、`alembic check`、Ruff、Black、ESLint、TypeScript、前端构建、OpenAPI 重复生成、视觉检查和路径脱敏检查通过。

## 2026-09-01 — 启动本地 Web 控制层

**本次工作目标：** 启动已验收的 Phase 1 网页、API 和 control Worker，供用户本机访问。

**已完成：**
- 保留既有 `ssscreen-web-test-postgres` 与 `ssscreen-web-test-redis` 容器，执行当前 Alembic migration 后启动 Uvicorn、Celery control Worker 和 Vite production preview。
- 验证 `http://localhost:5173` 与 `http://localhost:8000/docs` 返回 HTTP 200；`/health/ready` 确认 PostgreSQL、Redis、ArtifactStore、Attempt sandbox 和上传隔离区均为 `ok`。

**决策 / 计划变更：** 本次仅启动现有开发服务，不改变 Web 或科学路线；继续使用 production preview，避免当前主机 Vite watcher 的 inotify 上限问题。

**下一步：** 用户在浏览器验收 Project → Run → Task → Artifact 流程；结束后按需停止本次启动的 API、Worker 和前端进程。

**阻塞项 / 上游问题：** Celery 当前以 root 运行并发出开发环境安全提示；生产部署仍需专用非 root 用户和对应的三个外部存储目录组权限。本次未运行 notebook、DFT 或 AiiDA daemon。

## 2026-08-31 — 加固并验收 Web 控制层 Phase 1

**本次工作目标：** 按 `docs/web_platform_implementation_handoff.md` 审查、加固并真实验收既有 Phase 1 控制层垂直切片。

**已完成：**
- 加固仓库外 ArtifactStore：三个存储根均纳入 ready 写入探针，发布采用并发不覆盖的原子语义；配置补齐 Attempt sandbox、上传隔离区、outbox 重投和演示任务失联阈值。
- 完善 PostgreSQL 权威状态机：投递绑定明确 Attempt，重复/过期消息幂等退出；队列取消同步关闭 Attempt/Task/Run 和未投递 outbox；显式重试保留旧 Attempt；停滞 `PUBLISHED` 消息可重投，长期 `RUNNING` 演示任务以 `worker.lost` 失败原因落库。
- 完善 API/UI：稳定化请求校验错误 envelope；项目列表显示 owner 与最近 Run；viewer 隐藏写操作；Run 操作错误邻近显示；四宽度布局避免全局横向溢出；Playwright 下载实际制品并核对 SHA-256。
- 同步 OpenAPI 客户端、部署示例、README、ADR 与 ZMD；本地浏览器安装在被忽略的前端目录，未写入系统环境。

**决策 / 计划变更：** 不扩展 handoff 路由或科学范围，确定性 demo JSON 继续仅用于验证编排而非科研结果；主机 Vite watcher 达到 `ENOSPC` 时采用 production build + preview 验收，不修改系统限制。下一阶段仍从既有控制面接入 Stage 1 Dataset/MP/WBM StageRunner。

**下一步：** 为 Stage 1 定义真实 StageRunner 输入/输出 schema、数据来源 provenance、资源估算和 Artifact 登记，并保持核心科学包对 Web 运行时零依赖。

**阻塞项 / 上游问题：** 当前主机缺少 Docker Compose，Vite 开发 watcher 达到系统 inotify 上限；现有三个外部存储子目录为 `root:root 755`，未来非 root 容器需管理员授予专用组权限；正式 OIDC、生产 Secret Manager 和 StageRunner 尚未实现。本次未运行 notebook、DFT、MACE、Phonopy 或 AiiDA daemon。

**验证：** 核心169项 pytest、Web后端29项 pytest、Vitest 1项及375/768/1024/1440四宽度 Playwright 12项通过；真实 PostgreSQL migration `up/down/up`、`alembic check`、Ruff、Black、ESLint、TypeScript、前端构建和视觉检查通过；临时 migration 审计数据库已删除，既有 PostgreSQL/Redis 容器未重启或删除。

## 2026-08-28 — 生成第十五章现场演示截图

**本次工作目标：** 在当前项目环境按 DOCX 的完整 BASH 代码块实际执行第十五章演示，并向用户交付可直接插入 Word 的终端截图。

**已完成：**
- 将第15.3节切换为在线 MP API，在不落盘密钥的前提下连续执行 `dataset mp --backend api` 和 `composition-screen`：下载数据库版本2026.04.13的45,624条唯一材料记录，生成421.9 MB `mp.df`、provenance、4,408条候选和343个组成模板，并生成完整 BASH 代码块截图与 transcript。
- 修复在线 Stage 1 大查询在 `mp-api` 默认20秒超时或中途断流时整批丢失的问题：`config.py` 增加120秒超时、500条分页、单页3次重试和退避具名配置；`data/mp.py` 使用稳定 `material_id` 排序逐页获取并把请求设置写入 provenance；`test_data_mp.py` 增加默认超时与失败页重试覆盖，README同步说明。
- 在已进入的 `screening-run` 中连续执行环境记录完整 BASH 命令组，确认项目 `.venv` 为 Python 3.11.15、SS-Screen 为1.0，并生成169行 `logs/python-packages.txt` 依赖快照；生成一张保持三条命令原顺序、输出和退出码的合并截图与 transcript。
- 在 `work/chapter15-live/` 按手册第15.2节原样执行全部五条 Bash 命令，实际创建 `01_dataset` 至 `12_recommendation` 以及 `logs`、`models` 共14个工作目录并进入 `screening-run`，为每条命令生成含完整实际路径、核验结果和退出码的逐步截图与 transcript。
- 在被 Git 忽略的 `work/screenshot-demo/` 实际执行环境/版本检查、Stage 1--11 CPU 端到端测试、既有教学阶段台账读取和最终推荐汇总读取，生成4张PNG及对应原始终端 transcript。
- 截图使用中文字体复核，保留实际命令、输出和退出码；最终推荐仍为2条，其中 CaSe-CaS 为 promising/L5，CaTe-CaS 为 low-priority/L5。

**决策 / 计划变更：** 后续以 DOCX 中每个完整 BASH 代码块为执行和截图单元，不再按单条命令拆图；Stage 1 在线后端固定为显式稳定分页和单页重试，以保证全量结构查询可恢复；无项目路线变化，运行截图和421.9 MB在线数据不纳入正式版本资产导航。

**下一步：** 按用户确认执行第15.4节 condensation、归档校验和结构匹配完整 BASH 代码块；运行前评估45,624条全量结构的时间与存储规模。

**阻塞项 / 上游问题：** `logs/python-packages.txt` 含3条本地安装路径，向外共享前必须脱敏；在线组成筛选对 Ne、Ar、He 缺少 Pauling 电负性发出3条 pymatgen 警告但未阻断筛选；本次未运行VASP、DFT、MACE、Phonopy、notebook或AiiDA daemon。

**验证：** 在线数据与组成筛选两条命令退出码均为0，45,624个数据ID无重复，provenance记录 API 后端、数据库版本和分页/重试设置，4,408条候选与summary一致，文本产物和transcript无API密钥残留；完整168项pytest和 `ruff check src tests` 通过；环境与目录命令均为0，现场PNG完成逐张视觉检查。

## 2026-08-26 — 建立方案二 Web 平台开发基线

**本次工作目标：** 在当前 Stage 1--11 科学内核基础上编写可直接指导实施的多用户 Web 平台开发文档。

**已完成：**
- 新增 `docs/web_platform_development_guide.md`，固定 React/TypeScript + FastAPI + PostgreSQL + Redis/Celery + 外部 ArtifactStore 架构，定义依赖边界、MVP 范围、领域实体、运行/科学双状态、StageRunner、队列、API、页面、安全、科学完整性、测试、运维和 Definition of Done。
- 将开发拆为科学基线冻结、控制层、Stage 1--5 MVP、Stage 6--11 Worker 和实验室生产化四个实施阶段，并给出首批20项顺序任务和外部决策清单。
- 更新 `docs/PROJECT_PLAN.md`，将 Web 平台登记为正式扩展路线；同步项目文档导航、文件资产索引、目录树和版本变更索引，并修正相关 ZMD 中过时的包版本/测试数。

**决策 / 计划变更：** Web 平台采用独立 `web/` 包，依赖方向固定为 `ssscreen_web -> ssscreen`；首版只交付 Stage 1--5，多用户元数据进入 PostgreSQL，大型制品保存在仓库外 NFS/对象存储，GPU/HPC 与 Stage 6--11 后置接入。当前仅完成设计，不代表 Web 运行时已经实现。

**下一步：** 先完成 Phase 0：审查并版本化当前科学工作树、恢复绿色 CI、移出仓库内大型运行数据，并为核心/Web 边界、ArtifactStore、状态机和认证编写 ADR；随后创建 `web/backend` 骨架和数据库迁移。

**阻塞项 / 上游问题：** 实施前需确认首个部署拓扑、OIDC 提供方、仓库外 ArtifactStore、项目共享权限、首个 Slurm/AiiDA 适配目标、数据保留周期和 MACE checkpoint 许可边界；这些问题不阻塞当前开发指南。

**验证：** 指南含20个连续主章节、24个配对代码围栏且无 TODO/TBD；检查6个关联 Markdown 的93个本地链接，失效数为0；完整166项pytest、正式源码/测试/脚本 Ruff 和 `git diff --check` 通过。未创建 Web 代码、数据库、队列、容器、集群任务或Git提交。

## 2026-08-24 — 补齐VASP批量带隙收集契约

**本次工作目标：** 按高通量批量优先要求补齐 `gap-collect-vasp` 的命令接口、逐任务结果和错误审计。

**已完成：**
- 扩展 `src/ssscreen/pair/gap_collect_vasp.py` 和CLI：支持 `--method-metadata` 设置哈希、可选 `--report`、四状态完整计数、逐任务错误、已发现/未知目录审计；每个选中任务均写结果行，缺失结果明确为 `missing`。
- 将 `missing` 纳入外部带隙结果合法状态；新增方法哈希、默认报告、未知目录和missing结果行回归覆盖，并同步README、算法说明、V1.0手册和相关ZMD导航。
- 重新生成 V1.0 DOCX/PDF，保持Markdown与交付物一致。

**决策 / 计划变更：** 无路线变更。任务表继续定义应收集的权威任务集合，结果目录扫描用于定位对应子目录并审计额外目录；单任务模式只用于调试和失败重试。

**下一步：** 使用一组可再分发的真实脱敏 `vasprun.xml` 验证不同VASP版本、静态/能带K点路径和跃迁标签提取。

**阻塞项 / 上游问题：** 仓库仍没有合法可再分发的真实VASP输出夹具；当前真实XML集成验证缺失，未修改只读上游目录。

**验证：** Python 3.11.15、`ssscreen 1.0`；完整166项pytest、Ruff、涉及文件Black和`pip check`通过；CLI帮助显示新参数，V1.0手册构建器`--check`通过，DOCX/PDF含37处图片。全库Black仅报告 `tests/test_reference_curation.py` 和 `scripts/curate_upstream_references.py` 两个既有格式差异。未运行VASP、DFT、notebook或AiiDA daemon，未创建Git提交。

## 2026-08-24 — 新增VASP批量带隙结果收集

**本次工作目标：** 让用户只需提供按任务ID组织的VASP结果目录，即可批量生成SS-Screen标准带隙结果。

**已完成：**
- 新增 `src/ssscreen/pair/gap_collect_vasp.py`：读取 `gap_tasks.csv`，批量解析 `task_id/vasprun.xml` 或 `.xml.gz`，提取带隙、直接性、跃迁、收敛状态、VASP版本和完成时间。
- 新增顶层 `ss-screen gap-collect-vasp`；默认处理全部任务，重复 `--task-id`支持单任务调试或选择性重试，输出结果CSV和收集报告。
- 新增 `tests/test_gap_collect_vasp.py` 和CLI回归测试，更新README、项目计划、算法说明、V1.0手册第7章及相关ZMD导航；重新生成DOCX/PDF。

**决策 / 计划变更：** Stage 3外部高精度带隙契约增加VASP批量适配器；VASP执行仍在包外，`gap-validate`继续负责最终身份、设置和数值校验。缺失结果只进入missing报告，不伪造失败带隙。

**下一步：** 使用一组合法脱敏的真实 `vasprun.xml` 做集成验证，并为正式手册补充真实批量收集截图；如需支持ABACUS/AiiDA，按相同结果契约增加独立适配器。

**阻塞项 / 上游问题：** 仓库内没有可再分发的真实VASP输出夹具，因此本次未完成真实XML端到端解析验证。

**验证：** Black、Ruff、完整165项pytest和`pip check`通过；CLI帮助显示新命令；手册构建器`--check`通过，DOCX含37处内嵌图片且无外链，PDF 65页。未运行VASP、DFT、AiiDA、MACE或其他昂贵任务，未创建Git提交。

## 2026-08-24 — 增加 gap-export 连续操作截图

**本次工作目标：** 按真实教学数据执行高精度带隙任务导出，并将输入、执行、任务输出和模板检查截图加入 V1.0 操作手册。

**已完成：**
- 扩展 `scripts/build_copyright_manual_assets.py`，在不影响原合成 gap 校验链的前提下，新增独立的 `vasp-hse06-pbe54-nosoc-v1` 任务导出演示；真实生成3条任务、9个 JSON/CIF/POSCAR 结构文件、结果模板和方法元数据模板。
- 新增 `cli_19_gap_export_inputs.png` 至 `cli_22_gap_export_templates.png` 四张终端界面，并更新资产 manifest。
- 更新 `docs/user-guide/SS-Screen_V1.0_软件著作权登记操作手册.md` 第7.2节的图7-1至图7-4及后续图号，重新生成同名 DOCX/PDF。

**决策 / 计划变更：** VASP方法字符串仅作为外部任务身份；本次未运行VASP、DFT或其他昂贵计算，不改变软件功能和项目路线。

**下一步：** 在 Microsoft Word 或 WPS 中更新目录/页码域，并复核提交端分页。

**阻塞项 / 上游问题：** 当前环境无 LibreOffice，Microsoft Word/WPS 最终分页仍需人工复核。

**验证：** 资产脚本生成36个不同图片文件；登记版构建器 `--check` 通过，DOCX含37处内嵌图片引用且无外链，PDF共65页；第7章连续页面视觉检查无裁切、重叠或不可读截图。Black、Ruff通过，未创建Git提交。

## 2026-08-24 — 完善 V1.0 手册第六至十七章连续操作说明

**本次工作目标：** 按软著审查意见，仿照前五章逻辑扩写操作手册第六至十七章，突出连续操作截图、数据变化和阶段交接。

**已完成：**
- 仅修改 `docs/user-guide/SS-Screen_V1.0_软件著作权登记操作手册.md` 第六至十七章，为主要功能章补充上一步输入、操作前后数据变化、结果验收和下一章交接。
- 将第十五章整理为同一批次的端到端操作台账；第十六章增加从推荐结果反查上游证据的审计步骤；第十七章增加故障定位、单变量修复和复验闭环。
- 复用已有真实 CLI/教学结果界面，重新生成同名 DOCX/PDF；第十六、十七章均已作为正式 Word 标题和图文操作章节进入正文。

**决策 / 计划变更：** 第一至第五章保持不变；不虚构登录页，不重新运行 MACE、Phonopy、在线 MP、DFT 或 AiiDA，不改变软件功能和项目路线。

**下一步：** 在 Microsoft Word 或 WPS 中更新目录/页码域，并复核提交端字体环境下的最终分页。

**阻塞项 / 上游问题：** 当前环境无 LibreOffice，无法验证 Microsoft Word/WPS 自身的最终分页；不影响同源 PDF 和 DOCX 结构检查。

**验证：** 构建器 `--check` 通过；源稿 2075 行、174 个标题、41 个表格、63 个代码块和34处图片引用；DOCX含34个内嵌图片、无外部图片关系且ZIP完整，PDF共63页；第6、10、14、16、17章代表页视觉抽查无裁切或重叠。未创建Git提交。

## 2026-08-24 — 增加 CLI ASCII 启动界面

**本次工作目标：** 将 SS-Screen 版本界面改为带软件字符 Logo 的真实终端启动画面，并同步软著手册。

**已完成：**
- 在 `src/ssscreen/cli/app.py` 增加固定纯 ASCII `SS-SCREEN` Logo，`ss-screen --version` 现输出 Logo 和 `SS-Screen version 1.0`。
- 更新 `tests/test_cli.py` 的完整输出契约，重新生成 `docs/user-guide/assets/copyright-v1/cli_01_version_and_main.png` 等手册资产，并同步 V1.0 Markdown、DOCX/PDF 与相关 ZMD 页面。

**决策 / 计划变更：** 仅改进 CLI 启动展示和登记材料截图，不改变命令结构、软件版本、科学算法或项目路线。

**下一步：** 在 Microsoft Word 或 WPS 中打开最终 DOCX，更新目录/页码域并复核提交端分页。

**阻塞项 / 上游问题：** 当前环境无 LibreOffice，无法验证 Microsoft Word/WPS 自身的最终分页。

**验证：** 完整 pytest、Ruff、相关文件 Black 和 `pip check` 通过；登记版构建器 `--check` 通过，DOCX 包含 32 张内嵌图片、无外部图片关系且 ZIP 完整，PDF 共 55 页；启动截图已视觉复核。未运行 notebook、DFT、MACE、Phonopy、在线 MP 或 AiiDA daemon，未创建 Git 提交。

## 2026-08-18 — 完善 V1.0 软著图文操作手册

**本次工作目标：** 在现有 V1.0 Word 手册基础上补齐真实操作截图、连续操作流程、软件结构、接口、模块/函数、算法、数据字典和运行设计。

**已完成：**
- 更新 `docs/user-guide/SS-Screen_V1.0_软件著作权登记操作手册.md`，明确命令行软件无账户登录页，增加顶层/二级菜单、总体结构、模块依赖、接口逻辑、数据结构/字典和运行恢复说明。
- 将 `docs/user-guide/assets/copyright-v1/` 的 10 张真实 CLI 截图、5 张设计/逻辑图、8 张功能流程图和 1 张声子结果图按 Stage 1–11 顺序嵌入手册。
- 重新生成同名 DOCX 和 PDF；Word 核心元数据由错误的 V0.1.0 修正为 V1.0，并同步 ZMD 项目文档、脚本、资产、目录树和版本索引。

**决策 / 计划变更：** 登录界面要求按真实产品形态处理：SS-Screen 是本地 CLI 科研软件，以版本界面、顶层帮助和展开的二级命令菜单表现启动和导航，不虚构 GUI 登录页。本次不改变软件功能或科学边界。

**下一步：** 在 Microsoft Word 或 WPS 中打开 DOCX，更新目录/页码域，并对本机字体环境下的最终分页进行人工复核。

**阻塞项 / 上游问题：** 当前环境无 LibreOffice，无法渲染 Microsoft Word/WPS 自身的分页结果；不影响 DOCX 结构和同源 PDF 检查。

**验证：** 登记版构建器 `--check` 通过；源稿 1841 行、163 个标题、31 个表格、63 个代码块和 24 张图；DOCX 包含 24 个内嵌图像且无外部图片关系，ZIP 完整性通过；PDF 共 51 页，封面、正文、模块图、中间流程页和末页视觉抽查无裁切、重叠或空白图。未运行 notebook、DFT、MACE、声子、在线 MP 或 AiiDA daemon，未创建 Git 提交。

## 2026-08-18 — 生成无前置标号的源程序 Word 材料

**本次工作目标：** 将正式包前后各 2500 行源代码制作为 Word 文档，并删除正文前面的人工标号。

**已完成：**
- 扩展 `scripts/build_copyright_source.py`，在既有 PDF、文本和 manifest 基础上生成无前置标号 DOCX；Word 正文只写入原始代码，页眉保留软件名称、版本和自动页码。
- 新增 `docs/copyright-source/SS-Screen_V0.1.0_source_front2500_back2500_unlabeled.docx`，共 5000 个源码段落，每 50 行设置强制分页；manifest 增加 Word 行数、分页规则、无前缀标志和 SHA-256。
- 同步源程序目录说明、项目文档、脚本自动化、文件资产和版本变更 ZMD 索引。

**决策 / 计划变更：** Word 选段范围与既有材料保持一致，不改变正式源码或软件版本；文件路径只保留在 manifest，不进入 Word 正文，以满足删除前置标号的要求。

**下一步：** 使用 Microsoft Word 或 WPS 打开 DOCX，更新页码域并确认不同字体环境下仍保持每页 50 行和预期总页数。

**阻塞项 / 上游问题：** 当前环境无 LibreOffice，无法进行 Word 最终分页渲染；实际分页仍需在提交端 Word/WPS 中复核。

**验证：** DOCX 5000 个正文段落与源代码选段逐行完全一致，99 个分页点，前置编号计数为零；压缩结构、重复构建哈希、Ruff 和 Black 通过。未运行 notebook、DFT、MACE、声子、在线 MP 或 AiiDA daemon，未创建 Git 提交。

## 2026-08-18 — 扩写软著申请表主要功能栏

**本次工作目标：** 访问当前工作区真实功能，将用户提供申请表中的“主要功能”扩写到 500--1300 字范围。

**已完成：**
- 新增 `scripts/update_copyright_application.py`，在不覆盖原附件的前提下定位申请表合并单元格、保留原段落和宋体 10 磅格式，并只替换“主要功能”内容。
- 新增 `docs/copyright-application/计算机软件著作权登记申请表_主要功能扩写.docx`；正文为 1281 个非空白字符，覆盖数据规范化、环境指纹分组、外部带隙任务、材料对、SQS、MACE 弛豫、混合焓、声子、竞争相凸包和 Stage 11 推荐。
- 同步项目文档、脚本自动化、资产、目录树和版本变更 ZMD 索引。

**决策 / 计划变更：** 申请表只描述当前 V0.1.0 已实现能力；高精度带隙计算仍表述为外部执行，综合结果仍定位为科研候选预筛和决策支持。本次不改变软件功能、版本或路线。

**下一步：** 在 Microsoft Word 或 WPS 中打开工作副本，确认扩写后表格分页满足提交系统要求，并复核申请表中的软件名称、版本、源程序量、日期和著作权人信息。

**阻塞项 / 上游问题：** 当前环境无 LibreOffice，无法完成 DOCX 逐页渲染；原申请表中的其他字段由用户负责最终确认，本次未修改。

**验证：** 主要功能正文 1281 个非空白字符，连同栏目标识共 1297 个；DOCX 保持 1 个表格、36 行且 ZIP 完整性通过。脚本 Ruff 和 Black 通过。未运行 notebook、DFT、MACE、声子、在线 MP 或 AiiDA daemon，未创建 Git 提交。

## 2026-08-05 — 生成软著源程序前后各 2500 行

**本次工作目标：** 从当前 V0.1.0 正式软件包生成可上交的源程序前段 2500 行和后段 2500 行。

**已完成：**
- 新增 `scripts/build_copyright_source.py`，仅汇总 `src/ssscreen/**/*.py`，按 POSIX 路径和原文件行号稳定排序，并生成完整可追溯的 PDF、文本和 JSON manifest。
- 在 `docs/copyright-source/` 生成 5000 行可检索文本与 A4 PDF；PDF 每页 50 行、共 100 页，前 50 页为前段、后 50 页为后段，页眉统一使用“新材料计算筛选软件 V0.1.0”。
- manifest 记录 25 个源文件、9944 行总源码、前后边界、零重叠、文件清单和交付物 SHA-256；同步目录说明与全部相关 ZMD 页面。

**决策 / 计划变更：** 源程序范围固定为当前权威实现 `src/ssscreen/**/*.py`，不混入测试、构建脚本、文档、历史参考或生成数据；本次不改变软件功能、版本或项目路线。

**下一步：** 上交前确认申请表和操作手册同样使用“新材料计算筛选软件 V0.1.0”，并按受理系统要求决定提交全部 100 页还是调整为其规定页数。

**阻塞项 / 上游问题：** 著作权人法定名称仍未提供；源程序材料本身不含著作权人字段，但申请表与操作手册仍须使用一致主体名称。

**验证：** 文本 `wc -l` 为 5000；Ghostscript 解析 PDF 为 100 页，前后标识各提取 2500 行；首、中、末页视觉复核清晰，无裁切或重叠。新脚本 Ruff、Black 通过。未运行 notebook、DFT、MACE、声子、在线 MP 或 AiiDA daemon，未创建 Git 提交。

## 2026-08-05 — 增加窄带隙与红外探测研发背景

**本次工作目标：** 在软著登记操作手册第一章补充窄带隙材料的作用和本软件的研发必要性。

**已完成：**
- 在 `docs/user-guide/SS-Screen_V0.1.0_软件著作权登记操作手册.md` 第一章开头新增“1.1 研发背景”，说明带隙对材料设计的意义、实验与 DFT 高通量路径、窄带隙与光伏型红外探测截止波长的关系、中波/长波红外的近似带隙范围，以及暗电流、稳定性和固溶体调控边界。
- 将第一章原 1.1--1.6 顺延为 1.2--1.7，更新编制日期为 2026 年 8 月 5 日，并在附录 C.2 增加本次修订记录。
- 使用 `scripts/build_copyright_manual.py` 重新生成同名 DOCX/PDF；源稿现为 1737 行、41558 字符、158 个标题、29 个表格和 63 个代码块，PDF 增至 37 个物理页。
- 同步项目文档、脚本自动化和版本变更 ZMD 索引。

**决策 / 计划变更：** 研发背景将红外波段与带隙关系明确标为近似关系，并保留温度、组分、载流子寿命、暗电流和稳定性等限制，不将窄带隙单独表述为器件适用性证明。本次不改变软件功能、版本或项目路线。

**下一步：** 获取著作权人法定名称，使用 `--rights-holder` 生成正式提交稿；提交时确保申请表、源程序和本手册的软件全称及 `V0.1.0` 版本完全一致。

**阻塞项 / 上游问题：** 著作权人法定名称仍未提供，当前 DOCX/PDF 仍为待替换主体名称的登记稿。

**验证：** 登记版构建器 `--check` 通过；PDF 37 页全部非空，目录、新增背景页、截止波长公式、1.1--1.7 连续小节和附录日期已视觉/文本提取复核。完整 pytest、Ruff、Black、字节码、`pip check` 和 347 个 ZMD 本地链接通过。未运行 notebook、DFT、MACE、声子、在线 MP 或 AiiDA daemon，未创建 Git 提交。

## 2026-08-04 — 变更软著登记软件全称

**本次工作目标：** 将 `V0.1.0` 软著登记操作手册的软件全称统一改为“新材料计算筛选软件”。

**已完成：**
- 更新 `docs/user-guide/SS-Screen_V0.1.0_软件著作权登记操作手册.md` 的软件全称、文档名称、版本说明、简介和附录对应表。
- 更新 `scripts/build_copyright_manual.py` 的软件全称常量，重新生成同名 DOCX/PDF；封面、页眉、DOCX/PDF 元数据和 PDF 书签由同一常量统一驱动。
- 同步项目文档、脚本自动化和版本变更 ZMD 索引。

**决策 / 计划变更：** 本次只变更软著登记版软件全称；软件简称 `SS-Screen`、Python 包/CLI 名 `ss-screen`、版本 `V0.1.0` 和手册文件名均保持不变。描述未来能力的完整功能版手册不在本次软著交付范围内。

**下一步：** 获取著作权人法定名称，通过 `--rights-holder` 生成可正式提交的 DOCX/PDF，并确保申请表和源程序鉴别材料也使用“新材料计算筛选软件 V0.1.0”。

**阻塞项 / 上游问题：** 著作权人法定名称仍未提供，当前交付物仍为待填主体名称的登记稿。

**验证：** 登记版构建器 `--check` 通过；当前 Markdown/生成器及生成 DOCX/PDF 旧全称零残留，DOCX 元数据与 PDF 页眉均使用新全称。重新生成的 PDF 保持 36 个物理页，全页渲染无空白页，封面、正文页眉和末页版本表已视觉复核。完整 pytest、Ruff、Black、字节码、`pip check` 和 347 个 ZMD 本地链接通过。未运行 notebook、DFT、MACE、声子、在线 MP 或 AiiDA daemon，未创建 Git 提交。

## 2026-08-04 — 交付 V0.1.0 软著登记操作手册

**本次工作目标：** 按软著文档鉴别材料要求，为当前 `ss-screen 0.1.0` 真实功能编制可维护、可编辑、可提交的中文操作手册。

**已完成：**
- 新增 `docs/user-guide/SS-Screen_V0.1.0_软件著作权登记操作手册.md`，覆盖软件概述、安装、项目约定、Stage 1--11 操作、完整示例、结果解释、质量控制、常见问题、命令速查和提交核对；所有命令基于当前真实 CLI，不包含完整功能版的未实现接口。
- 新增 `scripts/build_copyright_manual.py`，从同一 Markdown 源生成同名 DOCX/PDF，固定 A4 纵向、封面、软件全称与 `V0.1.0` 页眉、右上角连续页码、中文字体和 PDF 目录页码，并校验必要章节、禁用文字和著作权人占位符；`--rights-holder` 可在正式构建时一次性替换唯一占位文字。
- 最终源稿为 1718 行、40441 字符、157 个标题、29 个表格和 63 个代码块；PDF 共 36 个物理页（封面 + 35 个逻辑编号页）。
- 同步工作区目录树、文件资产、项目文档、脚本自动化和版本变更 ZMD 索引。

**决策 / 计划变更：** 登记版手册与描述未来能力的完整功能版手册分开维护；本版冻结软件全称为“固溶体可调带隙材料筛选软件”、版本为 `V0.1.0`。由于申报主体尚未提供，封面保留且仅保留一处可检测占位文字；当前 PDF 少于 60 页，按一般交存规则应提交全部文档。

**下一步：** 获取与申请表及主体证明完全一致的著作权人法定名称，使用生成器的 `--rights-holder` 重新生成 DOCX/PDF；上传前再根据当日中国版权保护中心系统提示核对并准备同名同版本的源程序鉴别材料。

**阻塞项 / 上游问题：** 申报主体法定名称未提供，因此现有文件不应直接上传。当前环境无 LibreOffice，DOCX 已做结构校验但未做逐页渲染；PDF 已通过 Ghostscript 全 36 页渲染和联系表复核。

**验证：** 登记版构建器 `--check` 通过；PDF 全页无乱码、遮挡、裁切或空白页，封面不编号、目录从逻辑第 1 页起连续编号。`--rights-holder` 临时构建的 DOCX/PDF 均出现测试主体名称且占位文字计数为零。新脚本 Ruff、Black 和字节码检查、完整 pytest、`pip check`、DOCX 元数据/页眉字段和 347 个 ZMD 本地链接均通过。未运行 notebook、DFT、MACE、声子、在线 MP 或 AiiDA daemon，未创建 Git 提交。

## 2026-08-04 — 调研软著登记操作手册编制要求

**本次工作目标：** 核对中国计算机软件著作权登记中文档鉴别材料的现行要求，并评估 SS-Screen 现有完整功能版手册能否直接用于登记。

**已完成：**
- 核对中国版权保护中心的计算机软件著作权登记指南、所需文件、填表说明和问题问答，以及中国政府网公布的《计算机软件著作权登记办法》；确认一般交存、页数/行数、A4/PDF、页眉页码、软件名称和版本一致性要求。
- 形成适用于命令行科研软件的登记版手册建议：以真实发布快照为边界，按安装、启动、逐阶段操作、输入输出、成功结果和故障处理组织内容；终端截图不是官方硬性要求，但应使用同版本的真实命令和输出证明操作路径。
- 审查 `docs/user-guide/SS-Screen_完整功能版_用户使用手册.md`：现有手册可作为内容素材，但同时出现“完整功能版 V1.4”、实现基线 `ss-screen 0.1.0` 和尚未实现接口，不适合原样作为当前版本的软著文档鉴别材料。

**决策 / 计划变更：** 无项目计划或软件功能变化。后续应在申报软件全称、著作权人和申报版本确定后，另行生成只描述该冻结版本真实能力的登记版操作手册；不把未来接口写入申报材料。

**下一步：** 确认申报主体、软件全称和申报版本，再从现有手册裁编登记版 Markdown/Word/PDF，并逐页检查名称、版本、页码、连续性、行数、截图真实性和敏感信息。

**阻塞项 / 上游问题：** 当前缺少申报主体与申报版本决策；登记前仍需以中国版权保护中心在线系统的最新提示为准。

**验证：** 2026-08-04 只读核对官方网页和当前手册/包版本；项目环境为 Python 3.11.15、`ssscreen 0.1.0`。仅更新项目日志和 ZMD 变更索引，未修改手册、源码、测试、算法、依赖或数据，未运行 notebook、DFT、MACE、声子或 AiiDA daemon，未创建 Git 提交。

## 2026-08-03 — 完成 Stage 12 统一端到端 CI 夹具

**本次工作目标：** 增加无需大型数据、网络或昂贵计算引擎的 Stage 1--11 统一文件链回归测试。

**已完成：**
- 新增 `tests/data/e2e/`，包含三种合成 rock-salt 端元、最小 robocrys condensed 描述、外部 gap 值、预期 Stage 11 推荐和边界说明；所有内容均为软件测试夹具，不是科研数据。
- 新增 `tests/test_e2e_pipeline.py`：真实执行 composition-screen、structure-match、gap-export/gap-validate、pair、random sqs-generate、mixing-enthalpy 和 recommend；Stage 7/9/10 使用相同模型 SHA/设置的确定性测试证据，不调用 MACE、Phonopy 或 MP。
- 测试在两个独立临时目录重复构建产物，核对 3 条候选、1 个结构组、3 个 gap 任务、2 个材料对、2 个 SQS、2 条混合焓，以及 `promising/L5` 和 `low-priority/L5` 推荐完全一致；验证候选不丢失、模型兼容和风险字段。
- 长期路线 Stage 12 改为完成首个可复现基线；同步 `README.md`、`docs/PROJECT_PLAN.md`、导师软件汇报和相关 ZMD 页面。

**决策 / 计划变更：**
- CI 夹具只证明跨阶段文件契约、CLI 编排和确定性分类可复现，不证明 MACE/声子/凸包或材料结果的科学正确性；昂贵引擎继续由各阶段测试和显式科研运行验证。
- 不复制被 Git 忽略的 9.9 MB 教学目录，不提交 pickle、生成结构或计算输出；pytest 只在临时目录产生中间文件。

**下一步：** 审查并版本化 Stage 1--12 开发工作树；后续 schema 变化必须显式更新预期推荐，并保持该测试在普通 CPU 上约 10 秒以内。

**阻塞项 / 上游问题：** 无新增阻塞；当前全库仍有 3 个历史 Black 格式差异，和本次端到端夹具无关。

**验证：** 新测试单独通过并在普通 CPU 上约 7.5 秒完成；完整 158 项测试、全库源码/测试 Ruff、新测试 Black 和 `pip check` 通过。夹具共 4.5 KB，测试源码未引用 MACE、Phonopy、MP API、Torch、AiiDA、网络或子进程；338 个 ZMD 本地链接零失效，导师报告 302 行且相对链接零失效，旧状态扫描和 diff 检查通过。未运行 notebook、真实 MACE、声子、在线 MP、DFT 或 AiiDA daemon，未创建 Git 提交。

## 2026-08-03 — 更新 Stage 11 导师软件汇报

**本次工作目标：** 将 `docs/software_status_report_2026-08-04.md` 更新为可直接汇报的 Stage 1--11 当前状态。

**已完成：**
- 补充 Stage 11 的 `pair_index + structure_id` 推荐单元、三类判定、L2--L6 证据等级、默认混合焓/凸包阈值及“不使用不透明总分”的解释。
- 修正数据流图，使 Stage 5 的端元带隙/材料对证据进入 Stage 11；教学结果表新增 `promising/L5` 和 `low-priority/L5` 自动分类及缺陷、NAC、离线快照风险说明。
- 增加可从既有 Stage 5、8--10 产物现场重建 CSV/Markdown/JSON 的 Bash 命令；校正核心算法文档数量和 Stage 7--11 开发工作树范围。
- 同步 `ZMD/04_项目文档与开发计划/README.md` 和 `ZMD/07_版本与变更索引/README.md`。

**决策 / 计划变更：** 无项目计划变化。汇报继续将 Stage 11 表述为研究决策支持，不表述为正式材料发现或稳定性证明。

**下一步：** 汇报前填写汇报人信息，并在同一终端确认现有教学报告和 `ss-screen recommend --help` 可访问。

**阻塞项 / 上游问题：** 无新增阻塞；真实高精度带隙、缺陷、收敛研究和一致设置 DFT 复核仍是正式科研结论的前提。

**验证：** 报告共 297 行、31 个标题和 10 个成对代码围栏；8 个相对链接零失效，现场 Stage 11 命令引用的 8 个教学文件全部存在，旧状态表述扫描和 `git diff --check` 通过。仅修改文档与 ZMD，未运行测试、notebook、MACE、声子、在线 MP、DFT 或 AiiDA daemon，未创建 Git 提交。

## 2026-08-03 — 完成 Stage 11 可审计综合推荐

**本次工作目标：** 实现 Stage 11，将端元对、高精度带隙、混合焓、声子、竞争相凸包和可选缺陷证据汇总为可复现的研究优先级报告。

**已完成：**
- 新增 `src/ssscreen/stability/recommendation.py` 和 `RecommendationSettings`，按 `pair_index + structure_id` 保留每个材料对/SQS，校验端元 gap 与 Stage 8--10 模型 SHA，显式记录缺失、失败、歧义、不兼容、来源警告和下一步。
- 新增顶层 `ss-screen recommend`，输出逐候选 `recommendations.csv`、Markdown 审计报告和可选 JSON summary；支持 gap 方法覆盖、可选缺陷、`--require-defects` 和全部具名阈值。
- 实现 `promising`、`uncertain`、`low-priority` 三类判定和 L2--L6 证据等级。明确负面信号优先降为 low-priority；核心证据缺失/边界/不兼容为 uncertain；完整 L5 且无配置风险才为 promising。排序不使用不透明综合分数。
- 新增 `tests/test_stability_recommendation.py` 并扩展 CLI 测试，覆盖完整/缺失证据、模型冲突、可选/强制缺陷、阈值校验和命令参数传递。
- 新增 `docs/algorithm_recommendation.md`，同步 README、项目计划、长期路线、中文用户手册 V1.4 Markdown/Word、导师汇报和全部相关 ZMD 页面。
- 使用既有教学产物运行 Stage 11，在 `work/new-user-tutorial/12_recommendation/` 生成 2 条 L5 推荐：CaSe-CaS 为 promising；CaTe-CaS 因高混合焓和显著虚频为 low-priority。本地教学审计报告已同步。

**决策 / 计划变更：**
- Stage 11 作为决策支持而非材料发现结论；默认混合焓 `25/50 meV/atom` 和同 MLP 凸包 `0.025/0.1 eV/atom` 只作为可配置初筛阈值。
- directness、离线 MP 快照范围和未使用 NAC 保持可见风险，不单独作为硬过滤。缺陷结果默认可选；只有显式 `--require-defects` 时，缺失缺陷才产生不确定性。
- 路线图 Stage 11 改为已完成；Stage 12 的统一端到端 CI 夹具、缺陷执行/排序、目标带隙入口和正式科学验证仍未完成。

**下一步：** 用真实高精度带隙和更多化学体系校准推荐阈值，增加可提交的 Stage 1--11 微型端到端夹具，并设计缺陷计算/排序以提供 L6 证据。

**阻塞项 / 上游问题：** 无新增上游问题。真实 HSE06/mBJ 结果、缺陷形成能、SQS/声子/竞争相收敛和一致设置 DFT 复核仍是正式科研结论的外部前提。

**验证：** 项目 Python 3.11.15、`ssscreen 0.1.0`；完整 157 项测试、全库 Ruff、涉及 Python 文件 Black、`pip check`、CLI 帮助和教学 Stage 11 冒烟通过。手册构建器生成 81272 字节 DOCX，112 个标题、18 个表、50 个代码块，结构检查通过；334 个 ZMD 本地链接零失效，diff 检查通过。未运行 notebook、DFT、MACE、声子计算或 AiiDA daemon，未创建 Git 提交。

## 2026-08-03 — 编写导师软件阶段性汇报

**本次工作目标：** 为 2026-08-04 导师汇报编写一份可直接展示的 SS-Screen 中文 Markdown 软件报告。

**已完成：**
- 新增 `docs/software_status_report_2026-08-04.md`，按科学问题、核心方法、Stage 1–12 完成度、工程状态、教学演练、科学边界、主要缺口、下一阶段和需导师确认问题组织内容。
- 报告纳入 Stage 1–10 真实能力、151 项测试状态、CaSe-CaS/CaTe-CaS 教学结果及其合成带隙、小 SQS、MLP 和 2023 MP 快照限制，并提供只读 Bash 现场演示顺序。
- 同步 `ZMD/04_项目文档与开发计划/README.md` 和 `ZMD/07_版本与变更索引/README.md`。

**决策 / 计划变更：**
- 无正式项目计划变更。汇报将当前成果表述为可运行的 Stage 1–10 开发版本与候选预筛链路，不表述为稳定发布版或正式新材料发现。

**下一步：** 汇报前填写汇报人信息并确认演示终端；请导师决定优先推进目标带隙/用户数据 MVP，还是先完成 Stage 11 综合推荐与缺陷排序。

**阻塞项 / 上游问题：** 无新增阻塞；目标带隙模型、WBM 原始构建、真实高精度带隙、Stage 11、缺陷排序和 DFT 复核等既有缺口已在报告中明确列出。

**验证：** 报告 263 行，全部相对文件链接存在；涉及报告与 ZMD 页面 `git diff --check` 通过。仅修改文档和导航，未运行 notebook、在线请求、DFT、MACE、AiiDA daemon 或完整测试套件。

## 2026-08-03 — 目标带隙检索与用户数据双入口产品设计

**本次工作目标：** 将 SS-Screen 从固定阈值候选生成管线重新定义为支持目标带隙查询、用户结构/计算结果上传及 MP/私有数据混合检索的软件。

**已完成：**
- 核对当前 `pair/pairing.py`、`pair/gap_feedback.py`、MP/WBM 规范化入口和 CLI：现有 Stage 5 使用固定高低带隙阈值枚举端元对，尚未把用户给定的 `target_gap` 转换为目标组分、预测误差和验证状态；当前也没有通用用户数据集入口。
- 定义三种统一检索范围：MP×MP、用户×MP、用户×用户。用户结构和计算结果分别进入结构规范化/指纹匹配与版本化 calculation 记录；无带隙结构必须补充预测或高精度计算，不能静默假定带隙。
- 定义三级科学证据：端元带隙覆盖目标、基于线性/弯曲参数的目标组分预测、目标组分 SQS 弛豫和显式带隙计算验证。仅凭端元插值不得表述为已经获得目标带隙固溶体。
- 形成产品数据流：预计算并索引 MP 的组成模板、环境指纹和 gap/provenance；高频目标带隙查询只做过滤、匹配和排序；上传结构只增量计算其指纹并与 MP/用户索引匹配；选中候选再异步进入 SQS、MLP 稳定性和高精度 gap 验证。

**决策 / 计划变更：**
- 无正式计划变更。建议后续以 `ScreenRequest`、统一 `MaterialRecord`/`CalculationRecord`、`AlloyCandidate` 和 `ValidationJob` 为产品核心对象，并保留现有 gap 任务/结果哈希契约；需经设计文档和测试后再更新 `PROJECT_PLAN.md`。

**下一步：** 编写目标带隙检索设计规范，先实现 MP 预计算索引 + `target_gap/tolerance` 查询 + 通用上传 schema + MP/用户混合匹配的 MVP，再接入由预测目标组分驱动的 SQS 和显式 gap 验证。

**阻塞项 / 上游问题：** 目标组分的带隙弯曲模型及不确定度尚未定义；用户仅上传结构时必须选择带隙计算/预测后端，否则不能完成目标带隙判定。

**验证：** 只读核对当前正式源码、CLI 和既有测试契约；同步项目日志与 ZMD 索引。未修改正式源码、测试、算法、依赖或数据，未运行 notebook、DFT、MACE、AiiDA daemon 或完整测试套件。

## 2026-08-03 — 完成新用户端到端教学演练

**本次工作目标：** 以新用户视角从已接入的 MP 离线快照逐步运行当前 Stage 1 至 Stage 10，并形成可复核的本地审计报告。

**已完成：**
- 在被 Git 忽略的 `work/new-user-tutorial/` 中生成 370 个本地教学产物（约 9.9 MB），覆盖三条真实 MP rock-salt 结构的组成筛选、robocrys 凝练、环境分组、合成带隙契约校验、材料配对、icet SQS、MACE 弛豫、混合焓、Phonopy 声子和离线 MP 竞争相凸包。
- 两个 x=0.5 SQS 均由 icet 写出为 16 原子结构；严格 MACE 分支以 `fmax=0.005 eV/Å` 完成 2 个 SQS 与 3 个端元，混合焓分别为 CaSe-CaS `+10.417 meV/atom`、CaTe-CaS `+79.114 meV/atom`。
- Stage 9 的 21/21 个 float64 MACE 力任务成功；CaSe-CaS 无显著虚频，CaTe-CaS 最低频率 `-2.735 THz` 且分类为 unstable。声子仅使用 1x1x1、16 原子教学超胞且未应用 NAC。
- 离线 MP 在 `e_hull<=0.1 eV/atom` 下为 Ca-S-Se/Ca-S-Te 查询 75 条、去重为 46 个竞争相，数据库 SHA-256 为 `d54bca48d1e00bdfd8db7c1e5a7b5844ccb755b948335930f09fe85444a7ebb8`；凸包独立分支统一使用 `fmax=0.03 eV/Å` 后 46/46 竞争相成功，严格完整集凸包得到 `10.451/79.113 meV/atom`，均为 cutoff 内亚稳。
- 新增本地报告 `work/new-user-tutorial/12_report/README.md`，记录阶段账本、关键 SHA、设置分支、最终教学判断和正式科研升级清单；`.gitignore` 新增 `/work/`，防止生成结构与计算结果进入版本控制。

**决策 / 计划变更：**
- 无正式路线变化。CaSe-CaS 仅作为本次教学演练中的相对更强候选；由于带隙为合成数据、SQS/声子规模有限、稳定性为 MACE 预筛且 MP 快照截止 2023 年，禁止将该结果表述为正式科研发现。
- 混合焓/声子严格分支与凸包默认分支分别保持内部能量一致性，不跨分支混合能量。Stage 11 自动综合推荐仍未实现，本次报告是人工审计交付而非新增软件命令。

**下一步：** 以真实高精度带隙替换教学结果，在仓库外构建完整 MP/WBM 输入，增加多组分/大 SQS/声子超胞与参数收敛，并对 CaSe-CaS 及关键分解相做一致设置的 DFT 复核；随后实现可测试的 Stage 11 推荐与缺陷排序。

**阻塞项 / 上游问题：** WBM 正式 extxyz/summary/原始 step 仍未提供；离线 MP 不支持在线 thermo-type 过滤且可能缺少 2023 年后的竞争相；MACE checkpoint 再分发许可证仍需确认。本次未运行 notebook、DFT 或 AiiDA daemon。

**验证：** `work/` Git 忽略规则、报告/ZMD 相对链接、关键产物 SHA 和结果 schema 通过；`pip check`、Ruff 与完整 151 项测试通过；未创建 Git 提交。

## 2026-08-03 — 开源工作流框架与成熟软件架构调研

**本次工作目标：** 对照材料科学和通用编排开源项目，评估 SS-Screen 从分阶段 CLI 发展为成熟工作流软件的架构路线。

**已完成：**
- 核对 atomate2/jobflow、AiiDA、pyiron/pyiron_base、Dagster、Prefect、Maggma、Snakemake、DVC 和 OPTIMADE 的官方仓库与文档，比较其工作流建模、科研 provenance、执行后端、数据资产、项目管理和服务化能力。
- 结合当前 Stage 1–10、外部高精度带隙任务/结果契约及 CLI 实现，确认本项目已有确定性任务 ID、严格结果校验、原子写入、显式失败状态和模型/参数 provenance 等可靠基础；主要成熟度缺口是全局 DAG、统一 Run/Task/Attempt/Artifact 状态、工作流级恢复/重试、元数据与制品存储、插件机制和服务接口。
- 形成建议架构：保留当前科研算法与版本化文件契约作为科学内核，新增独立的工作流 IR、运行控制层、执行适配器、元数据数据库和内容寻址制品存储；工作流语义优先参考 jobflow/atomate2，provenance 和插件边界参考 AiiDA，科研 Project/Job 体验参考 pyiron。
- 确定建议的首个垂直切片为 Stage 1–5：覆盖数据导入、分组、外部 gap 等待/上传/校验、断点恢复和 pair 生成，再扩展 Stage 6–10 的 GPU/HPC 分支。

**决策 / 计划变更：**
- 无正式计划变更。本次只形成架构建议；在 ADR 和小型 PoC 验证前，不把 jobflow、AiiDA、Dagster 或 Prefect 设为必选核心依赖。高精度 DFT/AiiDA 执行仍保持包外边界。

**下一步：** 编写工作流控制层 ADR，定义 `Project`、`Run`、`Task`、`Attempt`、`Artifact`、`Event` 与状态机，并以 Stage 1–5 实现 SQLite + 本地内容寻址存储的可恢复 PoC，对比轻量自有执行器与 jobflow 集成成本。

**阻塞项 / 上游问题：** 无；成熟化路线尚需通过 PoC 确认执行框架选型和迁移成本。

**验证：** 只读核对当前源码/计划与上述开源项目官方资料；同步项目日志和 ZMD 索引。未修改正式源码、测试、算法、依赖或数据，未运行 notebook、DFT、MACE、AiiDA daemon 或完整测试套件。

## 2026-08-03 — Stage 1 接入外部 MP 离线快照

**本次工作目标：** 按只读审计、兼容性验证、provenance 和正式 CLI 契约接入用户指定的 `mp_offline` SQLite 数据库。

**已完成：**
- 只读审计 `/vepfs-mlp2/c20250609/public/zuolong/mp-offline/mp-offline/data/default.db`：文件大小 2220736512 字节，`quick_check=ok`，SHA-256 为 `d54bca48d1e00bdfd8db7c1e5a7b5844ccb755b948335930f09fe85444a7ebb8`，与历史 Stage 10 冒烟完全一致。
- 数据库包含 155361 条 `material_summary`、155361 个唯一材料 ID、零 deprecated 和零重复 ID；非 deprecated 的 `e_hull<=0.01 eV/atom` 集合为 46675 条，结构、组成和带隙无缺失。快照文档最大更新时间为 2023-11-07，builder 记录 emmet 0.72.13 / pymatgen 2023.10.4。
- 扩展 `src/ssscreen/data/mp.py`：离线/API 查询显式限定非负 hull 能并排除 deprecated；离线端只投影 Stage 1 必需字段；DataFrame attrs 与默认 `<output>.provenance.json` 保存查询条件、数据库路径/大小/SHA、样本文档 builder meta、数据库/API 版本、包版本和快照范围警告。
- 扩展 `dataset mp` CLI：`--offline-db` 校验真实文件，新增可选 `--provenance` 并显示实际 sidecar；扩展既有 MP/CLI 测试。同步 README、项目计划、中文手册 Markdown/Word V1.3 和相关 ZMD 页面。
- 使用真实只读快照完成 `mp-1672` 端到端小样本：得到 CaS、数据库带隙 2.3819 eV、`e_hull=0`，pickle 重载后 provenance 完整保留；临时一行数据产物已清理，外部数据库未修改或复制。

**决策 / 计划变更：**
- 该数据库作为固定、可复现的历史 MP 基线接入；“完整”严格限定于其 SHA 标识的 2023 快照，不替代当前在线 MP。Stage 1 和 Stage 10 均继续要求显式选择 API/离线来源，不自动混合或回退。
- 全量 `mp.df` 属于仓库外大型数据产物；在用户指定并授权仓库外可写输出目录前不生成，不把它放入 Git 工作区。

**下一步：** 用户指定仓库外可写输出目录后，使用该数据库生成 46675 条 `max_e_hull=0.01` 的正式 `mp.df` 与 provenance sidecar，再核对输出行数、索引唯一性、分布和随机结构样本；WBM 入口仍需另行补齐。

**阻塞项 / 上游问题：** 数据库接入无代码阻塞；仅缺全量输出目录授权。快照自身说明其用途是缓存且不提供长期 schema migration，正式最终竞争相研究仍应按需与在线 MP 对照。

**验证：** 项目 Python 3.11.15、`ssscreen 0.1.0`；完整 151 项测试、全库 Ruff、MP/CLI 相关 Python 文件 Black、`pip check`、`dataset mp --help`、Word 手册结构检查和 `git diff --check` 通过。手册构建脚本存在既有 Black 排版差异，本次只更新版本常量；未运行在线 MP、notebook、DFT、MACE 或 AiiDA daemon。

## 2026-08-03 — 核查 pairwise-screening 中的 WBM 数据入口

**本次工作目标：** 只读检查 `/vepfs-mlp2/c20250609/public/zuolong/pairwise-screening` 是否包含可作为 SS-Screen Stage 1 入口的 WBM 数据库或 extxyz。

**已完成：**
- 确认外部 `wbm-dataset/` 仅包含说明、转换/凝练脚本、257,489 行作业编号和 60,225 个稀疏的 `condense/structures/wbm-*.json`；未找到 `wbm-dataset.xyz`、`summary.txt`、`cleaned_summary.txt`、`step_1.json.bz2` 至 `step_5.json.bz2`、DataFrame、SQLite 或 Parquet 数据库，也没有 WBM `condensed/` 输出。
- 样本 JSON 仅含 pymatgen 晶格和原子位点，不含 Stage 1 所需的 `WBM_gap`、`WBM_e_hull`、`WBM_step` 等元数据；文件 ID 从 `wbm-0` 稀疏分布到 `wbm-257493`，与说明中 257,489 条记录的边界也不一致。
- 对照 `src/ssscreen/data/wbm.py`：当前 `dataset wbm` 只消费已构建 extxyz 及可选 summary，因此该外部目录不能直接作为完整 WBM Stage 1 入口；不应将缺失 gap/hull 元数据默认为零后继续科学筛选。
- 另外确认 `pair-screening/binary-group-df.json` 可由当前加载器读取，含 222 个二元组、952 个成员和 437 个唯一 WBM ID，可作为后续 pair 阶段的历史产物而非 WBM 源数据；`ternary-group-df.json` 仍因历史 `Compositions` 字段报 `KeyError: 'compositions'`。

**决策 / 计划变更：**
- 无路线变更。不将该不完整、缺少热力学/带隙元数据的结构子集接为 Stage 1 数据库；仅将可加载的二元 group JSON 视为下游复现入口。

**下一步：** 在仓库外定位官方/已验证的完整 `wbm-dataset.xyz`，或齐全五个原始 step 与 summary 后实现唯一行对齐、全量字段验证和可追溯转换；如需复现历史二元结果，可直接从现有 binary group/gap 产物进入后续阶段。

**阻塞项 / 上游问题：** 指定只读快照的 WBM 数据资产不完整，且结构 ID 边界与上游 README 记录数不一致；本次未修改该外部目录。

**验证：** 项目 Python 3.11.15、`ssscreen 0.1.0`；只读遍历外部文件名/大小/计数、样本结构 JSON、历史转换脚本和当前 WBM 加载器，并以当前 `load_group_df` 做内存加载核对；未运行 notebook、在线请求、DFT、MACE 或 AiiDA，未修改源码、测试或数据。

## 2026-08-03 — 审查 Stage 1 MP/WBM 数据准备度

**本次工作目标：** 核对 Materials Project 与 WBM extxyz 在当前工作区中的软件、依赖、测试和真实数据资产是否已可用。

**已完成：**
- 确认 `dataset mp` 已实现显式 `offline`/`api` 后端，`dataset wbm` 已实现已构建 extxyz 消费；`composition-screen` 可重复接收 `--df` 并在内存中合并 MP/WBM 标准化表。
- 确认项目 `.venv` 中 `mp-api 0.46.4`、`mp-offline 0.1.0`、`ase 3.26.0` 和数据层依赖完整，`pip check` 通过；MP/WBM/CLI 聚焦测试通过。
- 当前可见工作区及同级路径中未找到离线 MP `default.db`、`wbm-dataset.xyz`、WBM `summary.txt` 或原始 `step_*.json.bz2`；当前进程也未配置 `MP_API_KEY` 或 `~/.pmgrc.yaml`。
- 核对历史 WBM 转换脚本与完整性审计：正式代码仍只消费已构建 extxyz，未迁移 5 个原始 step 与 summary 的脏区唯一对齐、全量验证和可追溯构建。

**决策 / 计划变更：**
- 无路线变更。Stage 1 应表述为“读取与标准化软件已实现，完整大型数据保持在仓库外”，不应表述为当前工作区已包含可直接运行的 MP/WBM 数据。

**下一步：** 先显式挂载并记录一个可用的 MP 离线快照（或安全配置在线凭据）与官方/经验证的 WBM extxyz；正式全量筛选前补充 WBM 必需字段、行对齐和原始 step-to-extxyz provenance 校验。

**阻塞项 / 上游问题：** 当前无可发现的 MP/WBM 完整数据资产，因此不能宣称 Stage 1 已开箱可跑；历史 2.1 GB MP 快照的旧版本范围警告仍然有效。文档规定的 `/home/...` 路径在当前环境不存在，实际工作区为 `/vepfs-mlp2/...`。

**验证：** Python 3.11.15、`ssscreen 0.1.0`、`pip check`、MP/WBM/CLI 聚焦测试及三个 Stage 1 CLI 帮助通过；未运行在线 MP 请求、notebook、DFT、MACE 或 AiiDA daemon，未修改源码、算法、依赖或数据。

## 2026-08-03 — 生成当前软件逻辑画布

**本次工作目标：** 基于当前真实源码、CLI 和项目文档，清晰展示 SS-Screen 的端到端数据流、模块依赖和科研约束。

**已完成：**
- 核对项目 Python 3.11.15、`ssscreen 0.1.0`、24 个正式 Python 源文件、当前 CLI 命令树、模块导入关系及 Stage 1–10 的真实输入输出契约。
- 生成 Codex 会话内交互逻辑画布，提供“端到端流程”“模块依赖”“科研约束”三种视图和节点聚焦；明确 Stage 1a 组成筛选与 Stage 2 robocrys 描述在 Stage 3 汇合，Stage 8/9/10 从 Stage 7 并行分叉。
- 在画布中区分包内实现、包外高精度带隙执行、可选科研引擎和尚未实现的缺陷排序/综合推荐；画布属于本次会话展示，不作为仓库正式软件资产或权威实现。
- 同步 `ZMD/04_项目文档与开发计划/README.md` 和 `ZMD/07_版本与变更索引/README.md`；未修改正式源码、测试、算法、依赖或数据。

**决策 / 计划变更：**
- 无项目计划变更。架构表达以真实实现为准：高精度带隙计算继续保持包外边界；混合焓、声子和竞争相凸包是共享 Stage 7 弛豫结果的并行证据链，不互相构成串行前置条件。

**下一步：** 实现缺陷排序或综合推荐时，同步更新主数据流、CLI/ZMD 导航和逻辑画布中的规划节点。

**阻塞项 / 上游问题：** 无代码阻塞；文档规定的 `/home/zuolong/projects/ss-screen-learning-20260722` 在当前环境不存在，实际工作区仍为 `/vepfs-mlp2/project-battery/zuolong/ss-screen-learning-20260722`。

**验证：** Playwright 在 736 px 与 328 px 内容宽度、浅色和深色主题下检查三个视图；节点文字、控件和连线均无越界、重叠或穿越无关节点，视图切换与节点聚焦正常且无浏览器运行错误；325 个 ZMD 本地链接失效数为 0。未运行 notebook、DFT、MACE、AiiDA daemon 或完整测试套件。

## 2026-08-01 — Stage 10 接入 mp_offline 竞争相快照

**本次工作目标：** 让竞争相与凸包稳定性流程除在线 Materials Project API 外，也能从用户指定的本地 `mp_offline` SQLite 快照获取竞争相结构。

**已完成：**
- 扩展 `src/ssscreen/stability/competing.py`：`export_competing_phases` 和一步式 pipeline 支持显式 `api`/`offline` 后端；离线路径枚举候选体系的全部非空子体系，以 `chemsys`、`energy_above_hull` 和 `deprecated` 索引查询必要字段，复用原有 primitive/原子数/去重/manifest/MACE/凸包契约。
- 离线 manifest、导出报告和最终 `phase_stability.csv`/summary 贯通 `mp_source_backend`、snapshot scope、数据库版本/SHA 和快照警告；离线库不伪装在线 thermo-type 过滤。不同 backend/数据库来源混合时即使使用 `--allow-incomplete` 也硬拒绝。
- `stability competing-export` 与 `phase-diagram` 新增 `--mp-backend [api|offline]` 和 `--offline-db`；只有 API 后端隐藏提示密钥，离线后端强制显式数据库路径且不读取密钥。
- 修复 `src/ssscreen/data/mp.py` 对真实 `MPOffline.query_all()` SQLAlchemy 单实体 Row 的解包，使现有 `dataset mp --backend offline` 可读取真实本地包。项目 `.venv` 安装 `mp_offline 0.1.0`、SQLAlchemy 2.0.51 和构建依赖；数据库仍在仓库外只读位置。
- 新增 5 个 Row/provider/CLI/混合来源拒绝测试；同步 README、项目计划、长期路线、Stage 10 算法说明、中文手册 Markdown/Word 和全部相关 ZMD 页面。

**决策 / 计划变更：**
- API 和离线快照是显式互斥的结构发现来源，禁止查询失败时自动回退或把不同来源混入一次凸包。MP 能量仍只筛选结构，最终凸包继续严格使用同一 MLP 能量基准。
- 离线 `competing_set_complete=true` 只表示相对于数据库 SHA 标识的快照没有导出/弛豫缺失；本地缓存缺少在线 thermo-entry 的 scheme 过滤，且较旧快照可能没有新增竞争相。

**下一步：** 对真实 Stage 7 候选分别使用在线 MP 与该离线快照导出竞争相，比较条目覆盖差异；正式大规模运行优先按 manifest 分阶段完成同 MACE 弛豫，再计算凸包。

**阻塞项 / 上游问题：** 当前离线查询、CLI 和 provenance 无代码阻塞。只读数据库约 2.1 GB、包含 155361 条 summary，快照使用 emmet 0.72.13/pymatgen 2023.10.4，可能落后于当前在线 MP；首次 pip 构建隔离受默认镜像 SSL 影响，改用项目 `.venv` 安装 `flit_core`/SQLAlchemy 后以 `--no-build-isolation` 成功安装本地包。未修改外部 `mp-offline` 仓库或数据库。

**验证：** Python 3.11.15、`ssscreen 0.1.0`、`mp_offline 0.1.0`、SQLAlchemy 2.0.51 和 `pip check` 正常；完整 151 项测试、`ruff check src tests scripts`、本次生产代码/测试 Black、两个 Stage 10 CLI 帮助、Word 手册结构检查和 325 个 ZMD 本地链接通过。真实只读 Li-O 冒烟在 `e_hull<=0.05 eV/atom` 下查询并写出 18/18 个竞争相、零失败，数据库 SHA-256 为 `d54bca48d1e00bdfd8db7c1e5a7b5844ccb755b948335930f09fe85444a7ebb8`；真实 SQLAlchemy Row `mp-1672` 正确标准化为 CaS。临时产物已清理，未运行 MACE、DFT、notebook 或 AiiDA。

## 2026-07-31 — 实现外部高精度带隙任务与结果契约

**本次工作目标：** 将高精度带隙计算固定为软件外部能力，由 SS-Screen 导出可追溯任务并严格接收、校验和分析用户返回的结果。

**已完成：**
- 重构 `src/ssscreen/pair/gap_export.py`：加入 schema v1、确定性 `task_id`、结构 SHA-256、JSON/CIF/POSCAR 导出、结果模板和方法元数据模板；严格校验任务表身份、返回任务/材料/化学式/方法/结构/设置、状态、有限非负带隙、directness 和重复记录。
- `gap-validate` 可输出规范化结果、拒绝行和 JSON 审计报告，区分完全未返回与已返回但未获接受的任务；未知 directness 保持为空，失败/未收敛/跳过状态可审计，重复结果不再静默取最后一条。无任务表时保留历史七列 CSV/JSON 兼容。
- 扩展 `gap-export`/`gap-validate` CLI、回填入口和 9 个测试函数；移除 `pyproject.toml` 中未实现且易造成误解的 `dft` extra。同步 README、带隙算法说明、项目计划、长期路线、中文手册 Markdown/Word 和全部相关 ZMD 页面。
- 明确 AiiDA 只可作为外部执行平台：SS-Screen 不读取 profile、数据库/消息代理、SSH、Computer/Code、调度器或赝势配置；外部脚本只需传递标准任务/结果字段，可追加 `aiida_process_uuid` 等无凭据 provenance 列。

**决策 / 计划变更：**
- 不在 SS-Screen 内实现或集成 VASP、ABACUS、AiiDA 等高精度带隙执行后端。软件边界固定为“任务/结构导出 → 用户外部计算 → 严格结果接收 → 回填分析”，从而避免许可证、集群和方法实现耦合。
- 缺陷计算后端保持独立的后续设计问题，不因移除带隙 `dft` extra 而预先决定。

**下一步：** 让一个真实外部 HSE06/mBJ 或 AiiDA 收集脚本按 `gap_results_template.csv` 返回小批量结果，使用填写完整的 `method_metadata.json` 做端到端验收；随后可增加面向 Web/API 的上传入口，但复用同一 schema 和校验器。

**阻塞项 / 上游问题：** 当前文件契约和 CLI 无代码阻塞；尚未用真实外部计算结果做跨平台验收。文档规定的 `/home/...` 路径在当前环境不存在，实际工作区为 `/vepfs-mlp2/...`。未修改用户上传的 `aiida-module/`，未运行 notebook、DFT 作业或 AiiDA daemon。

**验证：** 项目 Python 3.11.15、`ssscreen 0.1.0` 和 `pip check` 正常；完整 146 项测试、`ruff check src tests scripts`、本次生产代码/测试 Black、`gap-export`/`gap-validate` 帮助、Word 手册结构检查和 325 个 ZMD 本地链接通过。手册构建脚本存在既有 Black 排版差异，本次仅更新一行封面版本号，未扩大格式化范围。

## 2026-07-31 — 实现 Stage 10 MP 竞争相与同 MACE 凸包

**本次工作目标：** 使用 Materials Project API 补齐竞争相结构获取、同 MLP 能量基准弛豫和候选 SQS 凸包筛选能力。

**已完成：**
- 新增 `src/ssscreen/stability/competing.py`：从 Stage 7 候选提取化学体系，以 `MPRester.get_entries_in_chemsys()` 获取父体系和全部子体系近凸包结构，保存 MP entry ID、数据库版本、检索时间、thermo scheme、结构哈希和逐条状态；API 初始化、请求和每体系均有可配置超时。
- 在线命令每次通过隐藏提示读取 API key，仅在请求期间临时设置当前进程 `MP_API_KEY`，结束后恢复环境；manifest、报告、CLI 参数和配置均不保存密钥。新增 `competing-export`、`competing-relax`、`convex-hull` 和一步式 `phase-diagram`。
- 扩展 `src/ssscreen/stability/relax.py`，使 MP 竞争相复用 Stage 7 的 MACE FIRE、断点续算、完整 E/F/stress、收敛和结构 QC 契约；禁止失败后回退到 MP DFT 能量。
- 凸包收集严格要求候选与竞争相的后端版本、模型 SHA-256、dtype 和完整弛豫/QC 设置一致；输出候选相对竞争相凸包的带符号裕量、常规非负 `e_above_hull`、分解相及分数、加入候选后的全部 hull entries 和完整性状态。缺失、跳过、未收敛或来源不兼容默认拒算，`--allow-incomplete` 只生成 uncertain 诊断。
- 新增 `tests/test_stability_competing.py` 和 `docs/algorithm_competing_phase_hull.md`；更新 pyproject 的已验证 `mp-api>=0.46.4,<0.47` 契约、README、PROJECT_PLAN、长期路线、中文手册 Markdown/Word 和全部相关 ZMD 页面。

**决策 / 计划变更：**
- Stage 10 从计划功能转为当前能力。Materials Project 只负责发现条目和提供结构，最终凸包不混用 MP DFT 与 MACE 能量；负的 `energy_relative_to_competing_hull_eV_per_atom` 表示候选降低已有竞争相凸包，常规 `energy_above_hull` 截断为零。
- 当前首版只支持在线 MP API；每次访问均要求用户重新输入密钥。离线竞争相缓存可在保持 manifest 契约不变的前提下后续增加。

**下一步：** 使用真实 Stage 7 SQS 与同一 MACE checkpoint 分阶段弛豫完整竞争相集合，评估不同 MP `e_above_hull` 窗口的凸包收敛；随后实现 Stage 11 综合推荐，并以 DFT 复核重点候选和关键分解相。

**阻塞项 / 上游问题：** 当前 Stage 10 无代码阻塞；未实现离线 MP 竞争相输入、有限温自由能或 DFT 凸包适配器。只读参考 MACE 脚本在竞争相 MLIP 失败时回退到未校正 DFT 能量，本实现明确拒绝该行为且未修改上游。文档中的 `/home/...` 与实际 `/vepfs-mlp2/...` 工作区路径差异仍存在。

**验证：** 完整 134 项测试、`ruff check src tests scripts`、涉及文件 Black、`pip check`、字节码编译、CLI 帮助、手册结构检查和 325 个 ZMD 本地链接检查通过；源码/测试/文档中用户 API key 字面量命中为 0。真实 MP API Ca-S 冒烟读取数据库 `2026.04.13` 的 31 条 `e_hull<=0.05 eV/atom` 记录，30 条在显式 100 原子门槛内成功导出且哈希有效，1 条 104 原子结构准确标为 skipped，零查询失败，临时产物已删除。未运行 DFT、notebook 或 AiiDA。

## 2026-07-31 — 实现 Stage 9 MACE 声子谱

**本次工作目标：** 在 `ss-screen` 中实现以 MACE 计算固定结构能量/力、以 Phonopy 构造谐波声子谱的可恢复 Stage 9 工作流。

**已完成：**
- 项目 `.venv` 新增 Phonopy 4.4.0、SeeK-path 2.2.1、symfc 和 phonors；`pyproject.toml` 新增独立 `[phonon]` extra，保持现有 NumPy 1.26.4 / MACE 0.3.14 / Torch 2.5.1+cu121 运行时不变。
- `src/ssscreen/stability/mlp.py` 新增后端中立 `SinglePointOutcome`/`ForceBackend` 和 MACE `evaluate()`，每个位移结构保存 MLIP 总能、每原子能、完整力、应力、模型哈希和运行指纹。
- 新增 `src/ssscreen/stability/phonon.py`：Stage 7 结构/QC/哈希预检、自动或显式超胞、Phonopy 有限位移、任务 manifest、逐任务原子续算、参考超胞力扣除、完整力覆盖/来源检查、力常数对称化、Gamma-centered q 网格、SeeK-path 频带、DOS、CSV/JSON/NPZ/HDF5/YAML 和 PNG/PDF 输出。
- 新增 `stability phonon-export`、`phonon-forces`、`phonon-collect` 和一步式 `phonon-run`；所有数值默认值集中在 `PhononSettings`，超胞原子数、输入残余力、位移、网格、频带点数和虚频容差均可配置。
- 新增 `tests/test_stability_phonon.py` 并扩展 CLI/依赖测试；同步 README、PROJECT_PLAN、长期路线、中文手册 Markdown/Word 和全部相关 ZMD 页面。

**决策 / 计划变更：**
- Stage 9 从计划功能转为当前能力。动力学分类使用均匀 q 网格而不是只看高对称路径；显著虚频阈值随结果保存，微小负频率保留原值并作为数值容差警告。
- 默认要求 Stage 7 结构的最大残余力不超过 `0.01 eV/Å`，并建议正式声子计算先以约 `0.001–0.005 eV/Å` 收紧弛豫；`--allow-loose-input` 只能显式绕过。
- 当前直接力后端只提供 MACE。`stable` 仅表示在给定谐波 MLIP、超胞、网格和容差下未检测到显著虚频，不代表有限温混溶、相图稳定或实验可合成。

**下一步：** 对真实 SQS 先做紧收敛 Stage 7 弛豫，再用至少两组超胞/位移幅度检查声子收敛；重点极性体系后续增加 Born 电荷/介电张量与 NAC 输入，重要候选用 DFT 有限位移复核。

**阻塞项 / 上游问题：** 当前 MACE 声子谱无代码阻塞；尚未实现 VASP/ABACUS 力结果适配器、NAC、非谐声子和有限温振动自由能。只读参考工程的集群提交脚本含硬编码平台路径，本次未移植或修改；未运行 DFT、notebook 或 AiiDA。

**验证：** 完整 124 项测试、`ruff check src tests scripts`、本次涉及 Python 文件的 Black、`pip check`、字节码编译、CLI 帮助和手册结构检查通过。A100 真实 MACE-MPA-0-medium 冒烟中，fcc Al 经 8 步全晶胞弛豫收敛，2/2 声子力任务成功，参考/位移能量为 `-29.920021/-29.919855 eV`，最低频率 `-5.59×10^-8 THz`，力常数漂移降至 `6.00×10^-16`，频带/DOS PNG 像素与人工查看均正常；临时计算输出已按仓库规则删除。

## 2026-07-30 — 声子谱实现调研与方案

**本次工作目标：** 阅读指定声子谱教程并核对 `solid-solutions-all` 的真实 DFT/Phonopy 案例，为 Stage 9 声子谱实现确定技术路线。

**已完成：**
- 完整核对 9 页 `声子谱教程(1).pdf`：教程给出有限位移和 VASP DFPT 两条路线，共同要求高精度预弛豫、约 10 Å 且尽量各向同性的超胞、静态力计算和 Phonopy 后处理。
- 核对只读参考工程的 Ca3(P0.25Pb0.75)N 案例：Phonopy 4.3 使用 `2×1×1`、120 原子超胞和 198 个 0.01 Å 位移，逐任务收集 VASP OUTCAR 最终力，再用 identity primitive axes、SeeK-path 和 101 点路径生成频带；最低频率约为数值零点量级，结论限定为“未发现显著虚频”。
- 核对当前环境：MACE/ASE/spglib 已安装，Phonopy 和 SeeK-path 尚未安装；官方 Phonopy 4.4 Python API 支持位移生成、力数组注入、力常数、自动频带和均匀网格结果。

**决策 / 计划变更：**
- Stage 9 第一版采用 Phonopy 有限位移 + 现有 MACE 模型的单点力计算，不采用只适用于 VASP 的 DFPT；位移 manifest 与力结果保持后端中立，为后续 VASP/ABACUS 导出和回收保留同一契约。
- 动力学稳定性判据基于配置化均匀 q 网格，而不是只看高对称路径图；虚频容差、超胞、位移幅度、对称容差、模型哈希、力覆盖率和非解析修正状态必须随结果保存。
- 首版将提供可恢复的 `phonon-export`、MACE 力计算和 `phonon-collect`/端到端入口，输出力常数、band/mesh/DOS 数值、PNG/PDF 图和逐结构 summary；不把无虚频解释为有限温混溶或热力学稳定。

**下一步：** 在项目 `.venv` 中增加经验证的 Phonopy 4.x/SeeK-path 依赖，扩展 MACE 单点力后端，实现位移任务、断点续算、力常数/频带/网格/DOS、稳定性分类和回归测试。

**阻塞项 / 上游问题：** 当前仅缺项目环境中的 Phonopy/SeeK-path 依赖，没有算法阻塞。参考工程的 VASP 提交脚本硬编码集群、镜像和二进制路径，正式实现只借鉴产物契约，不移植这些路径；本次未运行 notebook、DFT、AiiDA 或实际声子任务。

## 2026-07-30 — 实现 Stage 8 MLP 混合焓

**本次工作目标：** 基于 Stage 7 的 MACE 驰豫结果实现可审计的 SQS 混合焓计算，并把实际组分贯通到结果契约。

**已完成：**
- 新增 `src/ssscreen/stability/thermodynamics.py` 和 `ss-screen stability mixing-enthalpy`：按 `ΔH_mix(x)=E_SQS(x)-[(1-x)E_A+xE_B]` 输出逐 SQS CSV 与 JSON 汇总，同时保存 eV/atom、meV/atom、端元参考能、组分来源、能量基准哈希、状态、警告和错误。
- 强制 SQS 与两个端元均为 `success` 且 `usable_for_thermodynamics=true`，并要求 MLP 后端名称/版本、模型 SHA-256、精度和完整驰豫/QC 设置一致；计算设备允许不同。缺失、不可用、来源不兼容或歧义记录作为失败行保留，不静默过滤。
- Stage 6 manifest 新增 `actual_fraction_b`，Stage 7 将替换位点和实际组分传入结果；修正 icet 在目标元素已存在于非活性子晶格时的替换计数，实际比例会扣除端元超胞基线。
- 新增 `tests/test_stability_thermodynamics.py`，扩展 SQS、弛豫与 CLI 测试；同步 README、PROJECT_PLAN、长期路线、中文手册 Markdown/Word 和全部相关 ZMD 页面。

**决策 / 计划变更：**
- Stage 8 从计划功能转为当前能力。第一版只报告 MLP 势能形成的 0 K 初步混合信号，不将其解释为有限温自由能、竞争相凸包或实验稳定性。
- 实际 SQS 组分优先于目标组分；旧 Stage 7 记录仅在缺少实际组分和位点计数时允许回退到目标组分，并必须写入警告。

**下一步：** 实现 Stage 9 声子筛选或同一 MLP 能量基准下的竞争相凸包；正式推荐前补充多个 SQS 组分点并用一致设置的 DFT 复核重点体系。

**阻塞项 / 上游问题：** 当前 Stage 8 无代码阻塞；竞争相、声子和有限温自由能仍未实现。当前容器没有 LibreOffice，Word 手册只完成确定性重建和结构检查，未进行本次逐页渲染复检；文档中的 `/home/...` 与实际 `/vepfs-mlp2/...` 工作区路径差异仍存在。

**验证：** 完整 115 项测试通过；`ruff check src tests scripts`、本次涉及 Python 文件的 Black、`pip check`、CLI 帮助、手册结构检查和 302 个 ZMD 本地链接检查通过。测试仅有既有 spglib 弃用警告。

## 2026-07-30 — 稳定性计算路径调研

**本次工作目标：** 核对当前工程、历史参考 notebook 和 `solid-solutions-all` 参考实现中的稳定性计算定义与实现边界。

**已完成：**
- 确认当前正式代码包含三层相关能力：数据集 `e_hull` 初筛、SQS 无序构型生成、MACE 全晶胞/原子位置弛豫及能量/力/应力与 QC；目前没有正式的混合焓、竞争相凸包或声子稳定性命令。
- 核对历史反钙钛矿流程：将 VASP `MPRelaxSet` 弛豫能量组成 `ComputedStructureEntry`，与 MP 同化学体系条目构建 `PhaseDiagram`，通过 `get_e_above_hull` 得到凸包上能量。
- 核对 `solid-solutions-all` 参考实现：先用同一 MLIP 弛豫候选相和竞争相并计算 `e_above_hull`，再在多个 SQS 组分点计算 `ΔH_mix(x)=E_SQS(x)-[(1-x)E_A+xE_B]`。

**决策 / 计划变更：**
- 无计划变更。继续将 Stage 7 定位为产生可比能量与结构的预处理层，不把“弛豫收敛”解释为“热力学稳定”。

**下一步：** 优先实现 Stage 8 混合焓，强制端元与 SQS 的模型哈希、弛豫策略和收敛/QC 状态一致；随后实现同能量基准的竞争相凸包。

**阻塞项 / 上游问题：** 参考 `stability_line_mace.py` 在竞争相 MLIP 弛豫失败时回退到未校正 DFT 能量，会混用能量基准；正式实现不应沿用该回退。当前工作副本仍存在 `/home/...` 文档路径与实际 `/vepfs-mlp2/...` 路径不一致。

## 2026-07-30 — 接入 MACE MLP 结构弛豫与完整 E/F/stress 结果

**本次工作目标：** 为 Stage 6 SQS manifest 接入可恢复的 MACE 结构弛豫，并在当前工作区建立可运行的 Python 3.11/MACE 环境和本地模型资产。

**已完成：**
- 使用工作区内 CPython 3.11.15 重建 `.venv`，安装项目核心/SQS/开发依赖及经参考环境验证的 `torch==2.5.1+cu121`、`mace-torch==0.3.14`、`ase==3.26.0`、`numpy==1.26.4`、`matscipy==1.1.1`；旧失效环境保留为忽略的 `.venv-broken-20260730`。
- 将 `MACE-MPA-0-medium` checkpoint 放入忽略的 `models/mace-mpa-0-medium.model`；`models/README.md` 记录只读来源、79,462,305 字节大小、运行时版本和 SHA-256 `75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638`。
- 新增 `src/ssscreen/stability/mlp.py` 和 `relax.py`：后端协议、模型单次加载、ASE FIRE 全晶胞/仅位置弛豫、端元去重、旧 manifest 数据集 fallback、原子写入、输入/模型/设置指纹续跑及结构哈希校验。
- `src/ssscreen/stability/sqs.py` 现在写出端元结构路径/哈希和 SQS 哈希；新增 `ss-screen stability relax`，结果包含弛豫结构、总能/每原子能、完整力数组、笛卡尔应力 eV/Å³ 与 GPa、实际步数、收敛状态、体积/最小距离质量检查、运行时间和错误摘要。
- 新增 `tests/test_stability_relax.py`，扩展 CLI、SQS 和项目依赖测试；同步 README、PROJECT_PLAN、长期路线、完整中文手册 Markdown/Word 和全部相关 ZMD 页面。

**决策 / 计划变更：**
- 第一版采用 MACE + ASE `FrechetCellFilter`/FIRE，以准确保存每任务实际步数和收敛状态；参考仓库的 TorchSim 批量多 GPU 路线保留为后续性能后端，不改变本次结果契约。
- 模型二进制是本地运行时资产并由 Git 忽略；只跟踪来源和校验和。端元、SQS 和后续热力学计算必须使用同一模型哈希和弛豫设置。
- `success`、`not_converged`、`failed` 严格分离；未收敛或质量检查失败的结果设置 `usable_for_thermodynamics=false`，不能被后续阶段静默采用。

**下一步：** 使用真实 Stage 6 manifest 小批量运行 `stability relax`，评估吞吐和 QC 分布；随后实现 Stage 8 混合焓，或在相同后端协议下增加 TorchSim 分片/批处理执行器。

**阻塞项 / 上游问题：** 只读参考 MACE SQS 流程主要保留能量而丢弃完整力、应力和可靠步数，本次已在正式实现中补齐但未修改上游；参考 checkpoint 的再分发许可证尚未确认，因此模型只保留为本地忽略资产。`AGENTS.md`/部分 ZMD 仍记录旧 `/home/...` 路径，而当前实际工作副本位于 `/vepfs-mlp2/...`，本次按用户提供的当前工作区操作且未覆盖其既有规则修改。

**验证：** Python 3.11.15、`ssscreen 0.1.0` 和 `pip check` 通过；A100 上真实 MACE 单点及 `stability relax` 两步全晶胞 FIRE 冒烟均返回能量、完整力和 `3×3` 应力，未收敛任务正确落为 `not_converged`；完整 106 项测试、全库 Ruff、本次涉及 Python 文件的 Black、手册结构检查、模型哈希和 296 个 ZMD 本地链接检查通过。全库 Black 26 仍报告 `tests/test_reference_curation.py`、`scripts/curate_upstream_references.py` 和 `scripts/build_full_user_manual.py` 三个本次未修改的既有格式差异。

## 2026-07-22 — 交付未来完整功能版中文用户手册

**本次工作目标：** 按已批准设计生成面向材料科研用户的完整功能版中文手册，并同时交付可维护 Markdown 与正式 Word 文档。

**已完成：**
- 新增 `docs/user-guide/SS-Screen_完整功能版_用户使用手册.md`，共 38 章、六部分和 14 阶段工作流；当前 `ss-screen 0.1.0` 命令与未来预期接口采用明确状态标签区分。
- 新增 `scripts/build_full_user_manual.py`，支持标题、列表、代码块、提示框和固定几何表格的确定性 A4 Word 构建及结构检查。
- 生成并隐私清理 `docs/user-guide/SS-Screen_完整功能版_用户使用手册.docx`；文档包含 114 个标题、17 个表格、44 个代码块和 16 个完整版本预期接口提示，共 46 页。
- 新增 `docs/superpowers/plans/2026-07-22-full-user-manual.md`，并同步 ZMD 文档、脚本、资产、目录树与版本导航。

**决策 / 计划变更：**
- Markdown 是手册内容权威来源；Word 是正式用户交付物。后续内容修改必须由 Markdown 重新生成 Word，并重新执行隐私、结构和逐页视觉检查。
- 尚未实现的 DFT/AiiDA 托管、MLP、混合焓、声子、相图、缺陷、综合推荐和工作流编排命令全部标为“完整版本预期接口——当前代码尚未提供”，不能作为当前版本已有能力的证明。
- 本次只编写和验证文档，没有运行昂贵 DFT、MLP、声子、相图或缺陷计算，也没有改变 `src/ssscreen/` 和现有科学算法。

**下一步：** 用户可先按手册第三部分走当前可用的核心筛选流程；未来实现任何预期接口时，同步更新手册状态标签、命令参考和文件契约。

**阻塞项 / 上游问题：** 完整产品中的高精度托管计算、稳定性与缺陷后端仍是未来实现范围；手册已经给出目标交互与契约，但不代表这些命令当前可运行。

**验证：** Word 46 页全部以原始分辨率逐页复检，无乱码、遮挡、越界或编号续接问题；无障碍审计高/中/低风险均为 0，标题层级、A4 分节和 17 个表格几何检查通过；97 项测试通过；`ruff check src tests scripts` 通过；`git diff --check` 通过；285 个 ZMD 本地链接失效数为 0。全库 `ruff check .` 仍会扫描 `references/` 历史归档并报告 867 个既有问题，本次未修改这些保真资料。

## 2026-07-22 — 完整功能版中文用户手册设计

**本次工作目标：** 设计一套面向材料科研用户、覆盖未来完整筛选与验证流程的中文用户使用手册。

**已完成：**
- 新增 `docs/superpowers/specs/2026-07-22-full-user-manual-design.md`，定义 Markdown 与 Word 双格式交付、六部分目录、完整阶段数据流、当前与预期 CLI 边界、科研结果表达原则和验收标准。
- 将现有 14 个公共 CLI 入口与长期路线核对；为 DFT/AiiDA、MLP、混合焓、声子、相图、缺陷和综合推荐设计分组式预期命令。
- 同步 `ZMD/04_项目文档与开发计划/README.md` 和 `ZMD/07_版本与变更索引/README.md`。

**决策 / 计划变更：**
- 手册面向材料科研用户，采用端到端工作流结构，并用同一微型示例贯穿。
- 手册描述未来完整功能，但必须把尚未实现的命令标为“完整版本预期接口——当前代码尚未提供”；不能直接作为当前 `0.1.0` 已实现功能的软著证明。
- 当前接口可以使用实际终端截图；预期接口只能使用明确标注的交互示意图。

**下一步：** 用户审阅并批准设计后，编写实施计划，再生成中文 Markdown 源稿和经过逐页渲染检查的 Word 手册。

**阻塞项 / 上游问题：** 正式手册制作等待用户批准书面设计；当前未实现的完整功能只能按目标接口和文件契约描述。

## 2026-07-22 — 验证 WSL 工作区可运行性

**本次工作目标：** 确认项目环境、CLI、核心与可选依赖、测试和 ZMD 导航能够在当前 WSL 工作区正常运行。

**已完成：**
- 激活项目 `.venv`，确认使用 Python 3.11.15 和 `ss-screen 0.1.0`。
- 成功导入 `ssscreen`、pandas、pymatgen、mp-api、ASE、icet、robocrys 和 matminer；`pip check` 未发现损坏依赖。
- 成功加载完整 CLI，并使用仓库微型夹具运行 `ss-screen pair`，在 `/tmp/ss-screen-workspace-check.csv` 生成预期的 CaS–CaSe 材料对。
- 重新运行完整测试、Ruff 和 ZMD Markdown 链接检查。

**决策 / 计划变更：**
- 本次只进行本地、非破坏性验证；未调用需要凭据的在线 Materials Project 请求，也未运行 notebook、DFT 作业或 AiiDA daemon。

**下一步：** 继续按 ZMD 推荐阅读路径学习或选择下一个实现任务。

**阻塞项 / 上游问题：** 无；测试仅出现 spglib 旧错误处理接口的弃用警告，不影响当前结果。

**验证：** 完整 97 项测试通过；Ruff 通过；实际 `pair` CLI 冒烟测试通过；277 个 ZMD 本地链接失效数为 0；`pip check` 通过。

## 2026-07-22 — 建立 ZMD 工作区导航

**本次工作目标：** 为 WSL 学习副本建立与真实文件系统同步的路径导航知识库。

**已完成：**
- 新建 `ZMD/`，包含总入口、总览规则、入口配置、正式源码、测试、项目文档、历史资料、脚本自动化和版本变更 8 个分区，共 17 个 Markdown 导航文件。
- 为 `src/ssscreen/` 的 data/pair/stability/cli 模块、全部测试文件、项目文档、11 个历史资料家族、脚本和 CI 建立真实相对路径映射。
- 新增 `docs/superpowers/specs/2026-07-22-zmd-navigation-design.md` 和 `docs/superpowers/plans/2026-07-22-zmd-navigation.md`，记录信息架构、同步规则和实施步骤。
- 更新 `AGENTS.md`，要求每次先读 ZMD、修改前从导航定位真实文件、修改后同步对应导航和变更索引。

**决策 / 计划变更：**
- ZMD 只作为导航索引层，不复制正式内容；真实文件系统和 `src/` 实现仍是权威来源。
- 所有导航使用仓库相对链接；现有文件和目录均未移动、重命名或删除。
- 任意真实文件变化都必须在同一工作会话核对 ZMD，并在版本变更索引登记。

**下一步：** 后续工作从 `ZMD/README.md` 定位目标，并持续维护导航与真实文件的一致性。

**阻塞项 / 上游问题：** 无。

**验证：** 17 个 ZMD Markdown 文件、277 个本地链接且失效链接为 0；34 个正式源码/测试 Python 文件均已索引；完整 97 项测试通过；Ruff 检查通过。

## 2026-07-22 — 强制使用 WSL 项目环境

**本次工作目标：** 要求在 WSL 学习副本中工作时必须激活项目环境。

**已完成：**
- 将 `AGENTS.md` 完整翻译为中文，并写入当前 WSL 工作区路径、强制 `.venv` 激活、环境验证及非交互式命令规则。

**决策 / 计划变更：**
- 项目的所有 Python 命令必须使用本地 Python 3.11 环境；禁止使用 WSL 系统 Python，也禁止全局安装项目依赖。

**下一步：** 在已激活的项目环境中继续项目导览与学习。

**阻塞项 / 上游问题：** 无。

## 2026-07-21 — Curated upstream reference archive

**Goal of this session:** Implement the approved full-history curation of upstream notebooks, source code, executed results, and research knowledge.

**Done:**
- Added `scripts/curate_upstream_references.py`, a deterministic standard-library curation/validation tool with dry-run, write, and validate-only modes.
- Added `tests/test_reference_curation.py` with eight RED/GREEN tests covering discovery, checkpoint layout, output-preserving credential redaction, byte aliases, manifest/index generation, tamper/stale-file detection, policy/provenance fields, complete exclusions, and dry-run behavior.
- Generated `references/` with family knowledge indexes and `manifest.json`: 78 stored artifacts, 2 redacted notebooks, 35 byte-identical aliases, and 101 explicit file/directory exclusions; 55,618,466 curated artifact bytes.
- Preserved executed scientific outputs, including the large historical band/prototype plots, and retained source-distinct checkpoints under visible `revisions/` paths.
- Linked the archive and manifest from `README.md`.
- Completed a pre-commit credential scan of the curated archive: no remaining API-key formats, private keys, JWTs, URL credentials, or literal positional `MPRester` credentials were found.

**Decisions / changes to plan:**
- Credential-bearing positional `MPRester` arguments in two stored antiperovskite notebooks were replaced by standard configuration discovery (`MPRester()`); their outputs/execution state were preserved and original/curated hashes recorded.
- Byte-identical content is stored once and represented by manifest aliases. Files with distinct bytes/metadata remain separate historical artifacts.
- The archive records user-authorized/otherwise-unspecified license status because no upstream license files were found.
- Historical researcher email, local/cluster paths, and AiiDA `code@host` metadata were retained with explicit user approval as provenance-bearing notebook output.

**Next up:** Resume the CLI tutorial or use the curated source index to plan/port the remaining WBM, DFT, prototype/stability, and defect routines.

**Blockers / upstream issues:** The credential remains in read-only upstream files and should be rotated/scrubbed separately. No upstream path was modified.

**Verification:** 8 focused curation tests passed; full suite passed (97 tests); Ruff and `py_compile` passed; archive validation and `git diff --check` passed; repeated curation produced identical manifest/README SHA-256 values.

## 2026-07-21 — Upstream reference curation design

**Goal of this session:** Design a complete, safe archive of upstream notebooks, source code, executed results, and research knowledge inside `ss-screen`.

**Done:**
- Inventoried and classified primary notebooks, source scripts, checkpoint histories, embedded result payloads, duplicates, generated/data exclusions, provenance, and credential risks across every declared upstream family.
- Confirmed a duplicate-aware full-history archive is approximately 56 MB and preserves 67 distinct notebook cell histories from 98 primary/checkpoint paths.
- Wrote and self-reviewed `docs/superpowers/specs/2026-07-20-upstream-reference-curation-design.md` after user approval of the recommended design and redistribution-authority condition.

**Decisions / changes to plan:**
- Preserve scientific notebook outputs inline; retain source-distinct checkpoints as visible historical revisions; represent byte-identical files as manifest aliases.
- Redact the two credential-bearing antiperovskite notebook cells while recording original/curated hashes. Keep datasets, calculation directories, archives, `.aiida`, generated scheduler artifacts, and external result sidecars out of scope.

**Next up:** Obtain user review of the written spec, then create and execute the implementation plan.

**Blockers / upstream issues:** The external credential remains in read-only upstream files and should be rotated/scrubbed separately; no upstream file was modified.

## 2026-07-20 — Permit curated historical source copies

**Goal of this session:** Update repository policy so historical notebooks and source code can be curated inside `ss-screen`.

**Done:**
- Updated `AGENTS.md` to allow attributed notebook/source snapshots under `references/` while keeping all external originals read-only.
- Aligned `docs/PROJECT_PLAN.md` with the new historical-source curation policy.

**Decisions / changes to plan:**
- Copying is limited to notebooks and source code after provenance, secret, and license checks. Full datasets, archives, `.aiida` dumps, generated calculation outputs, and other large data remain external.
- Curated snapshots are historical references; tested implementations under `src/` remain canonical.

**Next up:** Define the `references/` layout and curate the relevant historical notebooks/source files.

**Blockers / upstream issues:** A live-looking credential previously identified in an upstream notebook must not be copied; it requires scrubbing and rotation at the source.

## 2026-07-19 — Upstream migration completeness audit

**Goal of this session:** Determine whether `ss-screen` includes all reusable information, routines, functionality, and workflows from the declared read-only upstream workspace.

**Done:**
- Added `docs/review_upstream_completeness_2026-07-19.md` with a source-family coverage matrix, prioritized gaps, verification evidence, and completion criteria.
- Confirmed the core MP/condense/group/gap/pair path is strongly migrated, while raw WBM construction is partial and AiiDA band workflows, phase stability, prototype/MACE flows, and defect ranking remain mostly absent.
- Fresh full verification passed (`89` tests; ruff clean); Black reported 33 files unchanged but hung after three variants, so its exit status is recorded as inconclusive.
- Reproduced the canonical binary result exactly (`52/52` rows).
- Found that the real ternary group JSON fails to load because it uses legacy `Compositions`; a temporary one-key normalization made the unchanged scientific logic reproduce the canonical `299/299` rows exactly.

**Decisions / changes to plan:**
- Classify the repository as a tested core screening package with external calculation contracts and an early SQS stage, not as a complete migration of the full upstream research workflow.
- Treat large datasets, tarballs, and `.aiida` archives as intentionally external; require their reusable schemas/provenance transformations rather than copying data.

**Next up:** Fix the legacy ternary field alias, implement optional PBE fallback and raw WBM reconciliation, then decide whether DFT/defect execution will be ported or formally replaced by documented external adapters.

**Blockers / upstream issues:** A read-only upstream notebook still contains a live-looking MP credential and should be rotated/scrubbed outside this package audit. No upstream file, notebook, archive, DFT job, AiiDA daemon, GPU task, or MPI task was modified or run.

## 2026-07-19 — mp-offline thermo cache commit

**Goal of this session:** Commit the completed `mp-offline` summary/thermo cache migration and theory-separation work.

**Done:**
- Committed `mp-offline/mp-offline-develop` on `codex/mp-offline-schema-migration` as `418b9e3` (`feat: add schema migration and theory-safe MP thermo cache`).
- Commit includes schema migration, resumable summary downloads, thermo-scheme selection/provenance, exact scalar run-type filtering, local thermo queries, CLI support, tests, and design/implementation docs.
- Verified the committed checkout with `.venv/bin/python -m pytest -q` before staging; the suite passed.

**Decisions / changes to plan:**
- Kept the parent-project log outside this package commit; it records the handoff without mixing unrelated root-project changes into the package history.

**Next up:**
- Optional live authenticated Materials Project smoke test, push, or pull-request preparation.

**Blockers / upstream issues:** Historical archive/default databases were not modified.

## 2026-07-19 — CLI tutorial design

**Goal of this session:** Define an interface-first CLI tutorial for researchers and future GUI developers.

**Done:**
- Agreed on a two-part guide: a complete staged screening workflow plus per-command file contracts.
- Wrote and self-reviewed `docs/superpowers/specs/2026-07-19-cli-tutorial-design.md` covering scope, artifact boundaries, command inventory, GUI contract, and verification.

**Decisions / changes to plan:**
- The tutorial will document only files and command contracts; GUI code, notebooks, bundled research data, and CLI behavior changes are out of scope.

**Next up:** Obtain user review of the design, then write `docs/CLI_TUTORIAL.md` and link it from `README.md`.

**Blockers / upstream issues:** No read-only source files were modified.

## 2026-07-16 — Binary CLI reproduction rerun

**Goal of this session:** Exercise the implemented CLI against the historical binary-screening inputs and verify its output against the notebook artifact.

**Done:**
- Ran `.venv/bin/ss-screen pair --groups ../pair-screening/binary-group-df.json --gaps ../pair-screening/mbj_gaps_binary_2025_0425_pmg_info.csv` and wrote the transient result to `/tmp/ss-screen-binary-reproduction-20260716.csv`.
- Fresh exact dataframe comparison against `../pair-screening/mbj_result_binary_20250426.csv` verified all 52 rows, columns, values, directness flags, and row order match.

**Decisions / changes to plan:**
- Used the existing editable virtual-environment CLI after `uv run` could not access the shared uv cache in the sandbox; no package code or reference data was changed.

**Next up:** Continue with the next explicitly requested package milestone.

**Blockers / upstream issues:** No read-only source files were modified.

## 2026-07-16 — MACE model JSON element-scope audit

**Goal of this session:** Determine whether MACE JSON conversion needs an explicit element list and whether it can retain all elements from its source `.model`.

**Done:**
- Inspected the read-only MACE conversion/training sources and existing AlN MACE logs; no `ss-screen` code or data artifacts were changed.
- Confirmed that JSON metadata derives its `atomic_numbers` from the loaded model, while the `foundation_model_elements` training option controls whether a fine-tuned model preserves the foundation model's full element set.

**Decisions / changes to plan:**
- None; this was a read-only compatibility assessment outside the current package implementation.

**Next up:** Use the original model's embedded `atomic_numbers` when exporting model metadata; retrain only if the source model was already pruned and broader elemental coverage is required.

**Blockers / upstream issues:** Direct CPU inspection of the selected AlN `.model` was blocked because its serialized e3nn module requires CUDA during deserialization; training logs provide the recorded element sets.

## 2026-07-16 — Review remediation for staged CLI

**Goal of this session:** Address multi-agent review findings against the staged CLI implementation.

**Done:**
- Fixed `condense_paths()` in `src/ssscreen/data/condense.py` so unreadable input files are recorded as failed manifest/index rows instead of being silently dropped.
- Fixed `gap-export` in `src/ssscreen/pair/gap_export.py` so atom-count gating and exported structure JSON use the same primitive/calculation structure.
- Updated gap-result validation and feedback in `src/ssscreen/pair/gap_export.py` and `src/ssscreen/pair/gap_feedback.py` to accept CSV/JSON records, tolerate blank failed rows, and report gap shifts/directness changes in method comparisons.
- Added `src/ssscreen/data/wbm.py` and `ss-screen dataset wbm` for WBM extxyz normalization.
- Hardened `src/ssscreen/stability/sqs.py` and CLI validation so SQS target fractions must be in `[0, 1]`.
- Updated `README.md`, `docs/PROJECT_PLAN.md`, and the CLI roadmap to reflect the current extras, WBM loader, JSON gap files, and review remediations.

**Decisions / changes to plan:**
- Core dependencies remain small; WBM loading, condensation, MP live API, and SQS each live behind targeted extras.
- Historical `mp-offline` notes remain below, but this ss-screen entry is the current project handoff point.

**Next up:** Run full verification, then continue with Stage 7 MLP relaxation adapters or Stage 12 Chinese user guide work.

**Blockers / upstream issues:** No read-only reference files were modified.

## 2026-07-14 — mp-offline thermo review Task 2 corrections

**Goal of this session:** Correct thermo resume compatibility, row-count metadata, and fallback identity behavior in the shared `mp-offline` development checkout.

**Done:**
- Updated `mp-offline/mp-offline-develop/src/mp_offline/dump.py` to reject resumes when the saved JSON-canonical normalized summary query differs, seed compatible thermo resumes from the existing `thermo_entry` count, and use stable material-plus-canonical-scheme fallback thermo identities.
- Retained and documented the public one-shot `ThermoRester.search()` download behavior; no private pagination or streaming redesign was added.
- Added regression coverage in `mp-offline/mp-offline-develop/tests/test_dump_resume.py` and `tests/test_thermo_entries.py`.
- Recorded TDD and verification evidence in `/tmp/mp-offline-20260714-task2.md`; focused and full test suites completed with exit code zero.

**Decisions / changes to plan:**
- Same-material, same-canonical-scheme rows with no API thermo ID deduplicate even when mutable payload fields change; distinct schemes remain separate identities.

**Next up:** Continue only with explicitly requested thermo-cache plan tasks.

**Blockers / upstream issues:** No live Materials Project request, staging, or commit was performed.

## 2026-07-14 — mp-offline thermo review Task 1 corrections

**Goal of this session:** Implement Task 1 from the thermo review corrections plan in the shared `mp-offline` development checkout.

**Done:**
- Updated `mp-offline/mp-offline-develop/src/mp_offline/dump.py` so `--run-type` semantics use only scalar `energy_type`, persisted thermo schemes are canonicalized, and every downloaded row is checked against the selected cache scheme before it can be written.
- Updated `mp-offline/mp-offline-develop/src/mp_offline/client.py` and `src/mp_offline/cli.py` to reject scheme requests that conflict with the cache profile and reject orphaned `--run-type` options.
- Added focused regression coverage in `mp-offline/mp-offline-develop/tests/test_thermo_entries.py`, `tests/test_client.py`, and `tests/test_cli.py`.
- Recorded TDD and verification evidence in `/tmp/mp-offline-20260714-task1.md`; focused tests passed (`35 passed`).

**Decisions / changes to plan:**
- A returned thermo row outside the selected scheme raises before any batch persistence rather than being silently ignored.

**Next up:** Continue only with explicitly requested thermo-cache plan tasks.

**Blockers / upstream issues:** `uv run` cannot resolve the declared Python support range with `mp-api==0.46.4`, and `ruff` is absent from the existing virtualenv. No live Materials Project request, staging, or commit was performed.

## 2026-07-13 — mp-offline thermo implementation review

**Goal of this session:** Run independent reviews of thermo download compatibility, theory separation, and the local query/CLI surface.

**Done:**
- Launched three read-only reviewers against `mp-offline/mp-offline-develop`.
- Identified P1 gaps in returned-scheme validation, authoritative run-type semantics, summary resume compatibility, and thermo resume/identity behavior.
- Identified P2 usability/provenance gaps around wrong-scheme local queries and native `r2SCAN` normalization.

**Decisions / changes to plan:**
- No implementation changes were made during this review pass; the findings require a focused correction plan before further claims of theory-safe caching.

**Next up:**
- Decide the authoritative meaning of `--run-type`, then implement the P1 correction set with tests.

**Blockers / upstream issues:** No live Materials Project request or archive/database modification.

## 2026-07-13 — mp-offline Task 4 theory-aware local thermo queries

**Goal of this session:** Expose an explicit-scheme local thermo query and CLI command in the shared `mp-offline` development checkout.

**Done:**
- Added `MPOffline.query_thermo()` in `mp-offline/mp-offline-develop/src/mp_offline/client.py`, constrained to `MaterialThermoEntry` and using Task 1/3 canonical scheme and exact run-type matching helpers.
- Added `mp-offline list-thermo --thermo-type ...` with repeated material/run filters and a validated `thermo_entry` projection in `mp-offline/mp-offline-develop/src/mp_offline/cli.py`.
- Added focused regression tests in `mp-offline/mp-offline-develop/tests/test_client.py` and `mp-offline/mp-offline-develop/tests/test_cli.py`.
- Recorded TDD evidence in `/tmp/mp-offline-task-4-report.md`: RED `5 failed, 10 passed`; GREEN focused `15 passed`; full suite `61 passed`.

**Decisions / changes to plan:**
- Kept the implementation table-specific; no generic table abstraction was introduced.

**Next up:** Continue only with explicitly requested thermo-cache tasks.

**Blockers / upstream issues:** No live Materials Project request or cache/archive modification. No files were staged or committed.

## 2026-07-13 — mp-offline Task 3 thermo identity and exact filtering

**Goal of this session:** Preserve distinct current Materials Project thermo documents and make thermo run-type selection/resume metadata exact and canonical in the shared development checkout.

**Done:**
- Updated `mp-offline/mp-offline-develop/src/mp_offline/dump.py` to derive `payload-sha256:` fallback thermo IDs from canonical raw JSON, map before deduplication, use exact normalized run-type labels, and sort/deduplicate run types in `thermo_profile`.
- Added Task 3 regression coverage in `mp-offline/mp-offline-develop/tests/test_thermo_entries.py` for pure versus mixed GGA labels, exact mixed scheme selection, distinct no-ID payload persistence, and reordered/duplicated profile selections.
- Recorded TDD evidence in `/tmp/mp-offline-task-3-report.md`: RED `3 failed, 8 passed`; GREEN `11 passed`; full suite `56 passed`.

**Decisions / changes to plan:**
- Existing `thermo_entry.thermo_id` schema accepts the deterministic textual hash key, so Task 3 required no schema or migration change.

**Next up:** Continue only with explicitly requested thermo-cache tasks.

**Blockers / upstream issues:** `ruff` is unavailable in the existing test virtual environment; no dependencies were installed. No files were staged or committed.

## 2026-07-13 — mp-offline Task 2 thermo resume safety

**Goal of this session:** Repair Task 2 thermo downloading/profile-safe resume behavior in the shared `mp-offline` development checkout.

**Done:**
- Updated `mp-offline/mp-offline-develop/src/mp_offline/dump.py` to use only public thermo chunking arguments, enforce public thermo selection invariants, persist profiles/failures, and reject mismatched resumes before summary writes.
- Updated `mp-offline/mp-offline-develop/src/mp_offline/migration.py` metadata defaults and added focused regression coverage in `mp-offline/mp-offline-develop/tests/`.
- Recorded RED/GREEN evidence in `/tmp/mp-offline-task-2-report.md`; focused result: `12 passed`.

**Decisions / changes to plan:**
- A supplied `thermo_types` value enables thermo inclusion at the public `create_offline_db` boundary; `GGA_GGA+U_R2SCAN` remains one valid scheme.

**Next up:** Continue only with explicitly requested thermo theory-separation tasks.

**Blockers / upstream issues:** `uv run` cannot resolve the declared Python support range with `mp-api==0.46.4`; focused tests used the existing checkout virtual environment. No files were staged or committed.

## 2026-07-13 — mp-offline Task 1 thermo profile validation

**Goal of this session:** Implement the first thermo theory-separation task in the shared `mp-offline` development checkout.

**Done:**
- Added enum-backed `normalize_thermo_types` and `thermo_profile` in `mp-offline/mp-offline-develop/src/mp_offline/dump.py`.
- Updated `mp-offline/mp-offline-develop/src/mp_offline/cli.py` so `--thermo-type` implies thermo download and `--include-thermo` requires a scheme.
- Added focused validator and CLI tests in `mp-offline/mp-offline-develop/tests/`.
- Recorded RED/GREEN evidence in `/tmp/mp-offline-task-1-report.md`.

**Decisions / changes to plan:**
- Normalize against installed `ThermoType` values and exclude `UNKNOWN`; defer pagination, resume comparison, and exact run-type filtering to later tasks.

**Next up:** Implement Task 2 downloader contract and profile-safe resume behavior.

**Blockers / upstream issues:** No live Materials Project request or archive/database modification. No files were staged or committed.

---

## 2026-07-13 — Stage 6 stability SQS input artifacts

**Goal of this session:** Start the optional stability workflow by generating reusable alloy/SQS input artifacts from final pair results.

**Done:**
- Added `src/ssscreen/stability/sqs.py` with deterministic random-substitution alloy structure generation and JSONL manifest writing.
- Installed `icet==3.2` into `.venv` and added an `icet` SQS backend using `generate_sqs_from_supercells`.
- Added `ss-screen stability sqs-generate` in `src/ssscreen/cli/app.py`.
- Added tests in `tests/test_stability_sqs.py` and CLI coverage in `tests/test_cli.py`.
- Updated `README.md` and `plans/2026-07-12-cli-long-term-screening-roadmap-v1.md` with the Stage 6 command and artifact boundary.

**Decisions / changes to plan:**
- `stability sqs-generate` now supports `--backend random` for dependency-light fixtures and `--backend icet` for optimized SQS generation.
- The JSONL manifest is the reusable task queue for future MLP relaxation and stability-analysis backends.

**Next up:** Implement Stage 7 MLP relaxation manifest/result adapters, keeping actual GPU-heavy relaxation outside default CI.

**Blockers / upstream issues:** No read-only reference files were modified.

## 2026-07-13 — thermo theory-separation review

**Goal of this session:** Audit whether the `mp-offline` thermo cache can safely select, record, and expose one Materials Project thermodynamic theory scheme.

**Done:**
- Ran three independent read-only reviews of downloader/CLI behavior, schema/provenance, and local consumer APIs.
- Found that the current installed `mp-api==0.46.4` thermo search does not accept the downloader's private `_page` argument, so the implemented thermo download path is not compatible with that API contract.
- Found that resume can append entries from a different scheme while replacing global metadata, run-type matching is fuzzy, and public client/CLI query paths expose only summary records.

**Decisions / changes to plan:**
- Proposed a strict single-thermo-scheme cache policy: one explicitly selected `thermo_type` per database, where MP's `GGA_GGA+U_R2SCAN` is a valid scheme in its own right.
- Require exact normalized matching, immutable per-download provenance, and public `query_thermo` access before considering thermo data theory-safe.

**Next up:**
- Obtain user approval for the strict scheme-separation policy, then implement with TDD.

**Blockers / upstream issues:** No live Materials Project request was run. No archive/database files were modified.

## 2026-07-13 — Stage 5 external gap feedback and comparison

**Goal of this session:** Continue the staged CLI by feeding externally calculated band gaps back into final pair generation and comparing multiple theory levels.

**Done:**
- Added `src/ssscreen/pair/gap_feedback.py` for validated external gap-result ingestion, method selection, coverage reporting, and final pair CSV generation.
- Extended `ss-screen pair` in `src/ssscreen/cli/app.py` with `--gap-results`, `--method`, and `--summary` while preserving the legacy `--gaps` path.
- Added `ss-screen gap-compare` for method-specific pair CSVs and JSON comparison reports across external gap methods.
- Added Stage 5 tests in `tests/test_gap_feedback.py` and `tests/test_cli.py`.
- Updated `README.md` and `plans/2026-07-12-cli-long-term-screening-roadmap-v1.md` with the new Stage 5 command flow.

**Decisions / changes to plan:**
- External gap results are used as a transient high-level gap map during pair enumeration; the original PBE/database `StructureGroup.band_gaps` are not overwritten.
- Multiple methods in gap-result files require explicit method selection for single-method final pair generation; `gap-compare` owns cross-method comparison.

**Next up:** Start the optional Stage 6 SQS/stability artifact generator.

**Blockers / upstream issues:** No read-only reference files were modified.

## 2026-07-13 — mp-api offline cache surface audit

**Goal of this session:** Identify Materials Project API routes beyond summaries and thermo entries that can be represented in an offline cache.

**Done:**
- Inspected the installed `mp-api==0.46.4` route registry and document primary keys without making a live API request.
- Classified material, task, relationship, molecule, and large-artifact routes for future offline-cache support.
- Identified a generic versioned document cache plus a content-addressed artifact store as the forward-compatible extension path; retain dedicated tables only for high-value query models such as summaries and thermo entries.

**Decisions / changes to plan:**
- Keep `thermo_entry` separate because it models stable one-to-many material thermodynamic entries.
- Do not treat `MPRester.local_dataset_cache` as an application offline database; it is client-side caching for the package's dataset/delta-table mechanisms.

**Next up:**
- Select the first property caches needed by downstream screening, likely robocrys, electronic-structure metadata, and elasticity/dielectric/magnetism.

**Blockers / upstream issues:** Browser access to the official documentation was unavailable in this environment; the audit is based on the locally installed `mp-api==0.46.4` source. No live authenticated query was run, and archive/database files were not modified.

## 2026-07-13 — mp-offline thermo entries cache

**Goal of this session:** Expand `mp-offline` to cache Materials Project thermo entries separately from summary documents and support thermo/run-type selection.

**Done:**
- Added `mp-offline/mp-offline-develop/src/mp_offline/model.py` support for a `thermo_entry` table storing thermo docs, entries, energy type, entry types, and raw JSON payloads.
- Extended `mp-offline/mp-offline-develop/src/mp_offline/dump.py` with thermo search normalization, chunked thermo downloads, thermo row writes, local run-type filtering, and thermo metadata.
- Extended `mp-offline/mp-offline-develop/src/mp_offline/cli.py` with `--include-thermo`, repeated `--thermo-type`, and repeated `--run-type`.
- Added tests in `mp-offline/mp-offline-develop/tests/test_thermo_entries.py` and extended API contract/download/CLI tests.
- Updated `mp-offline/mp-offline-develop/README.md` with summary-vs-thermo behavior and examples.
- Verified with `MPLCONFIGDIR=/tmp/mpl-cache /tmp/mp-offline-thermo-venv/bin/python -m pytest -q` (`40 passed`).

**Decisions / changes to plan:**
- Do not pass `thermo_types` into `summary.search`; current `mp-api==0.46.4` exposes `thermo_types` on `ThermoRester.search`, not `SummaryRester.search`.
- Store thermo documents as separate cache records because one material summary can be associated with multiple phase-diagram entries/schemes.
- Treat `run_type` as a local filter over `energy_type`, `entry_types`, and `entries` keys.

**Next up:**
- Consider adding client/CLI query helpers for the `thermo_entry` table if downstream screening needs direct thermo-cache queries.

**Blockers / upstream issues:** No live Materials Project API query was run. Existing archive/database files were not modified.

## 2026-07-13 — Stage 3 structure matching command

**Goal of this session:** Add the explicit Stage 3 structure-matching command that consumes Stage 1 composition candidates and Stage 2 condensed JSON archives.

**Done:**
- Added `src/ssscreen/pair/structure_match.py` with `match_structure_candidates()`.
- Added `ss-screen structure-match --candidates ... --condensed-dir ... --output ... [--summary ...]`.
- Added tests in `tests/test_structure_match.py` covering environment grouping, X-element diversity, band-gap attachment, and missing condensed descriptions.
- Added CLI regression coverage in `tests/test_cli.py`.
- Updated `README.md` and `plans/2026-07-12-cli-long-term-screening-roadmap-v1.md`.

**Decisions / changes to plan:**
- `ss-screen structure-match` is the new staged path for Stage 3.
- The older `ss-screen group` command remains available as a legacy all-in-one path for now.
- Stage 3 summaries report candidate/template counts, missing descriptions, raw groups, final groups, grouped members, and the X-element diversity threshold.

**Next up:**
- Implement Stage 3a: export the union of matched group member structures/metadata for external high-level band-gap calculations.

**Blockers / upstream issues:** No read-only reference files were modified.

## 2026-07-12 — mp-offline MP API compatibility updates implemented

**Goal of this session:** Implement the `mp-offline` downloader/provenance updates needed for current `mp-api` compatibility.

**Done:**
- Updated `mp-offline/mp-offline-develop/src/mp_offline/dump.py` with normalized Materials Project summary kwargs, required field merging, chunked page iteration, incremental SQLite writes, idempotent material-id skipping, resume support, and richer download metadata.
- Updated `mp-offline/mp-offline-develop/src/mp_offline/migration.py` with expanded provenance metadata defaults for old and new caches.
- Updated `mp-offline/mp-offline-develop/src/mp_offline/cli.py` with `dump` options for fields, filters, GNoMe inclusion, chunking, resume, endpoint, database version, and `MP_API_KEY`.
- Added tests for download option normalization, resumable dumps, CLI dump options, and the installed `mp-api` contract.
- Updated `mp-offline/mp-offline-develop/README.md`, `pyproject.toml`, and the compatibility plan checklist.
- Verified with `MPLCONFIGDIR=/tmp/mpl-cache /tmp/mp-offline-develop-venv/bin/python -m pytest -q` (`33 passed`).

**Decisions / changes to plan:**
- Did not promote additional fields such as `density`, `volume`, `efermi`, or `has_props` because current workflow searches found no offline query requirement; they remain available in `json_data`.
- Set `mp_api>=0.46.4` and added contract tests instead of adding an upper bound.

**Next up:**
- Optional final code review/commit if the user wants this branch prepared for integration.

**Blockers / upstream issues:** No live Materials Project API query was run. The old archive and both `data/default.db` files were not modified; timestamps remained `2024-06-04 21:05:39.178801411 +0800`.

## 2026-07-12 — mp-offline MP API compatibility update plan

**Goal of this session:** Generate an implementation plan for `mp-offline` updates needed after the latest `mp-api` / Materials Project API audit.

**Done:**
- Added `mp-offline/mp-offline-develop/docs/superpowers/plans/2026-07-12-mp-offline-mp-api-compatibility-updates.md`.
- Covered downloader option normalization, chunked/resumable writes, provenance metadata, CLI controls, dependency contract tests, candidate promoted columns, and documentation/verification.
- Ran a placeholder scan on the new plan.

**Decisions / changes to plan:**
- Prioritize downloader/provenance compatibility before promoting additional schema columns.
- Keep implementation tests mocked/offline unless the user explicitly authorizes live Materials Project queries.

**Next up:**
- Execute the compatibility update plan, preferably with subagent-driven development.

**Blockers / upstream issues:** The `create-plan` validation script referenced by the planning skill is not present in this repository, so validation was manual.

## 2026-07-12 — mp-api 0.46.4 compatibility follow-up

**Goal of this session:** Inspect latest `mp-api` / Materials Project API behavior and identify updates needed for `mp-offline`.

**Done:**
- Verified the dedicated development environment is using `mp-api==0.46.4`, `emmet-core==0.87.1`, and `pymatgen==2026.5.4`.
- Reviewed current `MPRester` and `SummaryRester.search` signatures, including `db_version`, `local_dataset_cache`, `include_gnome`, `fields`, `all_fields`, `chunk_size`, and `num_chunks`.
- Ran read-only sub-agent audits of `mp-offline/mp-offline-develop` and the installed `mp-api` package surface.
- Identified follow-up updates needed around downloader chunking/resume behavior, credential documentation, required field handling, richer provenance metadata, and dependency compatibility bounds.

**Decisions / changes to plan:**
- Treat the existing schema migration work as compatible with current `mp-api`, but prioritize downloader/provenance improvements before adding more promoted columns.
- Keep old archive and database files untouched.

**Next up:**
- Implement a resumable/downloader-focused compatibility pass for `mp-offline/mp-offline-develop`.

**Blockers / upstream issues:** No live authenticated Materials Project query was run.

## 2026-07-12 — mp-offline migration system implemented

**Goal of this session:** Execute the `mp-offline` schema migration plan using subagent-driven development.

**Done:**
- Created branch `codex/mp-offline-schema-migration` in `mp-offline/mp-offline-develop`.
- Added `mp-offline/mp-offline-develop/src/mp_offline/migration.py` with `inspect_db()`, `migrate_db()`, schema versioning, metadata finalization, and v0-to-v1 `band_gap` backfill.
- Promoted `MaterialSummary.band_gap` and added `CacheMetadata` in `mp-offline/mp-offline-develop/src/mp_offline/model.py`.
- Updated `mp-offline/mp-offline-develop/src/mp_offline/dump.py` so promoted fields remain in raw `json_data` and fresh dumps are finalized through migration metadata.
- Updated `mp-offline/mp-offline-develop/src/mp_offline/client.py` with database inspection and a simple query wrapper.
- Updated `mp-offline/mp-offline-develop/src/mp_offline/cli.py` with `inspect`, `migrate`, safe repeated `--where` filters, and no `eval`.
- Added pytest coverage under `mp-offline/mp-offline-develop/tests/` for model mapping, migration idempotency, missing-path safety, client queries, CLI filters, and dump metadata.
- Updated `mp-offline/mp-offline-develop/README.md`, `pyproject.toml`, and the local design/plan docs under `mp-offline/mp-offline-develop/docs/superpowers/`.

**Decisions / changes to plan:**
- Kept `json_data` as the raw forward-compatible payload; explicit columns are indexed projections.
- Fixed final-review gaps by adding the full metadata contract and preventing `inspect_db()` / `migrate_db()` from creating empty SQLite files for missing paths.
- Did not commit changes, following the project rule that commits happen only when explicitly requested.

**Next up:**
- Optionally implement resumable Materials Project downloads using the new metadata table.
- Decide whether to stage/commit the `mp-offline` development branch changes.

**Blockers / upstream issues:** No live Materials Project API query was run. The old archive and both `data/default.db` files were not modified; final verification kept their timestamp at `2024-06-04 21:05:39.178801411 +0800`.

## 2026-07-12 — Stage 2 condensed JSON archive generation

**Goal of this session:** Implement Stage 2 archive generation and metadata management while preserving the per-material JSON storage layout used by `../mp-condense`.

**Done:**
- Added `docs/superpowers/plans/2026-07-12-stage-2-condense-archive.md`.
- Extended `src/ssscreen/data/condense.py` with DataFrame-driven condensation, atomic per-material JSON writes, JSONL manifest output, CSV index output, archive indexing, and archive validation.
- Extended `ss-screen condense` with `--df`, `--structure-column`, `--material-id-column`, `--limit`, `--manifest`, `--index`, and `--stop-on-error`.
- Added `ss-screen condense-index --condensed-dir ... --output ...`.
- Added `ss-screen condense-validate --condensed-dir ... --output ...`.
- Added `tests/test_condense_archive.py` and CLI regression tests for the new command surface.
- Installed the condense runtime into `.venv` and ran a real one-structure NaCl condensation smoke test at `/tmp/ss-screen-real-condense`, producing `condensed/smoke-nacl.json`, `manifest.jsonl`, `index.csv`, and a valid validation report.
- Updated the `condense` optional dependency constraints in `pyproject.toml` so modern installs use `matminer>=0.10.1` and `setuptools<81`, avoiding the robocrys/matminer runtime import failures seen with the default resolver choices.
- Updated `README.md` and `plans/2026-07-12-cli-long-term-screening-roadmap-v1.md`.

**Decisions / changes to plan:**
- Keep `condensed/{material_id}.json` as the primary artifact because concurrent workers can independently read, skip, and write files.
- Use JSONL manifest and CSV index sidecars for searchability/auditability instead of replacing the archive with one monolithic file.
- Marked Stage 2 and Stage 2a complete for the first reusable archive-management slice; optional merge/summarize/Parquet index can come later.

**Next up:**
- Refactor `ss-screen group` into the explicit Stage 3 structure-matching command, preferably consuming the Stage 1 composition-candidate CSV and Stage 2 condensed archive.
- Add attrition/missing-description reporting for Stage 3.

**Blockers / upstream issues:** The reference archive `../mp-condense/condensed` was read only for shape/scale checks (`145164` JSON files, about `1.4G`) and was not modified. The conda `work` environment still has an incompatible sklearn/numpy ABI for robocrys; use the project `.venv` for condense runtime checks.

## 2026-07-12 — mp-offline migration design and plan

**Goal of this session:** Review `mp-offline` development checkout and prepare a migration-system implementation plan.

**Done:**
- Used `/home/bonan/work/HC/ss-screen/mp-offline/mp-offline-develop` as the development base.
- Ran three parallel read-only sub-agent reviews covering usability, Materials Project downloading, and database API/schema migration.
- Added `mp-offline/mp-offline-develop/docs/superpowers/specs/2026-07-12-mp-offline-schema-migration-design.md`.
- Added `mp-offline/mp-offline-develop/docs/superpowers/plans/2026-07-12-mp-offline-schema-migration.md`.

**Decisions / changes to plan:**
- Treat explicit schema columns as indexed projections while preserving `json_data` as the raw forward-compatible payload.
- Implement migration and `band_gap` promotion before attempting resumable downloader changes.

**Next up:**
- Execute the migration implementation plan, preferably using subagent-driven task execution with TDD.

**Blockers / upstream issues:** No live Materials Project API query was run. The old archive and old database were not modified.

## 2026-07-12 — mp-offline compatibility audit

**Goal of this session:** Explore `mp-offline` and check compatibility with the latest installed Materials Project API without modifying the old archive.

**Done:**
- Located the private package at `mp-offline/mp-offline/` and inspected its metadata, README, SQLAlchemy model, dump path, client path, and CLI.
- Created a dedicated throwaway environment at `/tmp/mp-offline-latest-api-venv` and installed editable `mp_offline` against `mp-api==0.46.4`.
- Verified the bundled archive `mp-offline/mp-offline/data/default.db` is readable and contains 155,361 rows.
- Confirmed current `mp_api.client.routes.materials.summary.SummaryRester.search` still supports `energy_above_hull`, `band_gap`, `fields`, and `use_document_model=False` workflows needed by `mp_offline`.

**Decisions / changes to plan:**
- No source or archive changes were made to `mp-offline`; the compatibility result is an audit only.
- `mp_offline` remains usable for the historical screening workflow, but fields not mapped as SQL columns, notably `band_gap`, are stored in `json_data` and cannot be queried as `MaterialSummary.band_gap`.

**Next up:**
- If `mp_offline` is maintained further, update its README examples and consider mapping `band_gap` into `MaterialSummary` for SQL filtering.
- Prefer `ss-screen`'s direct `mp-api` loader for new data acquisition unless offline cache behavior is explicitly needed.

**Blockers / upstream issues:** No `MP_API_KEY` was present in the shell, so no live authenticated Materials Project query was run.

## 2026-07-12 — Stage 1 offline MP loader and composition screen start

**Goal of this session:** Start Stage 1 implementation with network-isolated MP data loading and separate composition screening from structure matching.

**Done:**
- Added `src/ssscreen/data/mp.py` with MP summary normalization, an offline `mp_offline` loader, and an explicit live API loader.
- Added `ss-screen dataset mp --output mp.df`, defaulting to `mp_offline` for network-isolated use.
- Added `ss-screen dataset mp --backend api --output mp.df`, using `MPRester()` without passing an explicit API key so `~/.pmgrc.yaml` / standard mp-api config can provide credentials when live access is desired.
- Added `screen_composition_candidates()` in `src/ssscreen/pair/grouping.py`.
- Added `ss-screen composition-screen --df ... --output ... [--summary ...]` to produce a machine-readable composition-candidate CSV and optional JSON summary before robocrys/envmatch structure matching.
- Added tests for MP normalization, offline loader injection, no-explicit-key API loader injection, `dataset mp`, and `composition-screen`.
- Updated `README.md` and `plans/2026-07-12-cli-long-term-screening-roadmap-v1.md` with the new command surface and current Stage 1 status.

**Decisions / changes to plan:**
- `mp_offline` is the default MP backend. The official Materials Project API remains an explicit `--backend api` path.
- `mp-api` is now an optional `mp` extra for the live API backend, keeping default CI free of live MP/network requirements.
- Stage 1 is partially complete: MP loading and composition screening are implemented; WBM loading remains.
- Stage 1a is marked complete for the first reusable CLI artifact because composition candidates can now be generated without condensed structure JSON.

**Next up:**
- Implement `src/ssscreen/data/wbm.py` and `ss-screen dataset wbm`.
- Refactor `ss-screen group` to optionally consume the composition-candidate CSV from `composition-screen`, so Stage 3 no longer repeats Stage 1a internally.

**Blockers / upstream issues:** Live Materials Project querying was not run in CI-style verification because it requires network access and user credentials; tests mock the `MPRester` boundary. The offline path was tested through a fake `mp_offline` client boundary rather than the full local SQLite database. Local untracked `mp-offline/` was added to `.gitignore` so lint does not scan a private/reference package accidentally.

## 2026-07-12 — Baseline commit and Stage 0 CLI CI cleanup

**Goal of this session:** Commit the current repository as a baseline, then start implementing the long-term CLI roadmap.

**Done:**
- Created baseline commit `d71aa25` (`Establish ss-screen baseline`) before making new implementation changes.
- Marked Stage 0 complete in `plans/2026-07-12-cli-long-term-screening-roadmap-v1.md`.
- Added a core GitHub Actions workflow in `.github/workflows/ci.yml` that installs the dev group and runs `ruff`, `black --check`, and `pytest` without optional DFT extras.
- Moved developer tools from the package `dev` extra into the `uv` `[dependency-groups].dev` section in `pyproject.toml`.
- Added `tests/test_project_config.py` so the dependency layout and CI workflow stay aligned with the core-only test path.
- Ran ruff cleanup and formatting on touched Python files.

**Decisions / changes to plan:**
- Stage 0 should keep default CI focused on the core CLI and tests; optional `condense`, `dft`, MLP, MP, and phonon dependencies stay outside the default CI path.
- The next implementation slice should move to Stage 1 / Stage 1a: normalized dataset inputs and composition-only screening artifacts before structure matching.

**Next up:**
- Implement the Stage 1 composition-screening/dataframe builder command surface with small fixtures and schema tests.
- Keep the Chinese user guide synchronized with the staged CLI artifact names once the Stage 1 outputs are stable.

**Blockers / upstream issues:** Local `uv` resolution still depends on network/cache availability in this environment; verification used the existing conda `work` Python plus `ruff`. Local `black` is not installed there, but CI installs it through the `uv` dev group.

## 2026-07-12 — Long-term CLI screening roadmap

**Goal of this session:** Generate a comprehensive long-term CLI plan for reproducing notebook-like screening results through staged command-line artifacts.

**Done:**
- Added `plans/2026-07-12-cli-long-term-screening-roadmap-v1.md`.
- Structured the CLI roadmap into stages: CLI platform, dataset/composition screening, structure-description JSON archives, structure matching, external band-gap candidate export, external gap-result ingestion, final pair generation, multi-theory comparison, SQS generation, MLP relaxation, mixing enthalpy, phonon screening, MP phase-diagram/competing-phase checks, and final recommendation reports.
- Made explicit that high-level band-gap calculations remain outside the core CLI; the CLI exports candidates and later ingests externally calculated gap tables so different theory levels can be compared.

**Decisions / changes to plan:**
- The CLI should separate composition screening from structure matching rather than treating `group` as one opaque operation.
- Condensed robocrys JSON descriptions should become reusable archives with manifests, validation, merging, and summary commands.
- Preliminary MLP stability evaluation belongs after final pair generation and should be optional, backend-pluggable, and clearly labeled as screening rather than final thermodynamic proof.

**Next up:**
- Convert the long-term roadmap into the next executable short plan, likely starting with Stage 0 CI/dependency cleanup and Stage 1 composition-screening/dataframe builder commands.
- Keep the Chinese user guide aligned with these staged CLI artifacts once command names and schemas settle.

**Blockers / upstream issues:** The `create-plan` validation script expected at `./.forge/skills/create-plan/validate-plan.sh` is still absent, so the roadmap was manually checked for required structure and placeholder markers.

---

## 2026-07-11 — CLI-first implementation: condense command and CLI tests

**Goal of this session:** Shift implementation priority to the reusable CLI, update the plan, and continue with the next CLI slice.

**Done:**
- Added `plans/2026-07-11-cli-first-implementation-v1.md` and marked the completed CLI-first tasks.
- Added CLI regression fixtures in `tests/data/cli/` and `tests/test_cli.py`, covering `ss-screen --help`, the `pair` command's gap-compression behavior, and the new `condense` command surface.
- Added `src/ssscreen/data/condense.py` with optional-runtime robocrys condensation helpers and `CondenseSummary`.
- Added `ss-screen condense --input ... --output-dir ... [--overwrite]` to `src/ssscreen/cli/app.py`.
- Updated `README.md` and `docs/PROJECT_PLAN.md` so the canonical command names are `valence-filter`, `group`, `pair`, and `condense`.

**Decisions / changes to plan:**
- CLI command names are now frozen to the shorter current names (`group`, `pair`) rather than the older `group-screen` / `pair-screen` planning names.
- `robocrys` remains optional: default tests mock the data-layer entry point and do not import robocrys unless the real `condense` runtime path is used.

**Next up:**
- Add a CI baseline that runs core CLI/tests without `[dft]`.
- Continue M2 with MP/WBM DataFrame builders once the CLI test harness is stable.
- Draft the Chinese user guide around the now-stabilized CLI command names.

**Blockers / upstream issues:** `uv run pytest` currently tries to resolve optional `[dft]` dependencies or fetch packages in this environment; tests were run with `/home/bonan/miniconda3/envs/work/bin/python`, matching the existing project environment noted earlier.

---

## 2026-07-11 — Scope split into Chinese docs and reusable CLI/package

**Goal of this session:** Clarify the next work plan after recognizing `ss-screen` is two related projects, not only a package migration.

**Done:**
- Confirmed two workstreams: a Chinese technical documentation project for the screening process, and an English CLI/package project for CI-ready reuse.
- Confirmed language boundaries: technical report and user guide should be Chinese-first; CLI commands, parameters, Python APIs, docstrings, tests, and CI should remain English-first.
- Added `plans/2026-07-11-next-task-breakdown-v1.md` with the next task breakdown, covering project-scope cleanup, Chinese technical report, Chinese user guide, `ss-screen pair` CLI regression coverage, M2 `condense`, MP/WBM loaders, CI baseline, README cleanup, and logging.

**Decisions / changes to plan:**
- Treat `docs/algorithm_structure_grouping.md` and `docs/algorithm_gap_backfill_pairing.md` as Chinese algorithm appendices / evidence sources, not the final top-level technical report.
- Add a Chinese `docs/technical_report.md` and Chinese `docs/user_guide.md` as explicit documentation deliverables before expanding far into M2/M3.
- Keep README short and English-first, linking to the Chinese technical report and user guide.

**Next up:**
- Update `docs/PROJECT_PLAN.md` to encode the two-workstream roadmap and language rules.
- Draft `docs/technical_report.md` and `docs/user_guide.md` skeletons.
- Add the small `ss-screen pair` CLI regression test before implementing M2 `condense`.

**Blockers / upstream issues:** The `create-plan` validation script expected at `./.forge/skills/create-plan/validate-plan.sh` is not present in this repository, so the new plan was manually checked for required structure instead.

---

## Current status (snapshot)

- **Phase:** M0 + M1 complete. Pair-screening core shipped as installable CLI; `ss-screen pair` reproduces the notebook's 52 binary pairs exactly (52/52 identical rows).
- **Next milestone:** M2 — data layer (`data/mp.py`, `data/wbm.py`, `data/condense.py` CLI); the only thing M1 cannot do yet is *build* the input `.df` files (it consumes pre-built ones).

### Milestone tracker
- [x] **M0** — Scaffolding: `pyproject.toml`, `src/ssscreen/` skeleton, `.gitignore`, ruff/black, README, `git init`. DONE.
- [x] **M1** — Pair-screening core. DONE: `config.py`, `pair/{envmatch,grouping,filters,pairing}.py`, `data/io.py`, `cli/app.py` (3 commands), 41 tests passing, CLI reproduces research output. DONE.
- [ ] **M2** — Data layer: `data/mp.py`, `data/wbm.py`, `data/condense.py` (the `ss-screen condense` command); externalize MP key.
- [ ] **M3** — DFT workflow factories `[dft]`: `make_bandstructure_updater`, `init_aiida`, MACE relax, hull stability.
- [ ] **M4** — Defect ranking `[dft]`: elemental refs, vacancy driver, cation/anion ranking.
- [ ] **M5** — Docs & technical reviews: `docs/algorithm_structure_grouping.md` (Part 1) and `docs/algorithm_gap_backfill_pairing.md` (Part 2) already exist and are high-quality source-indexed; remaining: a top-level package user guide + cross-references.

---

## 2026-07-06 — Both specs peer-reviewed & revised (4 agents, all P0/P1/P2 fixed)

**Goal of this session:** Have independent agents audit the two algorithm specs; fix every issue found.

**Done:**
- Ran 4 parallel review agents: (1) Doc1 scientific accuracy, (2) Doc2 scientific accuracy,
  (3) Doc-vs-code consistency audit, (4) structure/readability for implementers. Personally
  re-verified every P0/P1 claim against source code with bash/python.
- **P0 fixes (hard errors that would mislead migration):**
  - **Ternary uses real mBJ, not HSE06** — `mbj-screen-ternery.ipynb` Cell 11 uses `metagga='mbj'`
    (verified). Rewrote Doc2 §3.2/§4.3/§7/§8 to reflect FOUR independent DFT lines (binary PBE,
    binary VASP-HSE06, binary ABACUS-HSE06, ternary mBJ), and that "mbj" in filenames means
    different methods for binary vs ternary.
  - **Calc-submission sizes wrong** — wrote "286/927 submitted"; actual submission is 665/1588
    (verified). 286/927 are the *gap-success* subset. Fixed Doc1 §6, Doc2 §1/§4.3.
  - **direct-not-filtered consequence disclosed** — measured: 54% of binary pairs & 71% of ternary
    pairs are both-indirect (verified). Added table + migration guidance to Doc2 §5.4.
  - **Interface contract contradiction** — Doc1 said band_gaps gets overwritten by mBJ; Doc2 actually
    creates a new `gaps_mbj` field AND rebuilds the group (dropping members). Aligned both docs:
    Doc1 §4 now documents band_gaps as dynamic PBE field + points to Doc2 §4.2 for the rebuild contract.
- **P1 fixes (scientific argument / self-consistency):**
  - "充分条件 → 逐级必要筛": Doc1 §2.2/§2.3 no longer calls envmatch a sufficient condition; both
    layers are now framed as successive necessary filters (envmatch only captures
    `(poly_formula, geometry.type)`, not space group/lattice/bowing → ≈same-prototype, not ≈alloyable).
  - Robustness rationale assumptions: Doc2 §1 now explicitly states the two assumptions (Vegard-like
    gap-vs-composition + consistent per-endmember DFT error) and when they break.
  - Physical-window vs engineering-threshold split: Doc2 §5.1 separates the *physical target window*
    (0~0.5 / 0~0.15 eV) from the *engineering thresholds* (0.15/1.5 group-level, 0.2/0.3/0.8 pair-level),
    notes group-vs-pair use different values by design, and flags the LOW_HI/MID_LO overlap +
    `any()` logic that can let through "neither-end-near-zero" pairs (with min/max fix suggestion).
- **P2 fixes (precision/structure):**
  - Added pipeline data-flow diagram (Doc1 §1) spanning both parts.
  - Fixed cell refs: abacus-hse-analysis is Cell 5 (was "Cell 8"); mbj-analysis is Cell 8.
  - Documented `material_id` extraction differs (`split()[1]` vs `split()[0]`) between analysis notebooks.
  - Doc1 §3.5 added boundary/exception handling (robocrys fail, X-disambiguation, missing condensed).
  - Doc1 §5 added "group-level gap-diversity gate" row (binary/ternary inconsistent) + natoms
    reclassified as post-grouping; §7 added template-construction inconsistency.
  - Doc1 §3.3 fixed swap_elem_by_X asymmetry note + CoO/NiO example; §3.2 fixed list-vs-tuple + §-ref.
  - Doc2 §5.3 flagged self-pairing (i,i) bug; §8 flagged direct-is-string-type gotcha.

**Decisions / changes to plan:**
- The "mBJ naming misnomer" is more severe than first thought: ternary genuinely IS mBJ (not just
  binary ABACUS-HSE06 mislabeled). Migration MUST let binary/ternary use different methods.
- direct-as-info-column is now flagged as a decision point needing re-evaluation (not settled),
  given 54–71% both-indirect pairs in current output.
- Note: M0+M1 code was shipped by a parallel session *during* this review (see next entry). The spec
  fixes above apply to `docs/`; the M1 code may need a follow-up pass to align with the corrected
  mBJ/ternary understanding (e.g. gap-source config should be per-system, not assume one global method).

**Next up:** Specs are now review-hardened. Check whether M1 code already reflects these corrections
(esp. the mBJ-vs-HSE06-per-system point and the direct-column consequence); if not, schedule a fix.

**Blockers / upstream issues:** none new — all issues were in our docs, not upstream code.

---

## 2026-07-06 — M0 + M1 shipped: installable CLI, 41 tests, reproduces notebook output

**Goal of this session:** Build the formal CLI package per the approved plan (full pipeline, AiiDA as optional extra, refactor envmatch first).

**Done:**
- **M0 scaffolding:** `pyproject.toml` (hatchling, `ss-screen` console script, `[condense]`/`[dft]`/`[dev]` extras), `.gitignore` (excludes `*.df`, `*.aiida`, `*.tar.gz`), `LICENSE` (MIT), `README.md`, `git init`.
- **M1 config** (`src/ssscreen/config.py`): `Thresholds` / `SelectionThresholds` / `GroupThresholds` / `PairThresholds` dataclasses + `DEFAULT_EXCLUDED_ELEMENTS` + `composition_permutations(nelems)`. All notebook magic numbers centralised.
- **M1 envmatch** (`pair/envmatch.py`): faithful port of `pair-screening/envmatch.py`; **fixed the `__getitem___`→`__getitem__` typo**; added `band_gaps` field, type hints, docstrings, `to_dict()`.
- **M1 grouping** (`pair/grouping.py`): merged binary (cell 15) + ternary (cell 5) into one `group_by_composition_template(df, nelems)`; plus `attach_band_gaps`.
- **M1 filters** (`pair/filters.py`): `is_valence_assignable`, `valence_filter` (valence-filter.ipynb cell 11), `apply_element_exclusion`, `has_gap_diversity`, `apply_size_gate`.
- **M1 pairing** (`pair/pairing.py`): `gaps_valid` + `enumerate_pairs` + `attach_gaps_and_compress` (the cell-4 lockstep compression) + `pairs_to_dataframe`.
- **M1 data/io** (`data/io.py`): `CondenseLoader`, `dump_group_df`, `load_group_df` (handles BOTH records-array AND pandas column-oriented JSON — the real `binary-group-df.json` is column-oriented), `read_mbj_gaps`, `write_pairs_csv`.
- **M1 CLI** (`cli/app.py`): three commands — `ss-screen valence-filter`, `ss-screen group`, `ss-screen pair` — all thresholds exposed as `--options` with research defaults.
- **M1 tests**: 41 tests across `test_{envmatch,grouping,pairing,filters}.py` using 4 real robocrys fixtures copied from `../mp-condense/condensed/` (CeSe2 polymorphs mp-1080296/0351 with identical env, mp-1080265/1080248 as different-env controls). **41/41 passing.**
- **End-to-end verification:** `ss-screen pair` on the real research data (`binary-group-df.json` + `mbj_gaps_binary_2025_0425_pmg_info.csv`) produces **52 pairs identical to `mbj_result_binary_20250426.csv`** (52/52 rows match as sets; no row only-in-ours or only-in-notebook).
- Package installed editable in conda env `work`: `pip install -e .` succeeded; `ss-screen --help` works.
- Re-found two pre-existing high-quality docs: `docs/algorithm_structure_grouping.md` (Part 1) + `docs/algorithm_gap_backfill_pairing.md` (Part 2) — these cover the M5 technical-review content already; integrated into the milestone tracker.

**Decisions / changes to plan:**
- The `pair` command needed `attach_gaps_and_compress` (new helper) because the notebook's cell-4 compresses the group's `compositions`/`mp_ids` in lockstep with gap availability — without it, `gaps[k]` misaligns with `compositions[k]`. Caught by the end-to-end smoke test, not unit tests (a gap in test coverage to note).
- `load_group_df` supports both JSON layouts because the real `binary-group-df.json` is pandas column-oriented (`{col: {row_idx: val}}`), not a records array — only discovered during the smoke test.
- Env `work` lacks `robocrys`; this does NOT block M1 (envmatch consumes pre-condensed JSON). Only the future `ss-screen condense` command (M2) will need robocrys → declared in the `[condense]` extra.
- `mp_offline` is a private package; M1's `group`/`pair` commands take pre-built `.df` pickles as input and do NOT require `mp_offline` at runtime. Data acquisition (M2) is what will use it.

**Next up:**
- **M2 — data layer**: `data/mp.py` (`load_mp_dataset`, ported from `datacollect.py`), `data/wbm.py` (`load_wbm_data`), `data/condense.py` (the `ss-screen condense` single-file + batch worker, ported from `mp-condense/condense.py` + `condense_one.py`). This removes the last "consume a pre-built df" limitation.
- Add a CLI integration test that runs `ss-screen pair` on a tiny committed fixture group_df + gaps CSV, so the lockstep-compression regression is covered going forward.

**Blockers / upstream issues (read-only dirs — do NOT fix there):**
- All previously-listed upstream issues remain (envmatch dunder FIXED in our copy; live MP API key still in `../screen-antiperovskite/satbility-mp.ipynb`; checkpoint `if name==` bug; launcher duplication). None block further work.
- `robocrys` absent from env `work` — only blocks M2's `condense` command at runtime, not development.

---

## 2026-07-06 — Part 2 spec refined: tunable-range rationale + pair-criteria restatement

**Goal of this session:** Incorporate the user's two key clarifications into `docs/algorithm_gap_backfill_pairing.md`.

**Done:**
- Added a new subsection in §1 — **"为什么对带隙做范围筛选是合理的（方法论的根基）"**. This captures the
  foundational rationale the user articulated: a solid-solution is a *continuous compositional range*, so DFT's
  systematic gap error gets absorbed into a *compositional shift* — we can still tune the alloy to hit the target
  gap window. This is why range-based gap screening is sound despite DFT error. Rewires §1 to show how Part 1
  (isostructural group → physical precondition for tunability) and Part 2 (gap-spanning pair → target window)
  together yield "alloyable AND tunable-to-target" candidates.
- Restated §5 pair criteria in clean physical terms per user: **one endmember near-zero gap, the other small-gap
  (e.g. 0–0.5 eV)**, so the alloy's gap can be continuously tuned across a small window (e.g. 0–0.15 eV).
  Restructured §5 into: §5.1 (the physical form we seek, the source of the criteria) → §5.2 (group-level) →
  §5.3 (pair-level, mapping the three thresholds to the §5.1 concepts) → §5.4 (direct) → §5.5 (output schema).
- Aligned §6 parameter table to the new terminology ("小带隙端" instead of "中等端"), with cross-refs to §5.1.
- Renumbered downstream subsections consistently.

**Decisions / changes to plan:**
- The "tunable range absorbs DFT error" rationale is now documented as the **methodological foundation** of the
  whole pipeline, not just a side note. Both spec docs should be read with this in mind.
- Pair criteria are now expressed as physical concepts (near-zero end / small-gap end / tunable-range cap) with
  the numeric thresholds (0.15/1.5/0.2/0.3/0.8) demoted to "numerical instances of these concepts" — consistent
  with the user's stance that exact thresholds are tunable sieves, not algorithm core.

**Next up:** both Part 1 & Part 2 specs are now content-complete. Proceed to Milestone 0 (scaffolding) + M1 (port envmatch).

**Blockers / upstream issues:** none new.

---

## 2026-07-06 — Part 2 algorithm spec written (gap backfill + pairing)

**Goal of this session:** Write the formal spec for Part 2 of the pipeline (high-precision gap computation → backfill into groups → pair enumeration), with code-backed evidence.

**Done:**
- Read all of `screen-mbj/`: `pbe-screen-binary.ipynb`, `hse-screen-binary.ipynb`, `mbj-screen-binary.ipynb`
  (ABACUS HSE06, incl. PBE cell-relax), `mbj-analysis.ipynb`, `abacus-hse-analysis.ipynb`. Cross-checked the three
  DFT lines (PBE / VASP-HSE06 / ABACUS-HSE06) and re-read both `pairing_mbj_gaps_*.ipynb`.
- Confirmed WBM dataset **does** carry PBE band gaps (`datacollect.py:69` `df_all['band_gap']=df_all.gap`,
  257489 rows, ~85% zero/metallic) — so Part 1's PBE gaps come from the DB itself for both MP and WBM.
- Measured **gap-source coverage** (key finding): binary group has 680 unique members, VASP-HSE06 (2025-0425)
  covers only 286 (42%), ABACUS-HSE06 (2025-0528) covers 504 (74%); ternary 1646 members, VASP-HSE06 covers 909 (55%).
  → The current pairing notebooks hardcode `*_2025_0425` (older, less-covered VASP-HSE06) and silently drop
  members without a high-precision gap via `.get()`→`None`→`is_valid` filter. This is the main reason the final
  pair counts are low (binary 52, ternary 299).
- Wrote `docs/algorithm_gap_backfill_pairing.md` — formal spec of Part 2 with full source-code index (§8).
  Key framing per user: (1) the high-precision functional (mBJ / VASP-HSE06 / ABACUS-HSE06) is a **configurable
  sieve parameter, not algorithm core**; (2) the gap-size criteria are tunable thresholds; (3) `direct` is an
  **info column, not a hard filter** (user-confirmed).

**Decisions / changes to plan:**
- Part 2's high-precision method is abstracted to a configurable input (not bound to any one functional) —
  matches the user's view that it's "a sieve parameter". Migration target: `config.py` + CLI arg, no hardcoded CSV name.
- Documented the "mBJ" naming misnomer: `mbj-screen-*.ipynb` actually runs ABACUS HSE06, and `mbj_gaps_*.csv`
  comes from VASP HSE06 — historical naming to clarify during migration.
- Coverage-rate monitoring + optional PBE fallback flagged as a migration must-do (avoid silent member drops).

**Next up:**
- With both Part 1 & Part 2 specs locked, proceed to Milestone 0 (scaffolding) + Milestone 1 (port envmatch core).
- Milestone scope clarification: `pair/pairing.py` (`gaps_valid` + `enumerate_pairs`) is now scoped to the
  Part-2 milestone (gap backfill + pairing), not M1 (which is grouping only).

**Blockers / upstream issues:** none new beyond those recorded in
`algorithm_gap_backfill_pairing.md` §8 (pairing hardcodes old CSV; silent member drop; `has_direct` misnomer).

---

## 2026-07-06 — Part 1 algorithm spec written (structure grouping)

**Goal of this session:** Extract the structure-grouping algorithm from the research notebooks with code-backed evidence; write a formal spec for Part 1 of the pipeline.

**Done:**
- Read all of `pair-screening/`: `envmatch.py`, `datacollect.py`, `screening-binary.ipynb` (42 cells),
  `screening-tenary.ipynb` (32 cells), `pairing_mbj_gaps_binary.ipynb`, `pairing_mbj_gaps_ternary.ipynb`,
  `valence-filter.ipynb`. Cross-checked against result CSVs/JSONs (`binary-group-df.json`, `ternary-group-df.json`,
  `mbj_gaps_*`, `mbj_result_*`).
- Diffed `envmatch.py` (module) vs the inlined copy in `screening-tenary.ipynb` Cell 17:
  only **one** behaviour-affecting difference (`find_unique_envs` regex sanitization of `site['element']` is
  present in the module, missing in the inline copy). All other diffs are cosmetic (dataclass vs dict,
  `compositions` vs `Compositions`, function name, `.tolist()`).
- Clarified the pipeline's **two-part split** with the user (driven by mBJ cost):
  - Part 1 = structure grouping via two-layer match (cheap, the scope of this doc);
  - Part 2 = mBJ gap computation + gap backfill into groups + pair enumeration (separate doc).
- Wrote `docs/algorithm_structure_grouping.md` — formal spec of Part 1 with full source-code index (§7).
  Key framing confirmed by user: the two-layer match (composition match → envmatch) is the **only** load-bearing,
  order-dependent skeleton; every other filter (e_hull, PBE-gap, valence, element exclusion, natoms) is a
  **movable/tunable gate** that only shrinks the candidate set.

**Decisions / changes to plan:**
- Part 1 deliverable is now scoped to **grouping only** (not pairing). Pair enumeration is Part 2 work.
  Milestone 1 in PROJECT_PLAN.md should be read as "port envmatch + grouping + filters"; the `pair/pairing.py`
  module (gaps_valid + enumerate_pairs) belongs to a Part-2 milestone (TBD).
- Confirmed the module version (`envmatch.py`) is the migration baseline; the ternary inline copy is a stale
  duplicate to discard.

**Next up:**
- Discuss & write Part 2 spec: mBJ gap source → backfill into groups → pair enumeration + gap criteria
  (incl. settling whether `direct` is a hard filter or an info column).
- After both specs are locked, proceed to Milestone 0 (scaffolding) + Milestone 1 (port envmatch core).

**Blockers / upstream issues:** none new (see entry below for the standing list).

---

## 2026-07-06 — Exploration complete & plan written

**Goal of this session:** Map the whole `HC/` workdir, understand the project, draft a packaging plan.

**Done:**
- Ran 4 parallel Explore subagents over all of `/home/bonan/work/HC/`:
  pair-screening core; structure-type dirs (rocksalt/zincblend/Chalcopyrite/antiperovskite);
  data-prep dirs (mp-condense, wbm-dataset); downstream dirs (screen-mbj, screen-promising, simple-defects, old-screen-202411).
- Identified the project as a 4-stage pipeline: **data → pair-screening → band-gap verification → defect ranking**.
  Core algorithm = `envmatch` (robocrystallographer local-environment fingerprinting with the variable element relabeled to `X`).
- Catalogued reusable code, duplication, and defects (see `PROJECT_PLAN.md` §2).
- Wrote full blueprint: `docs/PROJECT_PLAN.md` (target layout, dependency strategy, 5 milestones, conventions).
- Wrote `AGENTS.md` (operating rules; **READ-ONLY boundary** = only `ss-screen/` is writable).
- Wrote this log.

**Decisions / changes to plan:**
- User decisions recorded: **full pipeline** scope; AiiDA as optional `[dft]` extra;
  package location = `/home/bonan/work/HC/ss-screen`; **refactor envmatch first**.
- Package working name: `ss-screen` (import name `ssscreen`).

**Next up:**
- Milestone 0: `git init` in `ss-screen/`, `pyproject.toml`, `src/ssscreen/` skeleton, `.gitignore` (exclude GB-scale data & `.aiida`), ruff/black config, README stub.
- Milestone 1: port `pair-screening/envmatch.py` → `src/ssscreen/pair/envmatch.py`
  (fix `__getitem___` → `__getitem__`, add type hints + docstrings);
  extract `group_by_composition_template`, `gaps_valid`, `enumerate_pairs`, filters into their modules;
  centralize thresholds/element-lists in `config.py`;
  write unit tests with tiny real robocrys fixtures sampled from `mp-condense/condensed/`;
  wire `ss-screen pair-screen` CLI.

**Blockers / upstream issues (read-only dirs — do NOT fix there, note for migration):**
- `pair-screening/envmatch.py:132` — `__getitem___` misspelled (3 trailing `_`); indexing silently broken.
- `pair-screening/screening-tenary.ipynb` — stale inlined envmatch copy, diverges from module.
- Hardcoded relative paths throughout (`wbm-dataset/condense/condensed`, `../mp-condense/condensed`).
- **Live MP API key committed** in `screen-antiperovskite/satbility-mp.ipynb` and used in `simple-defects/` — must be externalized to `MP_API_KEY` env var in the package.
- `mp-condense/.ipynb_checkpoints/condense-checkpoint.py:31` — `if name ==` missing `__main__`.
- DFT launcher functions (`launch_hse06`/`launch_mbj`/`get_upd*`) duplicated verbatim across 6+ notebooks; `rocksalt.ipynb` ≡ `zincblend.ipynb` cells 9–11.

---

<!-- Append new entries above this line, newest first. Use the template from AGENTS.md §5. -->
