# demo_v1 · 10 μm 原生 GUI 演示交付清单

## 需要交付的内容

| 项目 | 已核对的来源 | 交付要求 |
|---|---|---|
| 软件 | 当前工作副本，软件版本 1.0，基线提交 `1bc90932fd97c7d92ac1f98403560a51b932a558` | 冻结包含本轮 GUI 修改及新增源码的软件快照，并记录校验值。只检出基线提交会缺少本次演示的按钮行为。 |
| 环境 | Windows GUI 使用 Python 3.11.9、PySide6 6.12.0；Ubuntu WSL 常规项目环境使用 Python 3.11.18 | 正式交付时分别记录依赖版本和安装步骤，在接收机配置项目解释器及 WSL 后端。演示中的 MACE、声子等结果从模板载入。 |
| 初始工程 | `10.0 μm演示.ssproject` | 使用 GUI 的「打开工程文件 .ssproject」导入到新目录。已与 demo_v1 的配置及文件清单逐项比对，3,216 个预置文件的 SHA-256 全部匹配。 |
| 独立数据库 | `01_dataset/default.db`，2,220,736,512 字节 | 数据库独立提供或由接收方取得同版文件，放在新工程的 `01_dataset/default.db`。SHA-256 为 `d54bca48d1e00bdfd8db7c1e5a7b5844ccb755b948335930f09fe85444a7ebb8`。数据库留在软件仓库外。 |

## 新工程的起始状态

- 预置 03 结构描述、05 带隙、07 SQS、08 弛豫、10 声子及 11 竞争相与凸包的结果及相关结构、图件。13 保留 `candidate_evaluation.csv`、`substrate_top_matches.csv` 两份评价输入。
- 01 除独立数据库外从空输出开始；02、04、06、09、12 由接收方现场生成。不要从已运行工程带入日志、阶段标记 `.10um-cache-used`、CLI 进度 `.ten_micron_progress.json` 或手动导出的 13 评价表。
- 03、05、07、08、10、11 应显示预置结果尚待使用。13 首次打开表格为空；12 成功后才启用右下角「生成候选评价」。

## 复跑验收基准

| 检查点 | 本次演示记录 |
|---|---|
| 04 结构匹配 | 398 个结构组，部分覆盖 |
| 06 端元配对 | 波长 10 μm，严格带隙上下限 0 和 0.4 eV，116 对端元 |
| 07 SQS | 108 项已生成、8 项跳过；从 07 页按钮校验并进入 08 |
| 08 至 11 | 08 页按钮校验后进入 09；现场运行混合焓；10 和 11 分别通过页面按钮校验并进入下一步 |
| 12 综合推荐 | 116 对，promising 66、uncertain 30、low-priority 20。异机复跑还需对照端元配对身份与逐对分级。 |
| 13 候选评价 | 点击右下角高亮按钮前为空表；点击后显示 116 条候选评价。 |

## 接收方操作

推荐使用包含最新启动器修改的源码。Windows 文件夹中可双击 `start-10um.cmd`，或在 PowerShell 的 clone 目录运行 `.\start-10um.cmd`；Ubuntu WSL 中运行 `bash scripts/start-10um.sh`。首次需联网访问 GitHub、`api.nuget.org` 和 Python 包索引，Ubuntu WSL 及 Windows 互操作需预先可用。启动器在当前目录的 `ss-screen-10um` 下准备数据、运行环境和独立工程，校验通过后打开 01 页。再次运行会复用已有工程及其进度。以下步骤供手动安装使用。

1. 下载本 Release 的源代码、`project-10um.zip`、`default.db.zip` 和离线读取器 wheel。展开工程压缩包后保留文件名 `10.0 μm演示.ssproject`。两个环境的 constraints 文本记录本次用到的软件版本。
2. 在 Windows 源码目录用 Python 3.11 创建项目环境，激活后运行 `python -m pip install -c <Windows约束文件> -e ".[gui]"`。在 Ubuntu WSL 中进入同一源码目录，用 Python 3.11 创建并激活 `.venv`，运行 `python -m pip install -c <WSL约束文件> -e ".[mp]" <下载的mp_offline轮子路径>`。
3. 在 Windows GUI 环境从源码目录运行 `python -m ssscreen.gui.app`。选择「打开工程文件.ssproject」，导入「10.0 μm演示.ssproject」到新目录。解开数据库压缩包，将 default.db 放入新工程的 01_dataset。WSL 后端应使用源码目录的 .venv。
4. 从 01 开始，运行离线 Materials Project 获取；02 运行组成模板筛选。03 点右下角「进入 04 结构匹配与材料分组」校验预置描述，04 运行结构匹配，05 使用预置带隙，06 运行端元筛选。随后按上表推进至 13。按 SHA-256 核对下载文件；原始数据库指纹见上表。
5. 数据来源为 Materials Project，数据库为离线快照；格式转换及演示筛选由 ss-screen 完成。请保留 Materials Project 署名及原始资料的引用。见 [Materials Project 引用说明](https://materialsproject.org/about/cite) 和 [使用条款](https://materialsproject.org/about/terms)。

## 自动准备 Windows Python

- 不依赖 `py.exe`。启动器实际执行版本、架构和标准库探针，优先复用健康的 GUI 环境或已安装的 Windows Python 3.11；发现解释器时禁止 uv 自动下载或选择 uv 管理的 Python，避免重复命中 error 4551。
- 缺失时，从 [CPython 官方 NuGet 渠道](https://docs.python.org/3.11/using/windows.html#the-nuget-org-packages) 下载私有运行时，在解压前核验固定 SHA-256，解压后核验 `python.exe`、`pythonw.exe` 和 `python311.dll` 的有效 PSF 签名。无需安装 NuGet 客户端或 .NET SDK，无系统 Python 安装、PATH 修改或管理员提权。
- 私有运行时固定为 3.11.9，与已有 Windows GUI 验收基线相同。它是该系列最后的 PSF Windows 二进制发行版，不包含之后仅以源码发布的 3.11 安全修复。后续升级需同时验收运行时、Windows 依赖约束和 GUI；维护者可通过 `SSSCREEN_WINDOWS_PYTHON` 指向已获准运行的匹配架构 Python 3.11，显式选择失败时不会静默切换。
- GUI 创建环境时使用启动进程的绝对解释器路径。已有环境执行失败时，先保留为 `.venv-gui.unusable-<编号>` 再重建；工程与数据库保持原状。WSL 解释器仍单独管理，不接收 Windows 专用的 Python 选择设置。
- 连接失败会自动重试，校验通过的下载会复用；错误后可重新运行相同入口。安装日志为 `setup.log`，GUI 输出为 `gui-startup.log`，均位于 `ss-screen-10um/`。若签名验证或应用控制策略仍阻止运行，日志记录文件路径及错误；不自动解除 Windows 防护。

| 固定发行包 | SHA-256 |
|---|---|
| [python 3.11.9，Windows x64](https://www.nuget.org/packages/python/3.11.9) | `9283876d58c017e0e846f95b490da3bca0fc0a6ee1134b2870677cfb7eec3c67` |
| [pythonarm64 3.11.9，Windows ARM64](https://www.nuget.org/packages/pythonarm64/3.11.9) | `2f5b3bee38850fdde1b44227a23b8130d329839558376d2eb11099ce2b2cc33c` |

启动器回归入口为 `tests/test_start_10um.py`，其中 PowerShell 合约由 `tests/test_windows_python.ps1` 验证；在 WSL 项目环境中运行，Windows 检查经互操作调用系统自带的 Windows PowerShell/Pester。不下载演示数据库或执行科学计算。
