# 脚本与自动化导航

- 从 WSL 原生路径启动时，start-10um.sh 传递当前发行版；PowerShell 使用原生 UNC 路径建立目录。GUI 对工程 UNC 共享选择相同的 WSL 后端。

- Windows 启动器使用 .NET 核验 uv 下载，公开仓库克隆验收覆盖 Windows wheel 内的数据读取模块及 GUI 到 WSL 的 01 命令连接。

- [Windows 启动入口](../../start-10um.cmd) 和 [WSL 启动入口](../../scripts/start-10um.sh) 调用 [环境引导脚本](../../scripts/start-10um.ps1) 及 [工作区准备脚本](../../scripts/start_10um.py)。从公开 Release 获取校验过的数据，在命令执行目录创建 ss-screen-10um，使用独立 Windows/WSL 环境打开 01 页。

真实目录：[`scripts/`](../../scripts/) 和 [`.github/`](../../.github/)

## 文件映射

| 文件 | 作用 | 关联测试/配置 |
|---|---|---|
| [`scripts/curate_upstream_references.py`](../../scripts/curate_upstream_references.py) | 发现、分类、脱敏、去重、生成和验证 `references/` 历史资料归档 | [`tests/test_reference_curation.py`](../../tests/test_reference_curation.py) |
| [`scripts/build_full_user_manual.py`](../../scripts/build_full_user_manual.py) | 从中文 Markdown 权威源稿确定性生成正式 A4 Word 手册，并执行结构检查 | [`docs/user-guide/SS-Screen_完整功能版_用户使用手册.md`](../../docs/user-guide/SS-Screen_完整功能版_用户使用手册.md) |
| [`scripts/build_copyright_manual.py`](../../scripts/build_copyright_manual.py) | 从 V1.0 登记版 Markdown 同源生成 A4 DOCX/PDF，并检查软件名称、版本、必要章节、图片数量和著作权人信息 | [`docs/user-guide/SS-Screen_V1.0_软件著作权登记操作手册.md`](../../docs/user-guide/SS-Screen_V1.0_软件著作权登记操作手册.md) |
| [`scripts/build_copyright_manual_assets.py`](../../scripts/build_copyright_manual_assets.py) | 执行轻量 V1.0 CLI 教学链，对昂贵阶段读取已有真实教学结果，生成终端界面、软件结构图和分阶段流程图 | [`docs/user-guide/assets/copyright-v1/`](../../docs/user-guide/assets/copyright-v1/) |
| [`scripts/build_copyright_source.py`](../../scripts/build_copyright_source.py) | 按稳定路径顺序汇总正式包，生成前后各 2500 行的 A4 PDF、无前置标号 Word、可检索文本和 SHA-256 清单 | [`docs/copyright-source/README.md`](../../docs/copyright-source/README.md) |
| [`scripts/update_copyright_application.py`](../../scripts/update_copyright_application.py) | 在申请表副本中定位并扩写“主要功能”栏，同时验证 500--1300 字范围 | [`docs/copyright-application/计算机软件著作权登记申请表_主要功能扩写.docx`](../../docs/copyright-application/计算机软件著作权登记申请表_主要功能扩写.docx) |
| [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) | GitHub Actions 中安装核心项目并运行测试 | [`tests/test_project_config.py`](../../tests/test_project_config.py)、[`pyproject.toml`](../../pyproject.toml) |

## 资料整理脚本的边界

- 支持 dry-run、write 和 validate-only 模式。
- 输出由 `references/manifest.json` 和各家族 README 描述。
- 保留 notebook 科研输出，但会处理已知凭据风险。
- 大型数据、AiiDA 转储、压缩包、计算目录和生成调度文件被明确排除。
- 不得在没有重新核对来源、许可和秘密信息的情况下扩大收集范围。

## 自动化维护规则

- 脚本参数、输出 schema 或资料布局变化时，同步本页、`references/README.md`、manifest 相关测试和 ZMD 历史资料导航。
- CI 命令或 Python 支持范围变化时，同步 `pyproject.toml`、本页和测试导航。
- 缓存与生成的 `__pycache__/`、`.ruff_cache/` 不进入 ZMD 文件资产。
- 修改手册内容时先改 Markdown 源稿，再运行 `scripts/build_full_user_manual.py --check` 重新生成 Word；正式交付前还要重新执行隐私、结构、无障碍和逐页视觉检查。
- 登记版手册修改后运行 `scripts/build_copyright_manual.py --input <md> --docx <docx> --pdf <pdf> --check`；正式提交时再加 `--rights-holder "<法定主体名称>"` 替换唯一占位文字，重新生成并逐页检查 PDF。

## 最近同步

- 2026-09-02：发布前用 Black 机械格式化资料整理脚本及其测试，行为与文件职责不变；完整相关
  测试、Ruff和Black通过。
- 2026-08-24：资产构建器新增独立的 VASP 方法身份 gap-export 演示，生成输入、执行、任务/结构和模板检查四张截图；不运行VASP。
- 2026-08-24：使用登记版构建器重建扩写后的第六至十七章，结构检查覆盖174个标题、41个表格、63个代码块和34处图片引用。
- 2026-08-24：使用资产构建器重新捕获带 `SS-SCREEN` ASCII Logo 的真实启动/版本界面，手册图片总数保持 32 张。
- 2026-08-21：手册资产构建器新增 8 张任务界面，支持帮助输出截断和真实 JSON/JSONL/CSV 结果的字段投影，避免绝对路径泄露和过长文本压缩。
- 2026-08-18：V1.0 登记版构建器完整嵌入 24 张 CLI/设计/流程图，并校验 Word 图片数量、版本元数据和 PDF 版式。
- 2026-08-18：源程序材料构建器新增无前置标号 DOCX，保留恰好 5000 个源码段落并按每 50 行强制分页。
- 2026-08-18：新增申请表更新脚本，只替换“主要功能”合并单元格并保留其他字段与原有字体格式。
- 2026-08-05：新增源程序鉴别材料构建器，固定 `src/ssscreen/**/*.py` 范围、路径排序、前后各 2500 行和每页 50 行的 PDF 版式。
- 2026-08-05：软著登记版构建器的编制日期更新为 2026 年 8 月 5 日，并在第一章背景扩充后同源重新生成 DOCX/PDF。
- 2026-08-04：软著登记版构建器的软件全称常量更新为“新材料计算筛选软件”，同源重新生成 DOCX/PDF。
- 2026-08-04：新增软著登记版 DOCX/PDF 构建器，固定 `V0.1.0` 软件识别信息、A4 页面、页眉页码、中文字体和结构校验。
- 2026-08-03：正式手册构建器封面版本同步为 V1.4，对应 Stage 11 综合推荐当前能力。
- 2026-08-03：正式手册构建器封面版本同步为 V1.3，对应 Stage 1 MP 快照 provenance 与 deprecated 过滤。
- 2026-08-01：正式手册构建器封面版本同步为 V1.2，对应 Stage 10 离线 MP 快照支持。
- 2026-07-31：正式手册构建器封面版本同步为 V1.1，对应外部带隙任务/结果契约更新。
- 2026-07-22：登记完整功能版用户手册的确定性 Word 构建器。
- 2026-07-22：根据当时 1 个项目脚本和 1 个 GitHub Actions workflow 建立初始索引。
