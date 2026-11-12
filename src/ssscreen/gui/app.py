"""PySide6 desktop workbench for ``ss-screen``.

The desktop application is deliberately a GUI wrapper over the existing Click
surface rather than a second scientific implementation.  Command pages are
built from Click metadata at runtime, and jobs are executed in a subprocess via
``python -m ssscreen.cli.app``.  That keeps command validation, defaults,
scientific algorithms, output schemas, and exit codes identical between CLI and
GUI.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
import shlex
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any
from uuid import uuid4

import click

try:
    from PySide6.QtCore import QProcess, QProcessEnvironment, QSettings, QSize, Qt, QUrl, Signal
    from PySide6.QtGui import QActionGroup, QDesktopServices, QFont, QFontDatabase, QTextCursor
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFileSystemModel,
        QFormLayout,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSplitter,
        QStackedWidget,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextBrowser,
        QToolBar,
        QToolButton,
        QTreeView,
        QTreeWidget,
        QTreeWidgetItem,
        QTreeWidgetItemIterator,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - exercised only without GUI extra
    raise RuntimeError(
        'SS-Screen GUI requires PySide6. Install it with `pip install -e ".[gui]"` '
        'or `pip install "ss-screen[gui]"`.'
    ) from exc

if __package__ in {None, ""}:
    src_root = Path(__file__).resolve().parents[2]
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    from ssscreen import __version__
    from ssscreen.cli.app import cli
    from ssscreen.gui.appearance import (
        DEFAULT_FONT_SIZE,
        FONT_SETTINGS_KEY,
        MAX_FONT_SIZE,
        MIN_FONT_SIZE,
        adapt_font_layout,
        font_size,
        font_stylesheet,
    )
    from ssscreen.gui.detector_page import DetectorAssessmentPage
    from ssscreen.gui.gap_bundle_page import GapBundlePage
    from ssscreen.gui.gap_collect_page import GapCollectPage
    from ssscreen.gui.icons import app_icon, stage_icon
    from ssscreen.gui.metadata import (
        COMMANDS,
        PATH_PRESETS,
        STAGES,
        CommandPresentation,
        option_label_zh,
    )
    from ssscreen.gui.project_file import (
        create_project_file,
        extract_project_file,
        inspect_project_file,
    )
    from ssscreen.gui.relax_page import RelaxPage
    from ssscreen.gui.relax_results import manifest_rows
    from ssscreen.gui.sqs_page import SqsPage
    from ssscreen.gui.sqs_results import pair_count
    from ssscreen.gui.stability_page import STABILITY_PATHS, StabilityPage
    from ssscreen.gui.visualization import (
        MatterVizView,
        PhaseResultsPage,
        PhononResultsPage,
        StructureResultsPage,
    )
    from ssscreen.gui.wavelength_page import WavelengthPairPage
    from ssscreen.gui.workflow_project import (
        WorkflowController,
        apply_command_values,
        capture_forms,
        imported_artifact,
        mp_output_paths,
        read_project,
        restore_forms,
    )
else:
    from .. import __version__
    from ..cli.app import cli
    from .appearance import (
        DEFAULT_FONT_SIZE,
        FONT_SETTINGS_KEY,
        MAX_FONT_SIZE,
        MIN_FONT_SIZE,
        adapt_font_layout,
        font_size,
        font_stylesheet,
    )
    from .detector_page import DetectorAssessmentPage
    from .gap_bundle_page import GapBundlePage
    from .gap_collect_page import GapCollectPage
    from .icons import app_icon, stage_icon
    from .metadata import COMMANDS, PATH_PRESETS, STAGES, CommandPresentation, option_label_zh
    from .project_file import create_project_file, extract_project_file, inspect_project_file
    from .relax_page import RelaxPage
    from .relax_results import manifest_rows
    from .sqs_page import SqsPage
    from .sqs_results import pair_count
    from .stability_page import STABILITY_PATHS, StabilityPage
    from .visualization import (
        MatterVizView,
        PhaseResultsPage,
        PhononResultsPage,
        StructureResultsPage,
    )
    from .wavelength_page import WavelengthPairPage
    from .workflow_project import (
        WorkflowController,
        apply_command_values,
        capture_forms,
        imported_artifact,
        mp_output_paths,
        read_project,
        restore_forms,
    )


APP_TITLE = f"SS-Screen V{__version__} · Materials Engineering Workbench"
PROJECT_DIRS = tuple(directory for _sid, _name, directory in STAGES if directory) + (
    "logs",
    "models",
)
GUI_PACKAGE_RELATIVE_ROOT = ("src", "ssscreen", "gui")
WSL_VENV_ACTIVATE = ".venv/bin/activate"
WSL_MLP_VENV_ACTIVATE = ".venv-mlp/bin/activate"
MLP_COMMANDS = {
    ("stability", "relax"),
    ("stability", "phonon-forces"),
    ("stability", "phonon-run"),
    ("stability", "competing-relax"),
    ("stability", "phase-diagram"),
}


def _find_project_root(path: Path) -> Path:
    """Return the nearest repository/package root for a GUI launch path."""
    current = path.expanduser().resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        pyproject = candidate / "pyproject.toml"
        if (
            (candidate / ".ssscreen-project.json").exists()
            or (candidate / ".git").exists()
            or (pyproject.exists() and (candidate / "src" / "ssscreen").exists())
        ):
            return candidate
    return current


def _strip_gui_package_prefix(value: str) -> str:
    normalized = value.replace("\\", "/")
    prefix = "/".join(GUI_PACKAGE_RELATIVE_ROOT) + "/"
    if normalized.startswith(prefix):
        remainder = normalized[len(prefix) :]
        if remainder.split("/", 1)[0] in PROJECT_DIRS:
            return remainder
    return normalized


def _project_display_path(project_root: Path, path: Path) -> str:
    try:
        relative = str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)
    return _strip_gui_package_prefix(relative)


def _resolve_project_path(project_root: Path, value: str) -> Path:
    text = _strip_gui_package_prefix(value.strip())
    path = Path(text).expanduser()
    if not path.is_absolute():
        return imported_artifact(project_root, text)

    try:
        relative = path.resolve().relative_to(project_root)
    except Exception:
        return path

    normalized = _strip_gui_package_prefix(str(relative))
    return project_root / normalized


@dataclass
class RunRecord:
    """Small in-memory summary of a GUI-launched CLI process."""

    started: str
    command: str
    exit_code: int | None = None


class ValueEditor(QWidget):
    """Qt editor that can serialize one Click option back to argv tokens."""

    changed = Signal()

    def __init__(
        self,
        option: click.Option,
        preset: Any = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.option = option
        self._path_type = option.type if isinstance(option.type, click.Path) else None
        option_names = [*option.opts, *option.secondary_opts]
        self._semantic_directory = bool(
            self._path_type is not None
            and (
                (self._path_type.dir_okay and not self._path_type.file_okay)
                or option.name.endswith(("_dir", "_dirs"))
                or any(name.endswith(("-dir", "-dirs")) for name in option_names)
            )
        )
        self._default = option.get_default(click.Context(click.Command("gui")))
        if self._default is getattr(click.core, "UNSET", None):
            self._default = None
        self._preset = preset
        self._mode = "text"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        if option.is_bool_flag:
            self._mode = "bool"
            self.widget = QCheckBox()
            self.widget.setChecked(bool(self._initial_value()))
            self.widget.toggled.connect(self.changed)
            layout.addWidget(self.widget)
            layout.addStretch(1)
            return

        if isinstance(option.type, click.Choice) and not option.multiple:
            self._mode = "choice"
            self.widget = QComboBox()
            if self._default is None and not option.required:
                self.widget.addItem("")
            for choice in option.type.choices:
                self.widget.addItem(str(choice))
            value = self._initial_value()
            if value is not None:
                self.widget.setCurrentText(str(value))
            self.widget.currentTextChanged.connect(self.changed)
            layout.addWidget(self.widget, 1)
            return

        if option.multiple:
            self._mode = "multi"
            self.widget = QPlainTextEdit()
            self.widget.setMaximumHeight(82)
            self.widget.setPlaceholderText("每行一个值；运行时会重复传递该选项")
            initial = self._initial_value()
            if initial:
                if isinstance(initial, (list, tuple)):
                    self.widget.setPlainText("\n".join(str(x) for x in initial))
                else:
                    self.widget.setPlainText(str(initial))
            self.widget.textChanged.connect(self.changed)
            layout.addWidget(self.widget, 1)
            if self._path_type is not None:
                if self._path_type.file_okay:
                    file_btn = QPushButton("添加文件")
                    file_btn.clicked.connect(self._add_files)
                    layout.addWidget(file_btn)
                if self._path_type.dir_okay:
                    dir_btn = QPushButton("添加目录")
                    dir_btn.clicked.connect(self._add_directory)
                    layout.addWidget(dir_btn)
            return

        self.widget = QLineEdit()
        initial = self._initial_value()
        if initial is not None:
            self.widget.setText(str(initial))
        self.widget.textChanged.connect(self.changed)
        layout.addWidget(self.widget, 1)

        if self._path_type is not None:
            browse_btn = QPushButton("浏览…")
            browse_btn.clicked.connect(self._browse_single)
            layout.addWidget(browse_btn)

    def _initial_value(self) -> Any:
        if self._preset is not None:
            return self._preset
        return self._default

    def reset(self) -> None:
        """Restore Click default, falling back to a GUI path preset."""
        value = self._initial_value()
        if self._mode == "bool":
            self.widget.setChecked(bool(value))
        elif self._mode == "choice":
            self.widget.setCurrentText("" if value is None else str(value))
        elif self._mode == "multi":
            if value is None:
                self.widget.clear()
            elif isinstance(value, (tuple, list)):
                self.widget.setPlainText("\n".join(str(x) for x in value))
            else:
                self.widget.setPlainText(str(value))
        else:
            self.widget.setText("" if value is None else str(value))

    def set_value(self, value: Any) -> None:
        """Restore a value previously saved in a project snapshot."""

        if self._mode == "bool":
            self.widget.setChecked(bool(value))
            return

        if self._mode == "choice":
            self.widget.setCurrentText(
                "" if value is None else str(value)
            )
            return

        if self._mode == "multi":
            if value is None:
                self.widget.clear()
            elif isinstance(value, (list, tuple)):
                self.widget.setPlainText(
                    "\n".join(str(item) for item in value)
                )
            else:
                self.widget.setPlainText(str(value))
            return

        self.widget.setText(
            "" if value is None else str(value)
        )

    def _browse_single(self) -> None:
        path_type = self._path_type
        if path_type is None:
            return
        current = self.widget.text().strip() or str(Path.cwd())
        if self._semantic_directory:
            value = QFileDialog.getExistingDirectory(self, "选择目录", current)
        elif path_type.exists:
            value, _ = QFileDialog.getOpenFileName(self, "选择文件", current)
        else:
            value, _ = QFileDialog.getSaveFileName(self, "选择输出文件", current)
        if value:
            self.widget.setText(value)

    def _add_files(self) -> None:
        values, _ = QFileDialog.getOpenFileNames(self, "添加文件")
        if values:
            old = self.widget.toPlainText().strip()
            merged = ([old] if old else []) + values
            self.widget.setPlainText("\n".join(merged))

    def _add_directory(self) -> None:
        value = QFileDialog.getExistingDirectory(self, "添加目录")
        if value:
            old = self.widget.toPlainText().strip()
            self.widget.setPlainText("\n".join(([old] if old else []) + [value]))

    def is_empty(self) -> bool:
        if self._mode == "bool":
            return False
        if self._mode == "choice":
            return not self.widget.currentText().strip()
        if self._mode == "multi":
            return not self.widget.toPlainText().strip()
        return not self.widget.text().strip()

    def values(self) -> list[str]:
        if self._mode == "choice":
            value = self.widget.currentText().strip()
            return [value] if value else []
        if self._mode == "multi":
            return [line.strip() for line in self.widget.toPlainText().splitlines() if line.strip()]
        if self._mode == "text":
            value = self.widget.text().strip()
            return [value] if value else []
        return []

    def argv(self) -> list[str]:
        """Serialize this editor using the Click option's actual flag names."""
        option = self.option
        if self._mode == "bool":
            value = self.widget.isChecked()
            default = bool(self._default)
            if value == default:
                return []
            if value:
                return [option.opts[0]]
            if option.secondary_opts:
                return [option.secondary_opts[0]]
            return []

        values = self.values()
        if not values:
            return []
        flag = option.opts[0]
        out: list[str] = []
        if option.multiple:
            for value in values:
                out.extend([flag, value])
        else:
            out.extend([flag, values[0]])
        return out


class CommandPage(QWidget):
    """One generated form for one existing Click command."""

    run_requested = Signal(list, str)

    def __init__(
        self,
        presentation: CommandPresentation,
        command: click.Command,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation
        self.command = command
        self.editors: list[tuple[click.Option, ValueEditor]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(7)

        title = QLabel(presentation.title)
        title.setObjectName("pageTitle")
        root.addWidget(title)

        command_name = "ss-screen " + " ".join(presentation.command_path)
        command_label = QLabel(command_name)
        command_label.setObjectName("commandName")
        root.addWidget(command_label)

        description = QLabel(command.help or command.short_help or "")
        description.setWordWrap(True)
        description.setObjectName("pageDescription")
        root.addWidget(description)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 4, 0, 4)

        options_box = QGroupBox("Parameters / 参数")
        form = QFormLayout(options_box)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(9)

        presets = PATH_PRESETS.get(presentation.command_path, {})
        for param in command.params:
            if not isinstance(param, click.Option):
                continue
            if param.name == "help":
                continue
            preset = None
            for opt_name in param.opts:
                if opt_name in presets:
                    preset = presets[opt_name]
                    break
            editor = ValueEditor(param, preset=preset)
            editor.changed.connect(self.refresh_preview)
            self.editors.append((param, editor))

            cli_flag = param.opts[0] if param.opts else param.name
            flag_text = f"{option_label_zh(param.name)}  ({cli_flag})"
            if param.required:
                flag_text += "  *"
            label = QLabel(flag_text)
            label.setToolTip(param.help or "")
            editor.setToolTip(param.help or "")
            form.addRow(label, editor)

            if param.help:
                help_label = QLabel(param.help)
                help_label.setWordWrap(True)
                help_label.setObjectName("optionHelp")
                form.addRow("", help_label)

        body_layout.addWidget(options_box)

        advanced_box = QGroupBox("Advanced / 附加参数")
        advanced_layout = QVBoxLayout(advanced_box)
        self.extra_args = QLineEdit()
        self.extra_args.setPlaceholderText("可选：直接追加 CLI 参数，例如 --limit 1")
        self.extra_args.textChanged.connect(self.refresh_preview)
        advanced_layout.addWidget(self.extra_args)
        body_layout.addWidget(advanced_box)
        body_layout.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        preview_label = QLabel("Command Preview / 命令预览")
        preview_label.setObjectName("sectionLabel")
        root.addWidget(preview_label)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(72)
        self.preview.setObjectName("commandPreview")
        root.addWidget(self.preview)

        actions = QHBoxLayout()
        reset_btn = QPushButton("重置")
        reset_btn.setIcon(app_icon("reset"))
        reset_btn.setIconSize(QSize(16, 16))
        reset_btn.clicked.connect(self.reset)

        copy_btn = QPushButton("复制")
        copy_btn.setIcon(app_icon("copy"))
        copy_btn.setIconSize(QSize(16, 16))
        copy_btn.clicked.connect(self.copy_command)

        run_btn = QPushButton("运行任务")
        self.run_button = run_btn
        run_btn.setIcon(app_icon("run"))
        run_btn.setIconSize(QSize(16, 16))
        run_btn.setObjectName("primaryButton")
        run_btn.clicked.connect(self.emit_run)
        actions.addWidget(reset_btn)
        actions.addStretch(1)
        actions.addWidget(copy_btn)
        actions.addWidget(run_btn)
        root.addLayout(actions)

        self.refresh_preview()

    def reset(self) -> None:
        for _option, editor in self.editors:
            editor.reset()
        self.extra_args.clear()
        self.refresh_preview()

    def argv(self) -> list[str]:
        argv = list(self.presentation.command_path)
        for _option, editor in self.editors:
            argv.extend(editor.argv())
        extra = self.extra_args.text().strip()
        if extra:
            argv.extend(shlex.split(extra))
        return argv

    def restore_argv(self, argv: list[str]) -> None:
        """Restore GUI editors from a previously saved command argv."""

        saved = [str(value) for value in argv]

        # 保存时 page.argv() 包含 command_path，例如：
        #
        # ["stability", "relax", "--device", "cuda", ...]
        #
        # Click 当前 command 只需要后面的 option 参数。
        prefix = list(self.presentation.command_path)

        if saved[: len(prefix)] == prefix:
            saved = saved[len(prefix):]

        try:
            # Restore settings without requiring remote/WSL inputs to exist on
            # Windows. The real CLI still performs its normal path validation.
            restore_command = copy.copy(self.command)
            restore_command.params = [copy.copy(p) for p in self.command.params]
            for param in restore_command.params:
                # Editors need CLI text, before callbacks convert e.g. "2,2,2"
                # into a tuple that cannot be passed back to the same option.
                param.callback = None
                if isinstance(param.type, click.Path):
                    param.type = copy.copy(param.type)
                    param.type.exists = False
                    param.type.resolve_path = False
            with restore_command.make_context(
                self.command.name
                or self.presentation.command_path[-1],
                saved,
                resilient_parsing=True,
                ignore_unknown_options=True,
                allow_extra_args=True,
            ) as ctx:
                params = dict(ctx.params)
                extra_args = list(ctx.args)

        except Exception as exc:
            print(
                "Failed to restore command settings:",
                self.presentation.command_path,
                exc,
                flush=True,
            )
            return

        for option, editor in self.editors:
            if option.name in params:
                editor.set_value(params[option.name])
            else:
                editor.reset()

        # 当前 GUI 还有一个“附加参数”输入框。
        # Click 不认识的参数重新放回这里。
        if extra_args:
            self.extra_args.setText(
                shlex.join(extra_args)
            )
        else:
            self.extra_args.clear()

        self.refresh_preview()

    def missing_required(self) -> list[str]:
        missing = []
        for option, editor in self.editors:
            if option.required and editor.is_empty():
                missing.append(option.opts[0] if option.opts else option.name)
        return missing

    def refresh_preview(self) -> None:
        try:
            text = shlex.join(["ss-screen", *self.argv()])
        except ValueError as exc:
            text = f"参数解析错误：{exc}"
        self.preview.setPlainText(text)

    def copy_command(self) -> None:
        QApplication.clipboard().setText(self.preview.toPlainText())

    def emit_run(self) -> None:
        missing = self.missing_required()
        if missing:
            QMessageBox.warning(
                self,
                "缺少必填参数",
                "请先填写以下参数：\n" + "\n".join(f"• {x}" for x in missing),
            )
            return
        try:
            argv = self.argv()
        except ValueError as exc:
            QMessageBox.warning(self, "附加参数错误", str(exc))
            return
        self.run_requested.emit(argv, self.presentation.title)


def _wrap_in_scroll_area(
    content: QWidget,
    *,
    min_width: int = 760,
    min_height: int = 620,
) -> QScrollArea:
    """Keep engineering forms readable instead of letting Qt squash them.

    On smaller screens or Windows display scaling, the content keeps its
    natural minimum size and the tab becomes scrollable.
    """
    content.setMinimumWidth(min_width)
    content.setMinimumHeight(min_height)
    content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll.setWidget(content)
    return scroll


class DatasetSourcePage(QWidget):
    """Engineering GUI for Stage 01 external data sources.

    Materials Project and WBM are represented as external sources.  Their
    normalized local DataFrame outputs are the project objects consumed by
    later SS-Screen stages.
    """

    run_requested = Signal(list, str)

    def __init__(self, project_provider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_provider = project_provider

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(7)

        header = QHBoxLayout()
        title = QLabel("数据源 / Data Sources")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        badge = QLabel("Stage 01")
        badge.setObjectName("stateBadge")
        header.addWidget(badge)
        root.addLayout(header)

        subtitle = QLabel(
            "Materials Project 和 WBM 在这里作为外部材料数据源管理。"
            "SS-Screen 获取或导入数据后，将其规范化为本地 DataFrame；"
            "后续组成模板筛选、结构描述和结构匹配使用这些本地数据。"
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("pageDescription")
        root.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMinimumHeight(520)
        self.tabs.addTab(self._build_mp_tab(), "Materials Project")
        self.tabs.addTab(self._build_wbm_tab(), "WBM Dataset")
        self.tabs.addTab(self._build_structures_tab(), "Local POSCAR / 本地结构")
        self.tabs.addTab(self._build_local_tab(), "Local Datasets / 本地数据")
        root.addWidget(self.tabs, 1)

        boundary = QGroupBox("Data Boundary / 数据边界")
        boundary_layout = QVBoxLayout(boundary)
        boundary_layout.setContentsMargins(8, 8, 8, 8)
        note = QLabel(
            "外部数据源负责提供初始材料记录；SS-Screen 负责数据获取、规范化、"
            "本地保存和后续筛选。Materials Project 的 API Key 仅通过右侧 Properties "
            "中的 Connection 设置注入当前任务进程，不写入项目输出文件。"
        )
        note.setWordWrap(True)
        note.setObjectName("optionHelp")
        boundary_layout.addWidget(note)
        root.addWidget(boundary)

        self.refresh_sources()
        self._refresh_mp_preview()
        self._refresh_wbm_preview()
        self._refresh_structures_preview()

    # ------------------------------------------------------------------
    # Common helpers
    # ------------------------------------------------------------------

    def _project_root(self) -> Path:
        return Path(self.project_provider()).expanduser().resolve()

    def _resolve(self, text: str) -> Path:
        return _resolve_project_path(self._project_root(), text)

    def _display_path(self, path: Path) -> str:
        return _project_display_path(self._project_root(), path)

    def _path_editor(
        self,
        default: str,
        *,
        directory: bool = False,
        save_file: bool = False,
    ) -> tuple[QWidget, QLineEdit]:
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        edit = QLineEdit(default)
        browse = QPushButton("…")
        browse.setMaximumWidth(34)

        def choose() -> None:
            base = str(self._project_root())
            if directory:
                value = QFileDialog.getExistingDirectory(
                    self,
                    "选择目录",
                    base,
                )
            elif save_file:
                value, _ = QFileDialog.getSaveFileName(
                    self,
                    "选择输出文件",
                    base,
                )
            else:
                value, _ = QFileDialog.getOpenFileName(
                    self,
                    "选择文件",
                    base,
                )
            if value:
                edit.setText(self._display_path(Path(value)))
                edit.textEdited.emit(edit.text())

        browse.clicked.connect(choose)
        row.addWidget(edit, 1)
        row.addWidget(browse)
        return host, edit

    def _format_size(self, path: Path) -> str:
        try:
            size = path.stat().st_size
        except OSError:
            return "—"
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / 1024 / 1024:.1f} MB"

    # ------------------------------------------------------------------
    # Materials Project
    # ------------------------------------------------------------------

    def _build_mp_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(7)

        identity = QGroupBox("Source Identity / 数据源说明")
        identity_form = QFormLayout(identity)
        identity_form.setLabelAlignment(Qt.AlignRight | Qt.AlignTop)
        identity_form.setHorizontalSpacing(12)
        identity_form.setVerticalSpacing(7)

        source_type = QLabel("External materials database / 外部材料数据库")
        source_use = QLabel(
            "用于获取初始材料结构与筛选所需数据库字段；离线导入默认将输出保存到输入数据库所在目录。"
        )
        source_use.setWordWrap(True)
        source_flow = QLabel(
            "Materials Project → SS-Screen 数据获取/规范化 → 输出栏中的 mp.df → 组成模板筛选"
        )
        source_flow.setWordWrap(True)

        identity_form.addRow("类型", source_type)
        identity_form.addRow("在 SS-Screen 中的作用", source_use)
        identity_form.addRow("数据流", source_flow)
        layout.addWidget(identity)

        columns = QHBoxLayout()
        columns.setSpacing(16)
        self.mp_input_box = QGroupBox("输入栏 / Inputs")
        self.mp_input_box.setObjectName("mpInputColumn")
        input_layout = QVBoxLayout(self.mp_input_box)
        input_note = QLabel("提供已有的材料数据库，并设置本次读取的筛选条件。")
        input_note.setWordWrap(True)
        input_layout.addWidget(input_note)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        input_layout.addLayout(form)

        self.mp_backend = QComboBox()
        self.mp_backend.addItem("API / 在线接口", "api")
        self.mp_backend.addItem("Offline / 离线数据库", "offline")
        form.addRow("数据模式", self.mp_backend)

        offline_host, self.mp_offline_db = self._path_editor("")
        form.addRow("输入数据库文件", offline_host)

        self.mp_max_e_hull = QLineEdit("0.01")
        self.mp_max_e_hull.setMaximumWidth(180)
        form.addRow("最大凸包距离 (eV/atom)", self.mp_max_e_hull)

        api_note = QLabel("离线模式无需 API Key；在线模式请在右侧连接设置填写 MP API Key。")
        api_note.setWordWrap(True)
        api_note.setObjectName("optionHelp")
        form.addRow("在线凭据", api_note)
        input_layout.addStretch(1)
        columns.addWidget(self.mp_input_box, 1)

        self.mp_output_box = QGroupBox("输出栏 / Outputs")
        self.mp_output_box.setObjectName("mpOutputColumn")
        output_layout = QVBoxLayout(self.mp_output_box)
        output_note = QLabel(
            "以下文件由程序运行后生成。离线模式默认与输入数据库同目录；"
            "显示的相对路径以当前工程目录为基准。"
        )
        output_note.setWordWrap(True)
        output_layout.addWidget(output_note)
        self.mp_output_follow_input = QCheckBox("输出位置跟随输入数据库目录")
        self.mp_output_follow_input.setChecked(True)
        self.mp_output_follow_input.setToolTip(
            "更换输入数据库时自动更新两个输出路径。手动修改输出路径后取消跟随；勾选可恢复默认。"
        )
        output_layout.addWidget(self.mp_output_follow_input)
        output_form = QFormLayout()
        output_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        output_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        output_form.setHorizontalSpacing(12)
        output_form.setVerticalSpacing(8)
        output_layout.addLayout(output_form)

        host, self.mp_output = self._path_editor(
            "01_dataset/mp.df",
            save_file=True,
        )
        self.mp_output.setToolTip("输出文件：标准化材料数据，供后续组成模板筛选使用。")
        output_form.addRow("标准化材料数据文件", host)

        host, self.mp_provenance = self._path_editor(
            "01_dataset/mp.df.provenance.json",
            save_file=True,
        )
        self.mp_provenance.setToolTip("输出文件：记录数据库来源、筛选条件、数量和版本，供追溯核验。")
        output_form.addRow("来源记录文件", host)

        result = QGroupBox("输出文件生成状态")
        result_form = QFormLayout(result)
        result_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.mp_status = QLabel("未生成")
        self.mp_size = QLabel("—")
        self.mp_provenance_status = QLabel("未生成")
        result_form.addRow("材料数据", self.mp_status)
        result_form.addRow("文件大小", self.mp_size)
        result_form.addRow("来源记录", self.mp_provenance_status)
        output_layout.addWidget(result)
        output_layout.addStretch(1)
        columns.addWidget(self.mp_output_box, 1)
        layout.addLayout(columns)

        preview_label = QLabel("Command Preview / 命令预览")
        preview_label.setObjectName("sectionLabel")
        layout.addWidget(preview_label)

        self.mp_preview = QPlainTextEdit()
        self.mp_preview.setReadOnly(True)
        self.mp_preview.setMaximumHeight(82)
        self.mp_preview.setObjectName("commandPreview")
        layout.addWidget(self.mp_preview)

        actions = QHBoxLayout()
        refresh = QPushButton("检查输出文件")
        refresh.clicked.connect(self.refresh_sources)
        copy = QPushButton("复制命令")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.mp_preview.toPlainText()))
        run = QPushButton("获取 Materials Project 数据")
        run.setObjectName("primaryButton")
        run.setToolTip("读取输入栏中的数据库，按筛选条件生成输出栏中的两个文件。")
        run.clicked.connect(self._run_mp)
        actions.addWidget(refresh)
        actions.addStretch(1)
        actions.addWidget(copy)
        actions.addWidget(run)
        layout.addLayout(actions)
        layout.addStretch(1)

        self.mp_backend.currentIndexChanged.connect(self._mp_backend_changed)
        self.mp_offline_db.textChanged.connect(self._sync_mp_output_paths)
        self.mp_output_follow_input.toggled.connect(self._sync_mp_output_paths)
        self.mp_output.textEdited.connect(self._mp_manual_output)
        self.mp_provenance.textEdited.connect(self._mp_manual_output)
        for editor in (
            self.mp_offline_db,
            self.mp_max_e_hull,
            self.mp_output,
            self.mp_provenance,
        ):
            editor.textChanged.connect(self._refresh_mp_preview)

        self._mp_backend_changed()
        return _wrap_in_scroll_area(page, min_width=840, min_height=680)

    def _mp_backend_changed(self) -> None:
        offline = self.mp_backend.currentData() == "offline"
        self.mp_offline_db.setEnabled(offline)
        self._sync_mp_output_paths()
        self._refresh_mp_preview()

    def _mp_manual_output(self) -> None:
        self.mp_output_follow_input.setChecked(False)

    def _sync_mp_output_paths(self) -> None:
        if getattr(self, "_restoring_mp_settings", False):
            return
        if self.mp_output_follow_input.isChecked():
            database = self.mp_offline_db.text() if self.mp_backend.currentData() == "offline" else ""
            output, provenance = mp_output_paths(self._project_root(), database)
            self.mp_output.setText(output)
            self.mp_provenance.setText(provenance)
        self._refresh_mp_preview()
        self.refresh_sources()

    def _mp_argv(self) -> list[str]:
        argv = [
            "dataset",
            "mp",
            "--backend",
            str(self.mp_backend.currentData()),
        ]
        if self.mp_backend.currentData() == "offline" and self.mp_offline_db.text().strip():
            argv.extend(
                [
                    "--offline-db",
                    self.mp_offline_db.text().strip(),
                ]
            )

        argv.extend(
            [
                "--max-e-hull",
                self.mp_max_e_hull.text().strip() or "0.01",
                "--output",
                self.mp_output.text().strip(),
                "--provenance",
                self.mp_provenance.text().strip(),
            ]
        )
        return argv

    def _refresh_mp_preview(self) -> None:
        if hasattr(self, "mp_preview"):
            self.mp_preview.setPlainText(shlex.join(["ss-screen", *self._mp_argv()]))

    def _run_mp(self) -> None:
        if not self.mp_output.text().strip():
            QMessageBox.warning(
                self,
                "缺少输出路径",
                "请设置 Materials Project 本地 DataFrame 输出路径。",
            )
            return
        if self.mp_backend.currentData() == "offline" and not self.mp_offline_db.text().strip():
            QMessageBox.warning(
                self,
                "缺少离线数据库",
                "Offline 模式需要选择离线数据库文件。",
            )
            return
        try:
            if float(self.mp_max_e_hull.text().strip()) < 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(
                self,
                "参数错误",
                "最大凸包距离必须是非负数字。",
            )
            return

        self.run_requested.emit(
            self._mp_argv(),
            "Materials Project 数据获取",
        )

    # ------------------------------------------------------------------
    # WBM
    # ------------------------------------------------------------------

    def _build_wbm_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(7)

        identity = QGroupBox("Source Identity / 数据源说明")
        identity_layout = QVBoxLayout(identity)
        intro = QLabel(
            "WBM Dataset 作为另一个规范化材料数据源，与 Materials Project "
            "数据可以在 composition-screen 阶段通过重复 --df 一起参与筛选。"
        )
        intro.setWordWrap(True)
        identity_layout.addWidget(intro)
        layout.addWidget(identity)

        acquire = QGroupBox("WBM Data / 数据获取")
        form = QFormLayout(acquire)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        host, self.wbm_xyz = self._path_editor("")
        form.addRow("WBM extxyz", host)

        host, self.wbm_summary = self._path_editor("")
        form.addRow("Summary CSV/TSV", host)

        host, self.wbm_output = self._path_editor(
            "01_dataset/wbm.df",
            save_file=True,
        )
        form.addRow("本地标准化数据", host)
        layout.addWidget(acquire)

        result = QGroupBox("Local Result / 本地结果")
        result_form = QFormLayout(result)
        result_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.wbm_status = QLabel("未生成")
        self.wbm_size = QLabel("—")
        result_form.addRow("wbm.df", self.wbm_status)
        result_form.addRow("文件大小", self.wbm_size)
        layout.addWidget(result)

        self.wbm_preview = QPlainTextEdit()
        self.wbm_preview.setReadOnly(True)
        self.wbm_preview.setMaximumHeight(75)
        self.wbm_preview.setObjectName("commandPreview")
        layout.addWidget(QLabel("Command Preview / 命令预览"))
        layout.addWidget(self.wbm_preview)

        actions = QHBoxLayout()
        refresh = QPushButton("检查本地结果")
        refresh.clicked.connect(self.refresh_sources)
        copy = QPushButton("复制命令")
        copy.clicked.connect(
            lambda: QApplication.clipboard().setText(self.wbm_preview.toPlainText())
        )
        run = QPushButton("获取 WBM 数据")
        run.setObjectName("primaryButton")
        run.clicked.connect(self._run_wbm)
        actions.addWidget(refresh)
        actions.addStretch(1)
        actions.addWidget(copy)
        actions.addWidget(run)
        layout.addLayout(actions)
        layout.addStretch(1)

        for editor in (self.wbm_xyz, self.wbm_summary, self.wbm_output):
            editor.textChanged.connect(self._refresh_wbm_preview)

        return _wrap_in_scroll_area(page, min_width=840, min_height=560)

    def _wbm_argv(self) -> list[str]:
        argv = [
            "dataset",
            "wbm",
            "--xyz",
            self.wbm_xyz.text().strip(),
            "--output",
            self.wbm_output.text().strip(),
        ]
        if self.wbm_summary.text().strip():
            argv.extend(["--summary", self.wbm_summary.text().strip()])
        return argv

    def _refresh_wbm_preview(self) -> None:
        if hasattr(self, "wbm_preview"):
            self.wbm_preview.setPlainText(shlex.join(["ss-screen", *self._wbm_argv()]))

    def _run_wbm(self) -> None:
        if not self.wbm_xyz.text().strip():
            QMessageBox.warning(
                self,
                "缺少 WBM 文件",
                "请先选择 WBM extxyz 输入文件。",
            )
            return
        if not self.wbm_output.text().strip():
            QMessageBox.warning(
                self,
                "缺少输出路径",
                "请设置 WBM 本地 DataFrame 输出路径。",
            )
            return
        self.run_requested.emit(
            self._wbm_argv(),
            "WBM 数据获取",
        )

    # ------------------------------------------------------------------
    # Local structure folder
    # ------------------------------------------------------------------

    def _build_structures_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(7)

        identity = QGroupBox("Local Structures / 本地结构输入")
        identity_layout = QVBoxLayout(identity)
        intro = QLabel(
            "把本地 POSCAR/CIF/vasp/json 结构文件夹导入为标准 DataFrame。"
            "该入口适合小批量结构作为 Stage 01 初筛数据；"
        )
        intro.setWordWrap(True)
        identity_layout.addWidget(intro)
        layout.addWidget(identity)

        input_box = QGroupBox("Input / 输入")
        form = QFormLayout(input_box)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        host, self.structures_input_dir = self._path_editor(
            "data/CaS_CaSe_CaTe_PBE_relaxed_CONTCAR",
            directory=True,
        )
        form.addRow("结构文件夹", host)

        host, self.structures_metadata = self._path_editor("")
        form.addRow("Metadata CSV/TSV", host)

        self.structures_gap_default = QLineEdit("0.0")
        self.structures_gap_default.setMaximumWidth(180)
        form.addRow("默认 band gap", self.structures_gap_default)

        self.structures_hull_default = QLineEdit("0.0")
        self.structures_hull_default.setMaximumWidth(180)
        form.addRow("默认 e_hull", self.structures_hull_default)

        self.structures_source = QLineEdit("pbe-vasp-relaxed")
        form.addRow("数据源标签", self.structures_source)
        layout.addWidget(input_box)

        output_box = QGroupBox("Output / 输出")
        out_form = QFormLayout(output_box)
        out_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        out_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        host, self.structures_output = self._path_editor(
            "01_dataset/local_structures.df",
            save_file=True,
        )
        out_form.addRow("本地标准化数据", host)

        host, self.structures_provenance = self._path_editor(
            "01_dataset/local_structures.provenance.json",
            save_file=True,
        )
        out_form.addRow("Provenance / 来源记录", host)
        layout.addWidget(output_box)

        self.structures_preview = QPlainTextEdit()
        self.structures_preview.setReadOnly(True)
        self.structures_preview.setMaximumHeight(82)
        self.structures_preview.setObjectName("commandPreview")
        layout.addWidget(QLabel("Command Preview / 命令预览"))
        layout.addWidget(self.structures_preview)

        actions = QHBoxLayout()
        refresh = QPushButton("检查本地结果")
        refresh.clicked.connect(self.refresh_sources)
        copy = QPushButton("复制命令")
        copy.clicked.connect(
            lambda: QApplication.clipboard().setText(self.structures_preview.toPlainText())
        )
        run = QPushButton("导入本地结构")
        run.setObjectName("primaryButton")
        run.clicked.connect(self._run_structures)
        actions.addWidget(refresh)
        actions.addStretch(1)
        actions.addWidget(copy)
        actions.addWidget(run)
        layout.addLayout(actions)
        layout.addStretch(1)

        for editor in (
            self.structures_input_dir,
            self.structures_metadata,
            self.structures_gap_default,
            self.structures_hull_default,
            self.structures_source,
            self.structures_output,
            self.structures_provenance,
        ):
            editor.textChanged.connect(self._refresh_structures_preview)

        return _wrap_in_scroll_area(page, min_width=840, min_height=650)

    def _structures_argv(self) -> list[str]:
        argv = [
            "dataset",
            "structures",
            "--input-dir",
            self.structures_input_dir.text().strip(),
            "--band-gap-default",
            self.structures_gap_default.text().strip() or "0.0",
            "--e-hull-default",
            self.structures_hull_default.text().strip() or "0.0",
            "--source",
            self.structures_source.text().strip() or "local-structures",
            "--output",
            self.structures_output.text().strip(),
            "--provenance",
            self.structures_provenance.text().strip(),
        ]
        if self.structures_metadata.text().strip():
            argv.extend(["--metadata", self.structures_metadata.text().strip()])
        return argv

    def _refresh_structures_preview(self) -> None:
        if hasattr(self, "structures_preview"):
            self.structures_preview.setPlainText(
                shlex.join(["ss-screen", *self._structures_argv()])
            )

    def _run_structures(self) -> None:
        if not self.structures_input_dir.text().strip():
            QMessageBox.warning(self, "缺少输入目录", "请先选择 POSCAR/CIF 结构文件夹。")
            return
        if not self.structures_output.text().strip():
            QMessageBox.warning(self, "缺少输出路径", "请设置本地 DataFrame 输出路径。")
            return
        self.run_requested.emit(self._structures_argv(), "本地 POSCAR 结构导入")

    # ------------------------------------------------------------------
    # Local project data
    # ------------------------------------------------------------------

    def _build_local_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(7)

        local_box = QGroupBox("Normalized Local Datasets / 项目本地数据")
        local_layout = QVBoxLayout(local_box)

        self.local_table = QTableWidget(0, 5)
        self.local_table.setHorizontalHeaderLabels(
            ["Data Source", "Local DataFrame", "状态", "大小", "下游用途"]
        )
        self.local_table.verticalHeader().setVisible(False)
        self.local_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.local_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.local_table.horizontalHeader().setStretchLastSection(True)
        self.local_table.setColumnWidth(0, 180)
        self.local_table.setColumnWidth(1, 310)
        self.local_table.setColumnWidth(2, 90)
        self.local_table.setColumnWidth(3, 90)
        self.local_table.setMinimumHeight(150)
        local_layout.addWidget(self.local_table)
        layout.addWidget(local_box)

        provenance_box = QGroupBox("Materials Project Provenance / 来源记录")
        provenance_layout = QVBoxLayout(provenance_box)
        self.provenance_table = QTableWidget(0, 2)
        self.provenance_table.setHorizontalHeaderLabels(["字段", "值"])
        self.provenance_table.verticalHeader().setVisible(False)
        self.provenance_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.provenance_table.horizontalHeader().setStretchLastSection(True)
        self.provenance_table.setMinimumHeight(220)
        provenance_layout.addWidget(self.provenance_table)
        layout.addWidget(provenance_box, 1)

        downstream = QGroupBox("Downstream / 下游连接")
        downstream_layout = QVBoxLayout(downstream)
        downstream_note = QLabel(
            "组成模板筛选可以重复提供 --df，因此 mp.df、wbm.df 或其他规范化 "
            "DataFrame 可以组合使用。Stage 01 的输出是数据对象，Stage 02 才开始组成模板筛选。"
        )
        downstream_note.setWordWrap(True)
        downstream_layout.addWidget(downstream_note)
        layout.addWidget(downstream)

        actions = QHBoxLayout()
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self.refresh_sources)
        open_dir = QPushButton("打开 01_dataset")
        open_dir.clicked.connect(self._open_dataset_dir)
        actions.addWidget(refresh)
        actions.addWidget(open_dir)
        actions.addStretch(1)
        layout.addLayout(actions)

        return _wrap_in_scroll_area(page, min_width=880, min_height=650)

    def refresh_sources(self) -> None:
        if not hasattr(self, "local_table"):
            return

        mp_path = self._resolve(self.mp_output.text())
        wbm_path = self._resolve(self.wbm_output.text())
        structures_path = self._resolve(self.structures_output.text())
        provenance_path = self._resolve(self.mp_provenance.text())

        self.mp_status.setText(
            "Ready · " + self._display_path(mp_path) if mp_path.exists() else "未生成"
        )
        self.mp_size.setText(self._format_size(mp_path))
        self.mp_provenance_status.setText(
            "Ready · " + self._display_path(provenance_path)
            if provenance_path.exists()
            else "未生成"
        )
        self.wbm_status.setText(
            "Ready · " + self._display_path(wbm_path) if wbm_path.exists() else "未生成"
        )
        self.wbm_size.setText(self._format_size(wbm_path))

        records = [
            (
                "Materials Project",
                mp_path,
                "Ready" if mp_path.exists() else "未生成",
                self._format_size(mp_path),
                "组成模板筛选 / 结构描述",
            ),
            (
                "WBM Dataset",
                wbm_path,
                "Ready" if wbm_path.exists() else "未生成",
                self._format_size(wbm_path),
                "组成模板筛选",
            ),
            (
                "Local POSCAR",
                structures_path,
                "Ready" if structures_path.exists() else "未生成",
                self._format_size(structures_path),
                "组成模板筛选 / 结构描述",
            ),
        ]
        self.local_table.setRowCount(len(records))
        for row, record in enumerate(records):
            for col, value in enumerate(record):
                if isinstance(value, Path):
                    display = self._display_path(value)
                else:
                    display = str(value)
                self.local_table.setItem(
                    row,
                    col,
                    QTableWidgetItem(display),
                )

        self.provenance_table.setRowCount(0)
        if provenance_path.exists():
            try:
                with provenance_path.open(
                    "r",
                    encoding="utf-8",
                ) as handle:
                    data = json.load(handle)
                if isinstance(data, dict):
                    for key, value in data.items():
                        row = self.provenance_table.rowCount()
                        self.provenance_table.insertRow(row)
                        self.provenance_table.setItem(
                            row,
                            0,
                            QTableWidgetItem(str(key)),
                        )
                        if isinstance(value, (dict, list)):
                            display = json.dumps(
                                value,
                                ensure_ascii=False,
                                sort_keys=True,
                            )
                        else:
                            display = str(value)
                        self.provenance_table.setItem(
                            row,
                            1,
                            QTableWidgetItem(display),
                        )
            except Exception as exc:
                self.provenance_table.insertRow(0)
                self.provenance_table.setItem(
                    0,
                    0,
                    QTableWidgetItem("读取失败"),
                )
                self.provenance_table.setItem(
                    0,
                    1,
                    QTableWidgetItem(str(exc)),
                )

        self._refresh_mp_preview()
        self._refresh_wbm_preview()
        self._refresh_structures_preview()

    def _open_dataset_dir(self) -> None:
        path = self._project_root() / "01_dataset"
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def select_section(self, section: str) -> None:
        if section in {"mp", "mp_fetch"}:
            self.tabs.setCurrentIndex(0)
        elif section in {"wbm", "wbm_fetch"}:
            self.tabs.setCurrentIndex(1)
        elif section in {"structures", "local_structures"}:
            self.tabs.setCurrentIndex(2)
        else:
            self.tabs.setCurrentIndex(3)
        self.refresh_sources()


class CompositionScreenPage(QWidget):
    """Engineering GUI for composition template screening.

    This page maps directly to ``ss-screen composition-screen`` while treating
    the candidate CSV, screening summary and deduplicated structures as results.
    """

    run_requested = Signal(list, str)

    def __init__(self, project_provider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_provider = project_provider
        self._candidate_records: list[dict[str, str]] = []
        self._candidate_fields: list[str] = []
        self._template_field: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(7)

        header = QHBoxLayout()
        title = QLabel("组成模板筛选")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        badge = QLabel("Stage 02")
        badge.setObjectName("stateBadge")
        header.addWidget(badge)
        root.addLayout(header)

        subtitle = QLabel(
            "合并一个或多个规范化材料 DataFrame，可选使用价态过滤结果，"
            "再按照元素数、初筛带隙、凸包距离和组成模板条件筛选候选材料。"
            "输出候选材料表、筛选统计，以及供 03 使用的候选结构 candidates.df。"
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("pageDescription")
        root.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMinimumHeight(520)
        self.tabs.addTab(self._build_setup_tab(), "筛选设置与执行")
        self.tabs.addTab(self._build_results_tab(), "筛选结果")
        root.addWidget(self.tabs, 1)

        boundary = QGroupBox("Stage Output / 本阶段输出")
        boundary_layout = QVBoxLayout(boundary)
        boundary_layout.setContentsMargins(8, 8, 8, 8)
        text = QLabel(
            "候选材料表 CSV 用于 04 结构匹配；筛选统计 JSON 记录各元素数的结果；"
            "候选结构 candidates.df 按材料 ID 去重、保留原结构，默认传给 03 批量生成结构描述。"
        )
        text.setWordWrap(True)
        text.setObjectName("optionHelp")
        boundary_layout.addWidget(text)
        root.addWidget(boundary)

        self.refresh_inputs()
        self.refresh_results()
        self._refresh_preview()

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _project_root(self) -> Path:
        return Path(self.project_provider()).expanduser().resolve()

    def _display_path(self, path: Path) -> str:
        return _project_display_path(self._project_root(), path)

    def _resolve(self, text: str) -> Path:
        return _resolve_project_path(self._project_root(), text)

    def _path_editor(
        self,
        default: str,
        *,
        save_file: bool = False,
    ) -> tuple[QWidget, QLineEdit]:
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        edit = QLineEdit(default)
        button = QPushButton("…")
        button.setMaximumWidth(34)

        def browse() -> None:
            base = str(self._project_root())
            if save_file:
                value, _ = QFileDialog.getSaveFileName(
                    self,
                    "选择输出文件",
                    base,
                )
            else:
                value, _ = QFileDialog.getOpenFileName(
                    self,
                    "选择文件",
                    base,
                )
            if value:
                edit.setText(self._display_path(Path(value)))

        button.clicked.connect(browse)
        row.addWidget(edit, 1)
        row.addWidget(button)
        return host, edit

    def _check_required(self, items: list[tuple[str, str]]) -> bool:
        missing = [name for name, value in items if not str(value).strip()]
        if not missing:
            return True
        QMessageBox.warning(
            self,
            "缺少必要输入",
            "请先填写：\n" + "\n".join(f"• {name}" for name in missing),
        )
        return False

    # ------------------------------------------------------------------
    # Setup / execution
    # ------------------------------------------------------------------

    def _build_setup_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(7)

        input_box = QGroupBox("输入栏 / Inputs — 规范化数据")
        columns = QHBoxLayout()
        input_column = QVBoxLayout()
        columns.addLayout(input_column, 1)
        layout.addLayout(columns)
        input_layout = QVBoxLayout(input_box)
        input_layout.setContentsMargins(8, 10, 8, 8)

        self.df_table = QTableWidget(0, 2)
        self.df_table.setHorizontalHeaderLabels(["DataFrame", "状态"])
        self.df_table.verticalHeader().setVisible(False)
        self.df_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.df_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.df_table.horizontalHeader().setStretchLastSection(True)
        self.df_table.setColumnWidth(0, 560)
        self.df_table.setMinimumHeight(110)
        self.df_table.setMaximumHeight(165)
        input_layout.addWidget(self.df_table)

        df_actions = QHBoxLayout()
        add_df = QPushButton("＋ 添加 DataFrame")
        add_df.clicked.connect(self._add_dataframe)
        remove_df = QPushButton("移除所选")
        remove_df.clicked.connect(self._remove_dataframes)
        defaults_df = QPushButton("MP + WBM 默认")
        defaults_df.clicked.connect(self._reset_dataframes)
        check_df = QPushButton("检查输入")
        check_df.clicked.connect(self.refresh_inputs)
        df_actions.addWidget(add_df)
        df_actions.addWidget(remove_df)
        df_actions.addWidget(defaults_df)
        df_actions.addStretch(1)
        df_actions.addWidget(check_df)
        input_layout.addLayout(df_actions)

        valence_host = QWidget()
        valence_layout = QHBoxLayout(valence_host)
        valence_layout.setContentsMargins(0, 0, 0, 0)
        valence_layout.setSpacing(6)

        self.use_valence = QCheckBox("使用价态过滤结果（可选）")
        self.valence_edit = QLineEdit("02_composition/valid_ids.json")
        valence_browse = QPushButton("…")
        valence_browse.setMaximumWidth(34)

        def browse_valence() -> None:
            value, _ = QFileDialog.getOpenFileName(
                self,
                "选择 valid_ids.json",
                str(self._project_root()),
                "JSON (*.json);;All files (*)",
            )
            if value:
                self.valence_edit.setText(self._display_path(Path(value)))

        valence_browse.clicked.connect(browse_valence)
        self.use_valence.toggled.connect(self.valence_edit.setEnabled)
        self.use_valence.toggled.connect(valence_browse.setEnabled)
        valence_layout.addWidget(self.use_valence)
        valence_layout.addWidget(self.valence_edit, 1)
        valence_layout.addWidget(valence_browse)

        input_layout.addWidget(valence_host)
        input_column.addWidget(input_box)

        rules_box = QGroupBox("Screening Rules / 筛选规则")
        rules = QFormLayout(rules_box)
        rules.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        rules.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        rules.setHorizontalSpacing(12)
        rules.setVerticalSpacing(7)

        self.binary_enabled = QCheckBox("二元（2 种元素）")
        self.ternary_enabled = QCheckBox("三元（3 种元素）")
        self.binary_enabled.setChecked(True)
        self.ternary_enabled.setChecked(True)
        element_host = QWidget()
        element_layout = QHBoxLayout(element_host)
        element_layout.setContentsMargins(0, 0, 0, 0)
        element_layout.addWidget(self.binary_enabled)
        element_layout.addWidget(self.ternary_enabled)
        element_layout.addStretch(1)
        self.max_bandgap_edit = QLineEdit("1.0")
        self.max_e_hull_edit = QLineEdit("0.01")
        self.min_group_size_edit = QLineEdit("2")
        self.min_x_elements_edit = QLineEdit("2")

        for edit in (
            self.max_bandgap_edit,
            self.max_e_hull_edit,
            self.min_group_size_edit,
            self.min_x_elements_edit,
        ):
            edit.setMaximumWidth(180)

        rules.addRow("元素数量（可多选）", element_host)
        rules.addRow("最大初筛带隙 (eV)", self.max_bandgap_edit)
        rules.addRow("最大凸包距离 (eV/atom)", self.max_e_hull_edit)
        rules.addRow("模板最少材料数", self.min_group_size_edit)
        rules.addRow("模板最少可替换元素数", self.min_x_elements_edit)

        rules_note = QLabel(
            "流程：合并规范化 DataFrame → 可选价态过滤 → 元素数筛选 → "
            "带隙/e_hull 筛选 → 按组成模板分组 → 检查组大小与 X 元素数量。"
        )
        rules_note.setWordWrap(True)
        rules_note.setObjectName("optionHelp")
        rules.addRow("", rules_note)
        input_column.addWidget(rules_box)

        output_box = QGroupBox("输出栏 / Outputs — 运行后生成")
        outputs = QFormLayout(output_box)
        outputs.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        outputs.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        outputs.setHorizontalSpacing(12)
        outputs.setVerticalSpacing(7)

        host, self.candidates_output = self._path_editor(
            "02_composition/composition_candidates.csv",
            save_file=True,
        )
        outputs.addRow("候选材料表", host)

        host, self.summary_output = self._path_editor(
            "02_composition/composition_summary.json",
            save_file=True,
        )
        outputs.addRow("筛选统计", host)
        host, self.structures_output = self._path_editor(
            "02_composition/candidates.df",
            save_file=True,
        )
        outputs.addRow("候选结构（供 03 输入）", host)
        note = QLabel("以上三个文件均由本步运行生成。候选结构按材料 ID 去重，供 03 直接读取。")
        note.setWordWrap(True)
        outputs.addRow(note)
        columns.addWidget(output_box, 1)

        preview_label = QLabel("Command Preview / 命令预览")
        preview_label.setObjectName("sectionLabel")
        layout.addWidget(preview_label)

        self.command_preview = QPlainTextEdit()
        self.command_preview.setReadOnly(True)
        self.command_preview.setMaximumHeight(82)
        self.command_preview.setObjectName("commandPreview")
        layout.addWidget(self.command_preview)

        actions = QHBoxLayout()
        refresh_button = QPushButton("刷新参数")
        refresh_button.clicked.connect(self._refresh_preview)
        copy_button = QPushButton("复制命令")
        copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.command_preview.toPlainText())
        )
        run_button = QPushButton("开始组成模板筛选")
        run_button.setObjectName("primaryButton")
        run_button.clicked.connect(self._run_screen)

        actions.addWidget(refresh_button)
        actions.addStretch(1)
        actions.addWidget(copy_button)
        actions.addWidget(run_button)
        layout.addLayout(actions)
        layout.addStretch(1)

        # Defaults from the documented example.
        self._reset_dataframes(initial=True)

        for edit in (
            self.valence_edit,
            self.max_bandgap_edit,
            self.max_e_hull_edit,
            self.min_group_size_edit,
            self.min_x_elements_edit,
            self.candidates_output,
            self.summary_output,
            self.structures_output,
        ):
            edit.textChanged.connect(self._refresh_preview)
        self.use_valence.toggled.connect(self._refresh_preview)
        self.binary_enabled.toggled.connect(self._refresh_preview)
        self.ternary_enabled.toggled.connect(self._refresh_preview)

        return _wrap_in_scroll_area(page, min_width=840, min_height=700)

    def _dataframe_paths(self) -> list[str]:
        values: list[str] = []
        for row in range(self.df_table.rowCount()):
            item = self.df_table.item(row, 0)
            if item is None:
                continue
            values.append(str(item.data(Qt.UserRole) or item.text()))
        return values

    def _append_dataframe(self, path: Path | str) -> None:
        raw = str(path)
        resolved = self._resolve(raw)
        display = self._display_path(resolved)

        canonical = str(resolved.resolve())
        if canonical in self._dataframe_paths():
            return

        row = self.df_table.rowCount()
        self.df_table.insertRow(row)

        item = QTableWidgetItem(display)
        item.setData(Qt.UserRole, canonical)
        self.df_table.setItem(row, 0, item)
        self.df_table.setItem(
            row,
            1,
            QTableWidgetItem("Ready" if resolved.exists() else "文件不存在"),
        )
        self._refresh_preview()

    def _reset_dataframes(
        self,
        checked: bool = False,
        initial: bool = False,
    ) -> None:
        self.df_table.setRowCount(0)
        defaults = [
            "01_dataset/mp.df",
            "01_dataset/wbm.df",
            "01_dataset/local_structures.df",
        ]
        existing = [value for value in defaults if (self._project_root() / value).exists()]
        for value in existing:
            self._append_dataframe(value)
        if not initial:
            self.refresh_inputs()

    def _prune_stale_default_dataframes(self) -> None:
        root = self._project_root()
        default_names = {
            "01_dataset/mp.df",
            "01_dataset/wbm.df",
            "01_dataset/local_structures.df",
        }
        local_df = root / "01_dataset" / "local_structures.df"
        if not local_df.exists():
            return

        keep: list[Path | str] = []
        changed = False
        for raw in self._dataframe_paths():
            normalized = raw.replace("\\", "/")
            path = Path(raw)
            if not path.is_absolute():
                path = root / path
            is_default = (
                normalized in default_names
                or "/01_dataset/mp.df" in normalized
                or "/01_dataset/wbm.df" in normalized
                or "/01_dataset/local_structures.df" in normalized
            )
            is_stale_gui_child = "/src/ssscreen/gui/01_dataset/" in normalized
            if path.exists():
                keep.append(path)
            elif is_default or is_stale_gui_child:
                changed = True
            else:
                keep.append(raw)

        if changed:
            if not keep:
                keep = [local_df]
            self.df_table.setRowCount(0)
            for value in keep:
                self._append_dataframe(value)

    def _add_dataframe(self) -> None:
        values, _ = QFileDialog.getOpenFileNames(
            self,
            "添加规范化材料 DataFrame",
            str(self._project_root() / "01_dataset"),
            "DataFrame files (*.df *.pkl *.pickle);;All files (*)",
        )
        for value in values:
            self._append_dataframe(Path(value))
        self.refresh_inputs()

    def _remove_dataframes(self) -> None:
        rows = sorted(
            {index.row() for index in self.df_table.selectedIndexes()},
            reverse=True,
        )
        for row in rows:
            self.df_table.removeRow(row)
        self._refresh_preview()

    def refresh_inputs(self) -> None:
        if not hasattr(self, "df_table"):
            return

        if self.df_table.rowCount() == 0:
            self._reset_dataframes(initial=True)
        self._prune_stale_default_dataframes()

        for row in range(self.df_table.rowCount()):
            item = self.df_table.item(row, 0)
            if item is None:
                continue
            raw = str(item.data(Qt.UserRole) or item.text())
            path = Path(raw)
            if not path.is_absolute():
                path = self._project_root() / path
            display = self._display_path(path)
            item.setText(display.replace("\\", "/"))
            item.setData(Qt.UserRole, str(path.resolve()))
            self.df_table.setItem(
                row,
                1,
                QTableWidgetItem("Ready" if path.exists() else "文件不存在"),
            )

        valence_path = self._resolve(self.valence_edit.text())
        # First opening: automatically enable valence filtering only if a
        # valid_ids.json already exists. Afterwards the checkbox is user-owned.
        if not hasattr(self, "_valence_initialized"):
            self.use_valence.setChecked(valence_path.exists())
            self._valence_initialized = True

        self.valence_edit.setEnabled(self.use_valence.isChecked())
        self._refresh_preview()

    def _element_counts(self) -> list[int]:
        return [
            count
            for count, checkbox in ((2, self.binary_enabled), (3, self.ternary_enabled))
            if checkbox.isChecked()
        ]

    def _screen_argv(self) -> list[str]:
        argv = ["composition-screen"]

        for raw in self._dataframe_paths():
            path = Path(raw)
            value = self._display_path(path) if path.is_absolute() else raw
            value = value.replace("\\", "/")
            argv.extend(["--df", value])

        if self.use_valence.isChecked() and self.valence_edit.text().strip():
            argv.extend(["--valence-ids", self.valence_edit.text().strip()])

        for count in self._element_counts():
            argv.extend(["--nelems", str(count)])
        argv.extend(
            [
                "--max-bandgap",
                self.max_bandgap_edit.text().strip() or "1.0",
                "--max-e-hull",
                self.max_e_hull_edit.text().strip() or "0.01",
                "--min-group-size",
                self.min_group_size_edit.text().strip() or "2",
                "--min-x-elements",
                self.min_x_elements_edit.text().strip() or "2",
                "--output",
                self.candidates_output.text().strip().replace("\\", "/"),
                "--summary",
                self.summary_output.text().strip().replace("\\", "/"),
                "--structures-output",
                self.structures_output.text().strip().replace("\\", "/"),
            ]
        )
        return argv

    def _refresh_preview(self) -> None:
        if hasattr(self, "command_preview"):
            if not self._element_counts():
                self.command_preview.setPlainText("请至少勾选二元或三元。")
                return
            self.command_preview.setPlainText(shlex.join(["ss-screen", *self._screen_argv()]))

    def _run_screen(self) -> None:
        if not self._element_counts():
            QMessageBox.warning(self, "筛选参数错误", "请至少勾选二元或三元。")
            return
        if not self._check_required(
            [
                ("规范化 DataFrame", ", ".join(self._dataframe_paths())),
                ("候选材料表输出", self.candidates_output.text()),
                ("筛选统计输出", self.summary_output.text()),
                ("候选结构输出", self.structures_output.text()),
            ]
        ):
            return

        # Basic GUI-side type checks; final validation still belongs to Click.
        try:
            if int(self.min_group_size_edit.text().strip()) < 1:
                raise ValueError
            if int(self.min_x_elements_edit.text().strip()) < 1:
                raise ValueError
            if float(self.max_bandgap_edit.text().strip()) < 0:
                raise ValueError
            if float(self.max_e_hull_edit.text().strip()) < 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(
                self,
                "筛选参数错误",
                "组大小和 X 元素数量必须为正整数；带隙和凸包距离必须为非负数字。",
            )
            return

        self.run_requested.emit(
            self._screen_argv(),
            "组成模板筛选",
        )

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def _build_results_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(7)

        files_box = QGroupBox("Result Files / 结果文件")
        files_form = QFormLayout(files_box)
        files_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.candidates_file_state = QLabel("未生成")
        self.summary_file_state = QLabel("未生成")
        self.structures_file_state = QLabel("未生成")
        files_form.addRow("候选结构（供 03 输入）", self.structures_file_state)
        files_form.addRow(
            "Composition Candidates",
            self.candidates_file_state,
        )
        files_form.addRow(
            "Screening Summary",
            self.summary_file_state,
        )
        layout.addWidget(files_box)

        summary_box = QGroupBox("Screening Summary / 筛选统计")
        summary_form = QFormLayout(summary_box)
        summary_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.input_rows_value = QLabel("—")
        self.selected_rows_value = QLabel("—")
        self.template_count_value = QLabel("—")
        self.candidate_rows_value = QLabel("—")
        self.unique_materials_value = QLabel("—")

        summary_form.addRow("输入材料数", self.input_rows_value)
        summary_form.addRow("通过基础筛选", self.selected_rows_value)
        summary_form.addRow("组成模板数", self.template_count_value)
        summary_form.addRow("候选材料记录", self.candidate_rows_value)
        summary_form.addRow("去重候选结构数（供 03）", self.unique_materials_value)
        layout.addWidget(summary_box)

        condition_box = QGroupBox("Screening Conditions / 实际筛选条件")
        condition_form = QFormLayout(condition_box)
        condition_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.result_nelems = QLabel("—")
        self.result_max_bandgap = QLabel("—")
        self.result_max_e_hull = QLabel("—")
        self.result_min_group_size = QLabel("—")
        self.result_min_x_elements = QLabel("—")
        self.result_valence = QLabel("—")

        condition_form.addRow("元素数量", self.result_nelems)
        condition_form.addRow("最大初筛带隙", self.result_max_bandgap)
        condition_form.addRow("最大凸包距离", self.result_max_e_hull)
        condition_form.addRow("模板最少材料数", self.result_min_group_size)
        condition_form.addRow("模板最少 X 元素数", self.result_min_x_elements)
        condition_form.addRow("价态过滤", self.result_valence)
        layout.addWidget(condition_box)

        candidates_box = QGroupBox("Composition Candidates / 候选材料表")
        candidates_layout = QVBoxLayout(candidates_box)

        filter_row = QHBoxLayout()
        self.candidate_search = QLineEdit()
        self.candidate_search.setPlaceholderText(
            "搜索 Template / Material ID / Formula / Source ..."
        )
        self.template_filter = QComboBox()
        self.template_filter.addItem("全部模板")
        self.candidate_count_label = QLabel("0 条")

        self.candidate_search.textChanged.connect(self._apply_candidate_filter)
        self.template_filter.currentTextChanged.connect(self._apply_candidate_filter)

        filter_row.addWidget(QLabel("搜索"))
        filter_row.addWidget(self.candidate_search, 1)
        filter_row.addWidget(QLabel("Template"))
        filter_row.addWidget(self.template_filter)
        filter_row.addWidget(self.candidate_count_label)
        candidates_layout.addLayout(filter_row)

        self.candidates_table = QTableWidget(0, 0)
        self.candidates_table.verticalHeader().setVisible(False)
        self.candidates_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.candidates_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.candidates_table.setSortingEnabled(False)
        self.candidates_table.setMinimumHeight(275)
        candidates_layout.addWidget(self.candidates_table)
        layout.addWidget(candidates_box, 1)

        raw_summary_box = QGroupBox("Summary JSON Fields / 原始统计字段")
        raw_summary_layout = QVBoxLayout(raw_summary_box)
        self.summary_table = QTableWidget(0, 2)
        self.summary_table.setHorizontalHeaderLabels(["字段", "值"])
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.summary_table.horizontalHeader().setStretchLastSection(True)
        self.summary_table.setMaximumHeight(190)
        raw_summary_layout.addWidget(self.summary_table)
        layout.addWidget(raw_summary_box)

        actions = QHBoxLayout()
        refresh = QPushButton("刷新结果")
        refresh.clicked.connect(self.refresh_results)
        open_candidates = QPushButton("打开候选材料表")
        open_candidates.clicked.connect(self._open_candidates_file)
        open_summary = QPushButton("打开筛选统计")
        open_summary.clicked.connect(self._open_summary_file)

        actions.addWidget(refresh)
        actions.addWidget(open_candidates)
        actions.addWidget(open_summary)
        actions.addStretch(1)
        layout.addLayout(actions)

        return _wrap_in_scroll_area(page, min_width=900, min_height=930)

    def _load_summary(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _load_candidates(
        self,
        path: Path,
    ) -> tuple[list[str], list[dict[str, str]]]:
        if not path.exists():
            return [], []

        with path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames or [])
            rows = [dict(row) for row in reader]
        return fields, rows

    def _find_field(
        self,
        fields: list[str],
        candidates: tuple[str, ...],
    ) -> str | None:
        lowered = {field.lower(): field for field in fields}
        for candidate in candidates:
            if candidate.lower() in lowered:
                return lowered[candidate.lower()]
        return None

    def _display_header(self, field: str) -> str:
        aliases = {
            "template": "Template",
            "material_id": "Material ID",
            "mp_id": "Material ID",
            "formula": "Formula",
            "composition": "Composition",
            "x_element": "X Element",
            "band_gap": "Band Gap",
            "e_hull": "E Hull",
            "source": "Source",
        }
        return aliases.get(field.lower(), field)

    def refresh_results(self) -> None:
        if not hasattr(self, "candidates_table"):
            return

        candidate_path = self._resolve(self.candidates_output.text())
        summary_path = self._resolve(self.summary_output.text())
        structures_path = self._resolve(self.structures_output.text())
        self.structures_file_state.setText(
            self._display_path(structures_path)
            + (" · 已生成" if structures_path.is_file() else " · 未生成")
        )

        self.candidates_file_state.setText(
            self._display_path(candidate_path)
            + (" · 已生成" if candidate_path.exists() else " · 未生成")
        )
        self.summary_file_state.setText(
            self._display_path(summary_path)
            + (" · 已生成" if summary_path.exists() else " · 未生成")
        )

        summary = self._load_summary(summary_path)

        try:
            fields, records = self._load_candidates(candidate_path)
        except Exception as exc:
            fields, records = [], []
            self.candidates_file_state.setText(
                f"{self._display_path(candidate_path)} · 读取失败：{exc}"
            )

        self._candidate_fields = fields
        self._candidate_records = records
        self._template_field = self._find_field(
            fields,
            ("template", "composition_template"),
        )

        # Core statistics: summary.json has priority; CSV-derived values are
        # used only when that exact statistic can be computed safely.
        template_values = set()
        if self._template_field:
            template_values = {
                str(row.get(self._template_field, "")).strip()
                for row in records
                if str(row.get(self._template_field, "")).strip()
            }

        input_rows = summary.get("input_rows", "—")
        selected_rows = summary.get("selected_rows", "—")
        template_count = summary.get(
            "template_count",
            len(template_values) if template_values else "—",
        )
        candidate_rows = summary.get(
            "candidate_rows",
            len(records) if candidate_path.exists() else "—",
        )

        self.input_rows_value.setText(str(input_rows))
        self.selected_rows_value.setText(str(selected_rows))
        self.template_count_value.setText(str(template_count))
        self.candidate_rows_value.setText(str(candidate_rows))
        self.unique_materials_value.setText(str(summary.get("unique_candidate_materials", "—")))

        # Show the actual recorded conditions when summary contains them;
        # otherwise show current GUI settings and mark no extra conclusions.
        self.result_nelems.setText(str(summary.get("nelems", self._element_counts())))
        self.result_max_bandgap.setText(
            str(
                summary.get(
                    "max_bandgap",
                    self.max_bandgap_edit.text(),
                )
            )
            + " eV"
        )
        self.result_max_e_hull.setText(
            str(
                summary.get(
                    "max_e_hull",
                    self.max_e_hull_edit.text(),
                )
            )
            + " eV/atom"
        )
        self.result_min_group_size.setText(
            str(
                summary.get(
                    "min_group_size",
                    self.min_group_size_edit.text(),
                )
            )
        )
        self.result_min_x_elements.setText(
            str(
                summary.get(
                    "min_x_elements",
                    self.min_x_elements_edit.text(),
                )
            )
        )

        valence_path = self._resolve(self.valence_edit.text())
        if "valence_ids" in summary:
            self.result_valence.setText(str(summary["valence_ids"]))
        elif self.use_valence.isChecked():
            self.result_valence.setText("使用：" + self._display_path(valence_path))
        else:
            self.result_valence.setText("未使用")

        # Candidate table.
        self.candidates_table.setSortingEnabled(False)
        self.candidates_table.clear()
        self.candidates_table.setRowCount(len(records))
        self.candidates_table.setColumnCount(len(fields))
        self.candidates_table.setHorizontalHeaderLabels(
            [self._display_header(field) for field in fields]
        )

        for row_index, record in enumerate(records):
            for col_index, field in enumerate(fields):
                value = record.get(field, "")
                self.candidates_table.setItem(
                    row_index,
                    col_index,
                    QTableWidgetItem(str(value)),
                )

        if fields:
            self.candidates_table.horizontalHeader().setStretchLastSection(True)
        self.candidates_table.setSortingEnabled(True)

        # Template filter.
        current_template = self.template_filter.currentText()
        self.template_filter.blockSignals(True)
        self.template_filter.clear()
        self.template_filter.addItem("全部模板")
        for value in sorted(template_values):
            self.template_filter.addItem(value)
        index = self.template_filter.findText(current_template)
        self.template_filter.setCurrentIndex(index if index >= 0 else 0)
        self.template_filter.blockSignals(False)

        # Raw summary fields for auditability.
        self.summary_table.setRowCount(0)
        for key, value in summary.items():
            row = self.summary_table.rowCount()
            self.summary_table.insertRow(row)
            self.summary_table.setItem(
                row,
                0,
                QTableWidgetItem(str(key)),
            )
            if isinstance(value, (dict, list)):
                display = json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            else:
                display = str(value)
            self.summary_table.setItem(
                row,
                1,
                QTableWidgetItem(display),
            )

        self._apply_candidate_filter()

    def _apply_candidate_filter(self) -> None:
        if not hasattr(self, "candidates_table"):
            return

        query = self.candidate_search.text().strip().lower()
        template = self.template_filter.currentText()
        visible = 0

        for row_index, record in enumerate(self._candidate_records):
            text_match = True
            if query:
                text_match = any(query in str(value).lower() for value in record.values())

            template_match = True
            if template != "全部模板" and self._template_field is not None:
                template_match = str(record.get(self._template_field, "")).strip() == template

            show = text_match and template_match
            self.candidates_table.setRowHidden(
                row_index,
                not show,
            )
            if show:
                visible += 1

        total = len(self._candidate_records)
        if visible == total:
            self.candidate_count_label.setText(f"{total} 条")
        else:
            self.candidate_count_label.setText(f"{visible} / {total} 条")

    def _open_candidates_file(self) -> None:
        path = self._resolve(self.candidates_output.text())
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.information(
                self,
                "结果未生成",
                f"候选材料表尚不存在：\n{path}",
            )

    def _open_summary_file(self) -> None:
        path = self._resolve(self.summary_output.text())
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.information(
                self,
                "结果未生成",
                f"筛选统计尚不存在：\n{path}",
            )

    def select_section(self, section: str) -> None:
        if section in {"input", "rules", "screen"}:
            self.tabs.setCurrentIndex(0)
            self.refresh_inputs()
        else:
            self.tabs.setCurrentIndex(1)
            self.refresh_results()


class StructureArchivePage(QWidget):
    """Engineering GUI for workflow Step 2: structure description archive."""

    run_requested = Signal(list, str)
    stop_requested = Signal()
    use_completed_requested = Signal()

    def __init__(self, project_provider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_provider = project_provider

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(7)

        header = QHBoxLayout()
        title = QLabel("结构描述归档")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        badge = QLabel("Stage 03")
        badge.setObjectName("stateBadge")
        header.addWidget(badge)
        root.addLayout(header)

        subtitle = QLabel(
            "通过 condense 调用 robocrys，将 pymatgen 晶体结构转换为机器可读取、可比较、"
            "可审计的局部环境描述，为后续结构匹配与材料分组提供统一结构表达。"
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("pageDescription")
        root.addWidget(subtitle)

        controls = QHBoxLayout()
        self.stop_button = QPushButton("停止计算（保留结果）")
        self.stop_button.setEnabled(False)
        self.stop_button.setToolTip("完成当前结构后停止，保存已完成描述及运行记录；再次运行可续算。")
        self.stop_button.clicked.connect(self.stop_requested.emit)
        self.use_completed_button = QPushButton("使用已完成结果进入 04")
        self.use_completed_button.clicked.connect(self.use_completed_requested.emit)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.use_completed_button)
        controls.addStretch(1)
        root.addLayout(controls)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMinimumHeight(500)
        self.tabs.addTab(self._build_dataframe_tab(), "从 DataFrame 批量生成")
        self.tabs.addTab(self._build_files_tab(), "从结构文件生成")
        self.tabs.addTab(self._build_archive_tab(), "归档 / 索引 / 校验")
        root.addWidget(self.tabs, 1)

        boundary = QGroupBox("Stage Boundary / 本阶段边界")
        boundary_layout = QVBoxLayout(boundary)
        boundary_layout.setContentsMargins(8, 8, 8, 8)
        text = QLabel(
            "只读取输入结构，不修改原始 DataFrame、CIF、POSCAR，也不改变元素种类、原子坐标或晶胞参数。"
            "本阶段输出仅用于比较局部结构环境，不单独证明材料能够形成固溶体，"
            "也不提供带隙、混合焓、声子或凸包稳定性结论。"
        )
        text.setWordWrap(True)
        text.setObjectName("optionHelp")
        boundary_layout.addWidget(text)
        root.addWidget(boundary)

        self.refresh_archive()
        self._refresh_df_preview()
        self._refresh_files_preview()

    # ---------- shared helpers ----------

    def _project_root(self) -> Path:
        return Path(self.project_provider()).expanduser().resolve()

    def _display_path(self, path: Path) -> str:
        return _project_display_path(self._project_root(), path)

    def _resolve(self, value: str) -> Path:
        return _resolve_project_path(self._project_root(), value)

    def _path_editor(
        self,
        default: str,
        *,
        directory: bool = False,
        save_file: bool = False,
    ) -> tuple[QWidget, QLineEdit]:
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        edit = QLineEdit(default)
        button = QPushButton("…")
        button.setMaximumWidth(34)

        def browse() -> None:
            base = str(self._project_root())
            if directory:
                value = QFileDialog.getExistingDirectory(self, "选择目录", base)
            elif save_file:
                value, _ = QFileDialog.getSaveFileName(self, "选择输出文件", base)
            else:
                value, _ = QFileDialog.getOpenFileName(self, "选择文件", base)
            if value:
                edit.setText(self._display_path(Path(value)))

        button.clicked.connect(browse)
        row.addWidget(edit, 1)
        row.addWidget(button)
        return host, edit

    def _check_required(self, items: list[tuple[str, QLineEdit]]) -> bool:
        missing = [name for name, edit in items if not edit.text().strip()]
        if not missing:
            return True
        QMessageBox.warning(
            self,
            "缺少必要输入",
            "请先填写：\n" + "\n".join(f"• {name}" for name in missing),
        )
        return False

    # ---------- DataFrame mode ----------

    def _build_dataframe_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(7)

        intro = QLabel(
            "从规范化材料数据库批量读取晶体结构。默认使用 DataFrame index 作为材料 ID；"
            "若材料 ID 位于普通列，可启用“指定材料 ID 字段”。"
        )
        intro.setWordWrap(True)
        intro.setObjectName("pageDescription")
        layout.addWidget(intro)

        input_box = QGroupBox("Input / 输入数据")
        form = QFormLayout(input_box)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(7)

        self.df_follow_composition = QCheckBox("默认使用 02 输出的候选结构 candidates.df")
        self.df_follow_composition.setChecked(True)
        form.addRow("输入来源", self.df_follow_composition)
        host, self.df_path = self._path_editor("02_composition/candidates.df")
        self.df_path.setReadOnly(True)
        host.findChild(QPushButton).setEnabled(False)
        self.df_follow_composition.toggled.connect(self.df_path.setReadOnly)
        self.df_follow_composition.toggled.connect(
            lambda follow, host=host: host.findChild(QPushButton).setEnabled(not follow)
        )
        form.addRow("DataFrame", host)

        self.structure_column = QLineEdit("structure")
        form.addRow("结构字段", self.structure_column)

        self.use_material_id = QCheckBox("指定材料 ID 字段")
        self.material_id_column = QLineEdit()
        self.material_id_column.setPlaceholderText("默认：使用 DataFrame index")
        self.material_id_column.setEnabled(False)
        self.use_material_id.toggled.connect(self.material_id_column.setEnabled)
        id_host = QWidget()
        id_layout = QHBoxLayout(id_host)
        id_layout.setContentsMargins(0, 0, 0, 0)
        id_layout.addWidget(self.use_material_id)
        id_layout.addWidget(self.material_id_column, 1)
        form.addRow("材料 ID", id_host)
        layout.addWidget(input_box)

        output_box = QGroupBox("Archive / 归档输出")
        out_form = QFormLayout(output_box)
        out_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        out_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        out_form.setHorizontalSpacing(12)
        out_form.setVerticalSpacing(7)

        host, self.df_output_dir = self._path_editor("03_condensed/local", directory=True)
        out_form.addRow("结构描述目录", host)
        host, self.df_manifest = self._path_editor("03_condensed/local_manifest.jsonl", save_file=True)
        out_form.addRow("Manifest", host)
        host, self.df_index = self._path_editor("03_condensed/local_index.csv", save_file=True)
        out_form.addRow("Index", host)
        layout.addWidget(output_box)

        settings_box = QGroupBox("Run Settings / 运行设置")
        settings = QFormLayout(settings_box)
        settings.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.df_limit = QLineEdit()
        self.df_limit.setPlaceholderText("留空 = 全量处理")
        self.df_limit.setMaximumWidth(180)
        settings.addRow("处理数量", self.df_limit)
        self.df_stop_on_error = QCheckBox("首个错误即停止；未勾选时保留失败记录并继续批处理")
        settings.addRow("错误策略", self.df_stop_on_error)
        layout.addWidget(settings_box)

        preview_label = QLabel("Command Preview / 命令预览")
        preview_label.setObjectName("sectionLabel")
        layout.addWidget(preview_label)
        self.df_preview = QPlainTextEdit()
        self.df_preview.setReadOnly(True)
        self.df_preview.setMaximumHeight(72)
        self.df_preview.setObjectName("commandPreview")
        layout.addWidget(self.df_preview)

        actions = QHBoxLayout()
        test_button = QPushButton("小批量测试（10 个结构）")
        test_button.clicked.connect(lambda: self._run_dataframe(test_limit=10))
        copy_button = QPushButton("复制命令")
        copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.df_preview.toPlainText())
        )
        run_button = QPushButton("开始全量生成")
        run_button.setObjectName("primaryButton")
        run_button.clicked.connect(self._run_dataframe)
        actions.addWidget(test_button)
        actions.addStretch(1)
        actions.addWidget(copy_button)
        actions.addWidget(run_button)
        layout.addLayout(actions)
        layout.addStretch(1)

        for edit in (
            self.df_path,
            self.structure_column,
            self.material_id_column,
            self.df_output_dir,
            self.df_manifest,
            self.df_index,
            self.df_limit,
        ):
            edit.textChanged.connect(self._refresh_df_preview)
        self.use_material_id.toggled.connect(self._refresh_df_preview)
        self.df_stop_on_error.toggled.connect(self._refresh_df_preview)
        return _wrap_in_scroll_area(page, min_width=820, min_height=650)

    def _df_argv(self, override_limit: int | None = None) -> list[str]:
        argv = [
            "condense",
            "--df",
            self.df_path.text().strip(),
            "--structure-column",
            self.structure_column.text().strip() or "structure",
            "--output-dir",
            self.df_output_dir.text().strip(),
            "--manifest",
            self.df_manifest.text().strip(),
            "--index",
            self.df_index.text().strip(),
        ]
        if self.use_material_id.isChecked() and self.material_id_column.text().strip():
            argv.extend(["--material-id-column", self.material_id_column.text().strip()])
        limit = str(override_limit) if override_limit is not None else self.df_limit.text().strip()
        if limit:
            argv.extend(["--limit", limit])
        if self.df_stop_on_error.isChecked():
            argv.append("--stop-on-error")
        return argv

    def _refresh_df_preview(self) -> None:
        if hasattr(self, "df_preview"):
            self.df_preview.setPlainText(shlex.join(["ss-screen", *self._df_argv()]))

    def _run_dataframe(self, checked: bool = False, test_limit: int | None = None) -> None:
        if not self._check_required(
            [
                ("DataFrame", self.df_path),
                ("结构描述目录", self.df_output_dir),
                ("Manifest", self.df_manifest),
                ("Index", self.df_index),
            ]
        ):
            return
        argv = self._df_argv(override_limit=test_limit)
        title = "结构描述归档 · DataFrame"
        if test_limit is not None:
            title += f" · 小批量测试 {test_limit}"
        self.run_requested.emit(argv, title)

    # ---------- direct structure-file mode ----------

    def _build_files_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(7)

        intro = QLabel(
            "直接提供 CIF、POSCAR 或其他 pymatgen 可解析的晶体结构文件。"
            "软件使用文件名作为材料 ID，例如 example-a.cif → example-a.json。"
        )
        intro.setWordWrap(True)
        intro.setObjectName("pageDescription")
        layout.addWidget(intro)

        input_box = QGroupBox("Structure Files / 输入结构")
        input_layout = QVBoxLayout(input_box)
        input_layout.setContentsMargins(6, 8, 6, 6)

        self.file_table = QTableWidget(0, 4)
        self.file_table.setHorizontalHeaderLabels(["文件", "类型", "Material ID", "状态"])
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.file_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.file_table.horizontalHeader().setStretchLastSection(True)
        self.file_table.setColumnWidth(0, 390)
        self.file_table.setColumnWidth(1, 90)
        self.file_table.setColumnWidth(2, 150)
        self.file_table.setMinimumHeight(210)
        input_layout.addWidget(self.file_table)

        file_actions = QHBoxLayout()
        add_files = QPushButton("＋ 添加文件")
        add_files.clicked.connect(self._add_structure_files)
        add_folder = QPushButton("＋ 添加文件夹")
        add_folder.clicked.connect(self._add_structure_folder)
        remove = QPushButton("移除所选")
        remove.clicked.connect(self._remove_structure_files)
        clear = QPushButton("清空")
        clear.clicked.connect(self._clear_structure_files)
        file_actions.addWidget(add_files)
        file_actions.addWidget(add_folder)
        file_actions.addWidget(remove)
        file_actions.addWidget(clear)
        file_actions.addStretch(1)
        input_layout.addLayout(file_actions)
        layout.addWidget(input_box, 1)

        output_box = QGroupBox("Archive / 归档输出")
        out_form = QFormLayout(output_box)
        out_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        out_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        out_form.setHorizontalSpacing(12)
        out_form.setVerticalSpacing(7)

        host, self.files_output_dir = self._path_editor("03_condensed/local", directory=True)
        out_form.addRow("结构描述目录", host)
        host, self.files_manifest = self._path_editor(
            "03_condensed/local_manifest.jsonl", save_file=True
        )
        out_form.addRow("Manifest", host)
        host, self.files_index = self._path_editor("03_condensed/local_index.csv", save_file=True)
        out_form.addRow("Index", host)
        self.files_stop_on_error = QCheckBox("首个错误即停止")
        out_form.addRow("错误策略", self.files_stop_on_error)
        layout.addWidget(output_box)

        preview_label = QLabel("Command Preview / 命令预览")
        preview_label.setObjectName("sectionLabel")
        layout.addWidget(preview_label)
        self.files_preview = QPlainTextEdit()
        self.files_preview.setReadOnly(True)
        self.files_preview.setMaximumHeight(72)
        self.files_preview.setObjectName("commandPreview")
        layout.addWidget(self.files_preview)

        actions = QHBoxLayout()
        copy_button = QPushButton("复制命令")
        copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.files_preview.toPlainText())
        )
        run_button = QPushButton("生成结构描述")
        run_button.setObjectName("primaryButton")
        run_button.clicked.connect(self._run_files)
        actions.addStretch(1)
        actions.addWidget(copy_button)
        actions.addWidget(run_button)
        layout.addLayout(actions)

        for edit in (self.files_output_dir, self.files_manifest, self.files_index):
            edit.textChanged.connect(self._refresh_files_preview)
        self.files_stop_on_error.toggled.connect(self._refresh_files_preview)
        return _wrap_in_scroll_area(page, min_width=820, min_height=700)

    def _structure_file_rows(self) -> list[str]:
        values: list[str] = []
        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 0)
            if item is not None:
                values.append(str(item.data(Qt.UserRole) or item.text()))
        return values

    def _material_id_for_path(self, path: Path) -> str:
        upper = path.name.upper()
        if upper.startswith(("POSCAR", "CONTCAR")):
            return path.parent.name or path.name
        return path.stem

    def _file_type(self, path: Path) -> str:
        upper = path.name.upper()
        if upper.startswith("POSCAR"):
            return "POSCAR"
        if upper.startswith("CONTCAR"):
            return "CONTCAR"
        return path.suffix.lstrip(".").upper() or "STRUCTURE"

    def _append_structure_file(self, path: Path) -> None:
        canonical = str(path.resolve())
        existing = set(self._structure_file_rows())
        if canonical in existing:
            return

        row = self.file_table.rowCount()
        self.file_table.insertRow(row)

        item = QTableWidgetItem(self._display_path(path))
        item.setData(Qt.UserRole, canonical)
        self.file_table.setItem(row, 0, item)
        self.file_table.setItem(row, 1, QTableWidgetItem(self._file_type(path)))
        self.file_table.setItem(row, 2, QTableWidgetItem(self._material_id_for_path(path)))
        self.file_table.setItem(row, 3, QTableWidgetItem("Ready"))
        self._refresh_files_preview()

    def _add_structure_files(self) -> None:
        values, _ = QFileDialog.getOpenFileNames(
            self,
            "选择晶体结构文件",
            str(self._project_root()),
            "Structure files (*.cif *.vasp *.poscar *.json);;All files (*)",
        )
        for value in values:
            self._append_structure_file(Path(value))

    def _add_structure_folder(self) -> None:
        value = QFileDialog.getExistingDirectory(
            self,
            "选择结构文件目录",
            str(self._project_root()),
        )
        if not value:
            return

        folder = Path(value)
        supported = {".cif", ".vasp", ".poscar", ".json"}
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() in supported or path.name.upper().startswith(
                ("POSCAR", "CONTCAR")
            ):
                self._append_structure_file(path)

    def _remove_structure_files(self) -> None:
        rows = sorted(
            {index.row() for index in self.file_table.selectedIndexes()},
            reverse=True,
        )
        for row in rows:
            self.file_table.removeRow(row)
        self._refresh_files_preview()

    def _clear_structure_files(self) -> None:
        self.file_table.setRowCount(0)
        self._refresh_files_preview()

    def _files_argv(self) -> list[str]:
        argv = ["condense"]
        for value in self._structure_file_rows():
            argv.extend(["--input", value])
        argv.extend(
            [
                "--output-dir",
                self.files_output_dir.text().strip(),
                "--manifest",
                self.files_manifest.text().strip(),
                "--index",
                self.files_index.text().strip(),
            ]
        )
        if self.files_stop_on_error.isChecked():
            argv.append("--stop-on-error")
        return argv

    def _refresh_files_preview(self) -> None:
        if hasattr(self, "files_preview"):
            self.files_preview.setPlainText(shlex.join(["ss-screen", *self._files_argv()]))

    def _run_files(self) -> None:
        if not self._structure_file_rows():
            QMessageBox.warning(
                self,
                "没有结构文件",
                "请先添加至少一个 CIF、POSCAR 或其他晶体结构文件。",
            )
            return
        if not self._check_required(
            [
                ("结构描述目录", self.files_output_dir),
                ("Manifest", self.files_manifest),
                ("Index", self.files_index),
            ]
        ):
            return
        self.run_requested.emit(self._files_argv(), "结构描述归档 · 结构文件")

    # ---------- archive / index / validation ----------

    def _build_archive_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(7)

        summary_box = QGroupBox("Archive Status / 归档状态")
        summary = QFormLayout(summary_box)
        summary.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.archive_count = QLabel("0")
        self.manifest_state = QLabel("未生成")
        self.index_state = QLabel("未生成")
        self.validation_state = QLabel("未执行")
        summary.addRow("结构描述数量", self.archive_count)
        summary.addRow("Manifest", self.manifest_state)
        summary.addRow("Index", self.index_state)
        summary.addRow("Validation", self.validation_state)
        layout.addWidget(summary_box)

        archive_box = QGroupBox("Structure Description Archive / 结构描述库")
        archive_layout = QVBoxLayout(archive_box)
        self.archive_table = QTableWidget(0, 4)
        self.archive_table.setHorizontalHeaderLabels(["Material ID", "来源", "JSON", "状态"])
        self.archive_table.verticalHeader().setVisible(False)
        self.archive_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.archive_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.archive_table.horizontalHeader().setStretchLastSection(True)
        self.archive_table.setColumnWidth(0, 180)
        self.archive_table.setColumnWidth(1, 100)
        self.archive_table.setColumnWidth(2, 420)
        self.archive_table.setMinimumHeight(230)
        archive_layout.addWidget(self.archive_table)
        layout.addWidget(archive_box, 1)

        tools_box = QGroupBox("Archive Tools / 归档工具")
        tools = QFormLayout(tools_box)
        tools.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        tools.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        host, self.archive_dir_edit = self._path_editor("03_condensed/local", directory=True)
        tools.addRow("归档目录", host)
        host, self.archive_index_output = self._path_editor(
            "03_condensed/local_index.csv", save_file=True
        )
        tools.addRow("索引输出", host)
        host, self.archive_validation_output = self._path_editor(
            "03_condensed/local_validation.csv", save_file=True
        )
        tools.addRow("校验输出", host)
        layout.addWidget(tools_box)

        actions = QHBoxLayout()
        refresh = QPushButton("刷新归档")
        refresh.clicked.connect(self.refresh_archive)
        open_dir = QPushButton("打开归档目录")
        open_dir.clicked.connect(self._open_archive_dir)
        rebuild = QPushButton("建立 / 重建 Index")
        rebuild.clicked.connect(self._run_index)
        validate = QPushButton("校验归档")
        validate.setObjectName("primaryButton")
        validate.clicked.connect(self._run_validation)
        actions.addWidget(refresh)
        actions.addWidget(open_dir)
        actions.addStretch(1)
        actions.addWidget(rebuild)
        actions.addWidget(validate)
        layout.addLayout(actions)
        return _wrap_in_scroll_area(page, min_width=820, min_height=660)

    def _find_archive_json(self) -> list[tuple[str, Path]]:
        base = self._project_root() / "03_condensed"
        result: list[tuple[str, Path]] = []
        selected = self._resolve(self.archive_dir_edit.text())
        if selected.is_dir():
            result.extend(("LOCAL", path) for path in sorted(selected.glob("*.json")))
        for source in ("local", "mp", "user"):
            folder = base / source
            if not folder.exists():
                continue
            for path in sorted(folder.glob("*.json")):
                if not any(existing == path for _, existing in result):
                    result.append((source.upper(), path))
        return result

    def refresh_archive(self) -> None:
        if not hasattr(self, "archive_table"):
            return

        items = self._find_archive_json()
        self.archive_table.setRowCount(0)
        for source, path in items:
            row = self.archive_table.rowCount()
            self.archive_table.insertRow(row)
            self.archive_table.setItem(row, 0, QTableWidgetItem(path.stem))
            self.archive_table.setItem(row, 1, QTableWidgetItem(source))
            self.archive_table.setItem(row, 2, QTableWidgetItem(self._display_path(path)))
            self.archive_table.setItem(row, 3, QTableWidgetItem("OK"))
        self.archive_count.setText(str(len(items)))

        base = self._project_root() / "03_condensed"
        manifests = list(base.glob("*manifest*.jsonl")) if base.exists() else []
        indexes = list(base.glob("*index*.csv")) if base.exists() else []
        validations = list(base.glob("*validation*.csv")) if base.exists() else []

        self.manifest_state.setText(
            "未生成" if not manifests else "已生成：" + ", ".join(path.name for path in manifests)
        )
        self.index_state.setText(
            "未生成" if not indexes else "已生成：" + ", ".join(path.name for path in indexes)
        )
        self.validation_state.setText(
            "未执行"
            if not validations
            else "已生成：" + ", ".join(path.name for path in validations)
        )

    def select_section(self, section: str) -> None:
        if section in {"input", "dataframe"}:
            self.tabs.setCurrentIndex(0)
        elif section == "files":
            self.tabs.setCurrentIndex(1)
        else:
            self.tabs.setCurrentIndex(2)
        self.refresh_archive()

    def _open_archive_dir(self) -> None:
        path = self._resolve(self.archive_dir_edit.text())
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.information(self, "目录不存在", f"归档目录尚不存在：\n{path}")

    def _run_index(self) -> None:
        if not self._check_required(
            [
                ("归档目录", self.archive_dir_edit),
                ("索引输出", self.archive_index_output),
            ]
        ):
            return
        argv = [
            "condense-index",
            "--condensed-dir",
            self.archive_dir_edit.text().strip(),
            "--output",
            self.archive_index_output.text().strip(),
        ]
        self.run_requested.emit(argv, "结构描述归档 · 建立索引")

    def _run_validation(self) -> None:
        if not self._check_required(
            [
                ("归档目录", self.archive_dir_edit),
                ("校验输出", self.archive_validation_output),
            ]
        ):
            return
        argv = [
            "condense-validate",
            "--condensed-dir",
            self.archive_dir_edit.text().strip(),
            "--output",
            self.archive_validation_output.text().strip(),
        ]
        self.run_requested.emit(argv, "结构描述归档 · 校验")


class StructureMatchPage(QWidget):
    """Engineering GUI for workflow Step 3: structure matching and grouping.

    The page treats the structure group as a persistent engineering object.
    ``structure-match`` is an operation performed on the candidate table and
    one or more validated robocrys description archives.
    """

    run_requested = Signal(list, str)

    def __init__(self, project_provider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_provider = project_provider
        self._last_group_records: list[dict[str, Any]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(7)

        header = QHBoxLayout()
        title = QLabel("结构匹配与材料分组")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        badge = QLabel("Stage 04")
        badge.setObjectName("stateBadge")
        header.addWidget(badge)
        root.addLayout(header)

        subtitle = QLabel(
            "以上一步通过校验的 robocrys 结构描述归档为结构证据，以组成候选表为筛选范围，"
            "将可变元素重标记为占位符 X 后比较局部环境，并把结构原型相近的材料组织为 Structure Groups。"
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("pageDescription")
        root.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMinimumHeight(520)
        self.tabs.addTab(self._build_match_tab(), "匹配设置与执行")
        self.tabs.addTab(self._build_results_tab(), "Structure Groups / 结构组结果")
        root.addWidget(self.tabs, 1)

        boundary = QGroupBox("Algorithm Boundary / 算法边界")
        boundary_layout = QVBoxLayout(boundary)
        boundary_layout.setContentsMargins(8, 8, 8, 8)
        note = QLabel(
            "匹配依据是组成模板和 robocrys 局部结构环境，包括配位数、几何类型和连接关系等表达。"
            "软件不会仅凭化学式或空间群判断结构相同；结构环境相似也不等同于已经证明能够形成固溶体。"
            "热力学和动力学稳定性仍需后续混合焓、声子和凸包等证据。"
        )
        note.setWordWrap(True)
        note.setObjectName("optionHelp")
        boundary_layout.addWidget(note)
        root.addWidget(boundary)

        self.refresh_inputs()
        self.refresh_results()
        self._refresh_preview()

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _project_root(self) -> Path:
        return Path(self.project_provider()).expanduser().resolve()

    def _display_path(self, path: Path) -> str:
        return _project_display_path(self._project_root(), path)

    def _resolve(self, text: str) -> Path:
        return _resolve_project_path(self._project_root(), text)

    def _path_editor(
        self,
        default: str,
        *,
        directory: bool = False,
        save_file: bool = False,
    ) -> tuple[QWidget, QLineEdit]:
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        edit = QLineEdit(default)
        button = QPushButton("…")
        button.setMaximumWidth(34)

        def browse() -> None:
            base = str(self._project_root())
            if directory:
                value = QFileDialog.getExistingDirectory(self, "选择目录", base)
            elif save_file:
                value, _ = QFileDialog.getSaveFileName(self, "选择输出文件", base)
            else:
                value, _ = QFileDialog.getOpenFileName(self, "选择文件", base)
            if value:
                edit.setText(self._display_path(Path(value)))

        button.clicked.connect(browse)
        row.addWidget(edit, 1)
        row.addWidget(button)
        return host, edit

    def _check_required(self, items: list[tuple[str, str]]) -> bool:
        missing = [name for name, value in items if not str(value).strip()]
        if not missing:
            return True
        QMessageBox.warning(
            self,
            "缺少必要输入",
            "请先填写：\n" + "\n".join(f"• {name}" for name in missing),
        )
        return False

    # ------------------------------------------------------------------
    # Match setup tab
    # ------------------------------------------------------------------

    def _build_match_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(7)

        # Inputs
        input_box = QGroupBox("Match Inputs / 匹配输入")
        input_layout = QVBoxLayout(input_box)
        input_layout.setContentsMargins(8, 10, 8, 8)

        self.follow_stage03 = QCheckBox("默认使用 02 候选表和 03 已生成的结构描述")
        self.follow_stage03.setChecked(True)
        input_layout.addWidget(self.follow_stage03)
        partial_note = QLabel(
            "允许使用 03 的部分结果。仅匹配已生成且可读取的描述，"
            "未生成的材料会记录为缺失；结果页显示覆盖率及是否为部分筛选。"
        )
        partial_note.setWordWrap(True)
        input_layout.addWidget(partial_note)

        candidate_form = QFormLayout()
        candidate_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        candidate_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        candidate_form.setHorizontalSpacing(12)
        candidate_form.setVerticalSpacing(7)

        host, self.candidates_edit = self._path_editor("02_composition/composition_candidates.csv")
        self.candidates_edit.setReadOnly(True)
        host.findChild(QPushButton).setEnabled(False)
        self.follow_stage03.toggled.connect(self.candidates_edit.setReadOnly)
        self.follow_stage03.toggled.connect(
            lambda follow, host=host: host.findChild(QPushButton).setEnabled(not follow)
        )
        candidate_form.addRow("组成候选表", host)

        candidate_status_host = QWidget()
        candidate_status_layout = QHBoxLayout(candidate_status_host)
        candidate_status_layout.setContentsMargins(0, 0, 0, 0)
        candidate_status_layout.setSpacing(12)
        self.candidate_rows_label = QLabel("记录：—")
        self.template_count_label = QLabel("组成模板：—")
        self.candidate_input_state = QLabel("未检查")
        candidate_status_layout.addWidget(self.candidate_rows_label)
        candidate_status_layout.addWidget(self.template_count_label)
        candidate_status_layout.addWidget(self.candidate_input_state)
        candidate_status_layout.addStretch(1)
        candidate_form.addRow("候选状态", candidate_status_host)

        input_layout.addLayout(candidate_form)

        archive_label = QLabel("结构描述归档（可添加多个，运行时重复传递 --condensed-dir）")
        archive_label.setObjectName("sectionLabel")
        input_layout.addWidget(archive_label)

        self.archive_table = QTableWidget(0, 4)
        self.archive_table.setHorizontalHeaderLabels(["归档目录", "JSON 数量", "Validation", "状态"])
        self.archive_table.verticalHeader().setVisible(False)
        self.archive_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.archive_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.archive_table.horizontalHeader().setStretchLastSection(True)
        self.archive_table.setColumnWidth(0, 430)
        self.archive_table.setColumnWidth(1, 85)
        self.archive_table.setColumnWidth(2, 120)
        self.archive_table.setMinimumHeight(135)
        self.archive_table.setMaximumHeight(190)
        input_layout.addWidget(self.archive_table)

        archive_actions = QHBoxLayout()
        add_archive = QPushButton("＋ 添加描述归档")
        add_archive.clicked.connect(self._add_archive)
        remove_archive = QPushButton("移除所选")
        remove_archive.clicked.connect(self._remove_archives)
        reset_archives = QPushButton("恢复默认")
        reset_archives.clicked.connect(self._reset_archives)
        for button in (add_archive, remove_archive, reset_archives):
            button.setEnabled(False)
            self.follow_stage03.toggled.connect(
                lambda follow, button=button: button.setEnabled(not follow)
            )
        check_inputs = QPushButton("检查输入")
        check_inputs.clicked.connect(self.refresh_inputs)
        archive_actions.addWidget(add_archive)
        archive_actions.addWidget(remove_archive)
        archive_actions.addWidget(reset_archives)
        archive_actions.addStretch(1)
        archive_actions.addWidget(check_inputs)
        input_layout.addLayout(archive_actions)

        layout.addWidget(input_box)

        # Algorithm rules are deliberately read-only except min-x-elements,
        # because the current CLI does not expose separate switches for each
        # environment feature.
        rule_box = QGroupBox("Matching Rules / 匹配规则")
        rule_form = QFormLayout(rule_box)
        rule_form.setLabelAlignment(Qt.AlignRight | Qt.AlignTop)
        rule_form.setHorizontalSpacing(12)
        rule_form.setVerticalSpacing(7)

        self.min_x_edit = QLineEdit("2")
        self.min_x_edit.setMaximumWidth(100)
        rule_form.addRow("最少可替换元素数", self.min_x_edit)

        x_flow = QLabel(
            "组成模板 → 识别可变元素位点 → 可变元素重标记为 X → 比较 robocrys 局部环境 → Structure Group"
        )
        x_flow.setWordWrap(True)
        rule_form.addRow("X 占位符处理", x_flow)

        basis = QLabel("配位数 · 配位几何 · 最近邻/多面体表达 · 组分连接关系")
        basis.setWordWrap(True)
        rule_form.addRow("环境匹配依据", basis)

        limitation = QLabel("这些匹配依据由当前算法固定使用，并非可独立开关的 CLI 参数。")
        limitation.setWordWrap(True)
        limitation.setObjectName("optionHelp")
        rule_form.addRow("", limitation)

        layout.addWidget(rule_box)

        # Outputs
        output_box = QGroupBox("Outputs / 输出")
        output_form = QFormLayout(output_box)
        output_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        output_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        output_form.setHorizontalSpacing(12)
        output_form.setVerticalSpacing(7)

        host, self.groups_output = self._path_editor(
            "04_groups/groups.json",
            save_file=True,
        )
        output_form.addRow("Structure Groups", host)

        host, self.summary_output = self._path_editor(
            "04_groups/structure_match_summary.json",
            save_file=True,
        )
        output_form.addRow("阶段汇总", host)

        layout.addWidget(output_box)

        # Preview
        preview_label = QLabel("Command Preview / 命令预览")
        preview_label.setObjectName("sectionLabel")
        layout.addWidget(preview_label)

        self.match_preview = QPlainTextEdit()
        self.match_preview.setReadOnly(True)
        self.match_preview.setMaximumHeight(76)
        self.match_preview.setObjectName("commandPreview")
        layout.addWidget(self.match_preview)

        actions = QHBoxLayout()
        copy_button = QPushButton("复制命令")
        copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.match_preview.toPlainText())
        )
        refresh_button = QPushButton("刷新参数")
        refresh_button.clicked.connect(self._refresh_preview)
        run_button = QPushButton("开始结构匹配")
        run_button.setObjectName("primaryButton")
        run_button.clicked.connect(self._run_match)

        actions.addWidget(refresh_button)
        actions.addStretch(1)
        actions.addWidget(copy_button)
        actions.addWidget(run_button)
        layout.addLayout(actions)
        layout.addStretch(1)

        self.candidates_edit.textChanged.connect(self._refresh_preview)
        self.min_x_edit.textChanged.connect(self._refresh_preview)
        self.groups_output.textChanged.connect(self._refresh_preview)
        self.summary_output.textChanged.connect(self._refresh_preview)

        self._reset_archives(initial=True)
        return _wrap_in_scroll_area(page, min_width=820, min_height=760)

    def _archive_paths(self) -> list[str]:
        values: list[str] = []
        for row in range(self.archive_table.rowCount()):
            item = self.archive_table.item(row, 0)
            if item is None:
                continue
            values.append(str(item.data(Qt.UserRole) or item.text()))
        return values

    def _append_archive(self, path: Path) -> None:
        resolved = self._resolve(str(path))
        canonical = str(resolved.resolve())
        if canonical in self._archive_paths():
            return

        row = self.archive_table.rowCount()
        self.archive_table.insertRow(row)

        item = QTableWidgetItem(self._display_path(resolved))
        item.setData(Qt.UserRole, canonical)
        self.archive_table.setItem(row, 0, item)
        self.archive_table.setItem(row, 1, QTableWidgetItem("—"))
        self.archive_table.setItem(row, 2, QTableWidgetItem("—"))
        self.archive_table.setItem(row, 3, QTableWidgetItem("未检查"))
        self._refresh_preview()

    def _reset_archives(self, checked: bool = False, initial: bool = False) -> None:
        self.archive_table.setRowCount(0)
        default = self._project_root() / "03_condensed" / "local"
        self._append_archive(default)
        if not initial:
            self.refresh_inputs()

    def _add_archive(self) -> None:
        value = QFileDialog.getExistingDirectory(
            self,
            "添加 robocrys 结构描述归档",
            str(self._project_root() / "03_condensed"),
        )
        if value:
            self._append_archive(Path(value))
            self.refresh_inputs()

    def _remove_archives(self) -> None:
        rows = sorted(
            {index.row() for index in self.archive_table.selectedIndexes()},
            reverse=True,
        )
        for row in rows:
            self.archive_table.removeRow(row)
        self._refresh_preview()

    def _candidate_stats(self, path: Path) -> tuple[int, int]:
        if not path.exists():
            return 0, 0
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
            templates = {
                str(row.get("template", "")).strip()
                for row in rows
                if str(row.get("template", "")).strip()
            }
            return len(rows), len(templates)
        except Exception:
            return 0, 0

    def _validation_state_for_archive(self, archive: Path) -> str:
        parent = archive.parent
        candidates = [
            parent / "validation.csv",
            parent / f"{archive.name}_validation.csv",
        ]
        for path in candidates:
            if path.exists():
                return path.name
        return "未发现"

    def refresh_inputs(self) -> None:
        if not hasattr(self, "archive_table"):
            return

        candidate_path = self._resolve(self.candidates_edit.text())
        rows, templates = self._candidate_stats(candidate_path)
        self.candidate_rows_label.setText(f"记录：{rows if candidate_path.exists() else '—'}")
        self.template_count_label.setText(
            f"组成模板：{templates if candidate_path.exists() else '—'}"
        )
        self.candidate_input_state.setText("Ready" if candidate_path.exists() else "文件不存在")

        for row in range(self.archive_table.rowCount()):
            item = self.archive_table.item(row, 0)
            if item is None:
                continue
            raw = str(item.data(Qt.UserRole) or item.text())
            archive = Path(raw)
            if not archive.is_absolute():
                archive = self._project_root() / archive

            if archive.exists() and archive.is_dir():
                json_count = len(list(archive.glob("*.json")))
                validation = self._validation_state_for_archive(archive)
                state = "Ready" if json_count else "目录为空"
            else:
                json_count = 0
                validation = "—"
                state = "目录不存在"

            self.archive_table.setItem(row, 1, QTableWidgetItem(str(json_count)))
            self.archive_table.setItem(row, 2, QTableWidgetItem(validation))
            self.archive_table.setItem(row, 3, QTableWidgetItem(state))

        self._refresh_preview()

    def _match_argv(self) -> list[str]:
        argv = [
            "structure-match",
            "--candidates",
            self.candidates_edit.text().strip(),
        ]

        for archive in self._archive_paths():
            display = archive
            try:
                display = self._display_path(Path(archive))
            except Exception:
                pass
            argv.extend(["--condensed-dir", display])

        argv.extend(
            [
                "--min-x-elements",
                self.min_x_edit.text().strip() or "2",
                "--output",
                self.groups_output.text().strip(),
                "--summary",
                self.summary_output.text().strip(),
            ]
        )
        return argv

    def _refresh_preview(self) -> None:
        if hasattr(self, "match_preview"):
            self.match_preview.setPlainText(shlex.join(["ss-screen", *self._match_argv()]))

    def _run_match(self) -> None:
        if not self._check_required(
            [
                ("组成候选表", self.candidates_edit.text()),
                ("结构描述归档", ", ".join(self._archive_paths())),
                ("Structure Groups 输出", self.groups_output.text()),
                ("阶段汇总", self.summary_output.text()),
            ]
        ):
            return

        try:
            min_x = int(self.min_x_edit.text().strip())
            if min_x < 1:
                raise ValueError
        except ValueError:
            QMessageBox.warning(
                self,
                "参数错误",
                "“最少可替换元素数”必须是大于等于 1 的整数。",
            )
            return

        self.run_requested.emit(
            self._match_argv(),
            "结构匹配与材料分组",
        )

    # ------------------------------------------------------------------
    # Results tab
    # ------------------------------------------------------------------

    def _build_results_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(7)

        summary_box = QGroupBox("Match Summary / 匹配汇总")
        summary_grid = QFormLayout(summary_box)
        summary_grid.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.result_candidate_rows = QLabel("—")
        self.result_template_count = QLabel("—")
        self.result_group_count = QLabel("0")
        self.result_grouped_members = QLabel("0")
        self.result_missing = QLabel("—")
        self.result_missing_materials = QLabel("—")
        self.result_invalid = QLabel("—")
        self.result_min_x = QLabel("—")
        self.result_scope = QLabel("尚未运行")
        self.result_scope.setWordWrap(True)
        summary_grid.addRow("本次数据覆盖", self.result_scope)

        summary_grid.addRow("候选记录", self.result_candidate_rows)
        summary_grid.addRow("组成模板", self.result_template_count)
        summary_grid.addRow("Structure Groups", self.result_group_count)
        summary_grid.addRow("组内成员记录数（可重复）", self.result_grouped_members)
        summary_grid.addRow("暂无描述的材料（去重）", self.result_missing_materials)
        summary_grid.addRow("缺失描述（候选记录数）", self.result_missing)
        summary_grid.addRow("无效描述（候选记录数）", self.result_invalid)
        summary_grid.addRow("min X elements", self.result_min_x)
        layout.addWidget(summary_box)

        groups_box = QGroupBox("Structure Groups / 结构组")
        groups_layout = QVBoxLayout(groups_box)

        self.groups_table = QTableWidget(0, 6)
        self.groups_table.setHorizontalHeaderLabels(
            [
                "Group",
                "Members",
                "Compositions",
                "X Elements",
                "Material IDs",
                "Band Gaps",
            ]
        )
        self.groups_table.verticalHeader().setVisible(False)
        self.groups_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.groups_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.groups_table.horizontalHeader().setStretchLastSection(True)
        self.groups_table.setColumnWidth(0, 90)
        self.groups_table.setColumnWidth(1, 75)
        self.groups_table.setColumnWidth(2, 220)
        self.groups_table.setColumnWidth(3, 145)
        self.groups_table.setColumnWidth(4, 270)
        self.groups_table.setMinimumHeight(245)
        self.groups_table.itemSelectionChanged.connect(self._refresh_group_detail)
        groups_layout.addWidget(self.groups_table)
        layout.addWidget(groups_box, 1)

        detail_box = QGroupBox("Selected Group / 组内成员")
        detail_layout = QVBoxLayout(detail_box)

        self.group_detail_title = QLabel("未选择结构组")
        self.group_detail_title.setObjectName("sectionLabel")
        detail_layout.addWidget(self.group_detail_title)

        self.member_table = QTableWidget(0, 5)
        self.member_table.setHorizontalHeaderLabels(
            ["#", "Composition", "X Element", "Material ID", "Band Gap"]
        )
        self.member_table.verticalHeader().setVisible(False)
        self.member_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.member_table.horizontalHeader().setStretchLastSection(True)
        self.member_table.setMinimumHeight(125)
        self.member_table.setMaximumHeight(190)
        detail_layout.addWidget(self.member_table)

        self.group_algorithm_note = QLabel(
            "Material ID 可能来自不同数据源；GUI 不依据历史字段名 mp_ids 推断其全部来自 Materials Project。"
        )
        self.group_algorithm_note.setWordWrap(True)
        self.group_algorithm_note.setObjectName("optionHelp")
        detail_layout.addWidget(self.group_algorithm_note)

        layout.addWidget(detail_box)

        actions = QHBoxLayout()
        refresh = QPushButton("刷新结果")
        refresh.clicked.connect(self.refresh_results)
        open_groups = QPushButton("打开 groups.json")
        open_groups.clicked.connect(self._open_groups_file)
        open_summary = QPushButton("打开 summary.json")
        open_summary.clicked.connect(self._open_summary_file)
        actions.addWidget(refresh)
        actions.addWidget(open_groups)
        actions.addWidget(open_summary)
        actions.addStretch(1)
        layout.addLayout(actions)

        return _wrap_in_scroll_area(page, min_width=820, min_height=760)

    def _load_group_records(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []

        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]

        # Support the column-oriented DataFrame JSON layout accepted by the
        # real SS-Screen loader.
        if isinstance(data, dict) and "entry_idx" in data:
            columns = {key: value for key, value in data.items() if isinstance(value, dict)}
            row_keys: list[str] = []
            seen: set[str] = set()
            for values in columns.values():
                for key in values:
                    key_text = str(key)
                    if key_text not in seen:
                        seen.add(key_text)
                        row_keys.append(key_text)

            def sort_key(value: str):
                try:
                    return (0, int(value))
                except ValueError:
                    return (1, value)

            records: list[dict[str, Any]] = []
            for row_key in sorted(row_keys, key=sort_key):
                record = {}
                for column, values in columns.items():
                    if row_key in values:
                        record[column] = values[row_key]
                    elif str(row_key) in values:
                        record[column] = values[str(row_key)]
                records.append(record)
            return records

        return []

    def _load_summary(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _compact_list(self, value: Any, limit: int = 5) -> str:
        if value is None:
            return ""
        if not isinstance(value, (list, tuple)):
            return str(value)
        parts = [str(item) for item in value]
        if len(parts) <= limit:
            return ", ".join(parts)
        return ", ".join(parts[:limit]) + f" … (+{len(parts) - limit})"

    def refresh_results(self) -> None:
        if not hasattr(self, "groups_table"):
            return

        groups_path = self._resolve(self.groups_output.text())
        summary_path = self._resolve(self.summary_output.text())

        try:
            records = self._load_group_records(groups_path)
        except Exception as exc:
            records = []
            self.result_group_count.setText(f"读取失败：{exc}")
        self._last_group_records = records

        summary = self._load_summary(summary_path)

        if "candidate_materials" in summary:
            scope = "部分结果" if summary.get("partial_run") else "描述覆盖完整"
            self.result_scope.setText(
                f"{scope}：{summary['available_materials']} / {summary['candidate_materials']} "
                f"个材料有可用描述（{summary['description_coverage']:.1%}）"
            )
        else:
            self.result_scope.setText("未记录覆盖率" if summary else "尚未运行")
        self.result_candidate_rows.setText(str(summary.get("candidate_rows", "—")))
        self.result_template_count.setText(str(summary.get("template_count", "—")))
        self.result_group_count.setText(str(summary.get("group_count", len(records))))
        self.result_grouped_members.setText(
            str(
                summary.get(
                    "grouped_members",
                    sum(int(row.get("group_size", 0) or 0) for row in records),
                )
            )
        )
        self.result_missing.setText(str(summary.get("missing_descriptions", "—")))
        self.result_missing_materials.setText(str(summary.get("missing_materials", "—")))
        self.result_invalid.setText(str(summary.get("invalid_descriptions", "—")))
        self.result_min_x.setText(str(summary.get("min_x_elements", "—")))

        self.groups_table.setRowCount(0)
        for index, record in enumerate(records):
            row = self.groups_table.rowCount()
            self.groups_table.insertRow(row)

            group_id = f"G{index + 1:04d}"
            group_size = record.get(
                "group_size",
                len(record.get("mp_ids", []) or []),
            )

            values = [
                group_id,
                str(group_size),
                self._compact_list(record.get("compositions", [])),
                self._compact_list(record.get("X_element", [])),
                self._compact_list(record.get("mp_ids", [])),
                self._compact_list(record.get("band_gaps", [])),
            ]
            for col, value in enumerate(values):
                self.groups_table.setItem(row, col, QTableWidgetItem(value))

        if records:
            self.groups_table.selectRow(0)
        else:
            self.member_table.setRowCount(0)
            self.group_detail_title.setText("未生成结构组")

    def _refresh_group_detail(self) -> None:
        rows = self.groups_table.selectionModel().selectedRows()
        if not rows:
            return

        row_index = rows[0].row()
        if row_index >= len(self._last_group_records):
            return

        record = self._last_group_records[row_index]
        group_id = f"G{row_index + 1:04d}"
        compositions = list(record.get("compositions", []) or [])
        x_elements = list(record.get("X_element", []) or [])
        material_ids = list(record.get("mp_ids", []) or [])
        band_gaps = list(record.get("band_gaps", []) or [])

        member_count = max(
            len(compositions),
            len(x_elements),
            len(material_ids),
            len(band_gaps),
            int(record.get("group_size", 0) or 0),
        )

        self.group_detail_title.setText(
            f"{group_id} · {member_count} members · "
            f"A elements: {self._compact_list(record.get('A_elements', []))}"
        )

        self.member_table.setRowCount(member_count)
        for i in range(member_count):
            values = [
                str(i + 1),
                str(compositions[i]) if i < len(compositions) else "",
                str(x_elements[i]) if i < len(x_elements) else "",
                str(material_ids[i]) if i < len(material_ids) else "",
                str(band_gaps[i]) if i < len(band_gaps) else "",
            ]
            for col, value in enumerate(values):
                self.member_table.setItem(
                    i,
                    col,
                    QTableWidgetItem(value),
                )

    def _open_groups_file(self) -> None:
        path = self._resolve(self.groups_output.text())
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.information(
                self,
                "结果不存在",
                f"尚未生成结构组文件：\n{path}",
            )

    def _open_summary_file(self) -> None:
        path = self._resolve(self.summary_output.text())
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.information(
                self,
                "结果不存在",
                f"尚未生成阶段汇总：\n{path}",
            )

    def select_section(self, section: str) -> None:
        if section in {"input", "rules", "match"}:
            self.tabs.setCurrentIndex(0)
            self.refresh_inputs()
        else:
            self.tabs.setCurrentIndex(1)
            self.refresh_results()


@dataclass
class ProjectRecord:
    """One project shown as a top-level root in the project explorer."""

    name: str
    path: Path
    # .ssproject 中保存的 GUI / command 参数快照。
    settings: dict[str, Any] | None = None


# Engineering-style logical groups. Stage numbering remains unchanged so it
# still maps 1:1 to the SS-Screen project directories and CLI workflow.
STAGE_GROUPS = (
    ("数据与结构", ("01", "02", "03", "04")),
    ("电子结构", ("05", "06")),
    ("合金模型", ("07", "08")),
    ("稳定性分析", ("09", "10", "11")),
    ("结果与报告", ("12", "13")),
)

COMPOSITION_SCREEN_OBJECTS = (
    ("input", "筛选输入"),
    ("rules", "筛选规则"),
    ("candidates", "Composition Candidates / 候选材料表"),
    ("summary", "Screening Summary / 筛选统计"),
    ("structures", "候选结构 / candidates.df（供 03 输入）"),
)

STRUCTURE_ARCHIVE_OBJECTS = (
    ("input", "输入结构"),
    ("archive", "结构描述库"),
    ("manifest", "Manifest"),
    ("index", "Index"),
    ("validation", "Validation"),
)

STRUCTURE_MATCH_OBJECTS = (
    ("input", "匹配输入"),
    ("rules", "匹配规则"),
    ("groups", "Structure Groups / 结构组"),
    ("summary", "Summary"),
)



def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except Exception:
        return []


def _row_by_pair_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for index, row in enumerate(rows):
        key = row.get("pair_index") or row.get("") or str(index)
        if key and key not in result:
            result[key] = row
    return result


def _read_jsonl_dicts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    record = json.loads(line)
                    if isinstance(record, dict):
                        rows.append(record)
    except Exception:
        return []
    return rows


def _compact_value(value: object, *, max_len: int = 96) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


_RECOMMENDATION_LABELS_ZH = {
    "promising": "优先验证",
    "uncertain": "待确认",
    "low-priority": "低优先级",
    "stable": "稳定",
    "unstable": "不稳定",
    "metastable_within_cutoff": "阈值内亚稳态",
    "uncertain_incomplete_competing_set": "待确认（竞争相不完整）",
    "api": "在线接口",
    "offline": "离线数据库",
    "gap": "带隙",
    "mixing": "混合焓",
    "phonon": "声子",
    "phase": "竞争相",
    "defects": "缺陷",
    "mlp": "机器学习势",
    "a": "端元 A",
    "b": "端元 B",
    "missing": "缺失",
    "failed": "失败",
    "not_converged": "未收敛",
    "missing_source": "缺少数据来源",
    "ambiguous_records": "存在多条歧义记录",
    "pair_method_conflict": "配对与带隙计算方法不一致",
    "ambiguous_method": "计算方法存在歧义",
    "missing_method": "缺少计算方法",
    "value_mismatch": "数值不一致",
    "directness_mismatch": "直接或间接带隙标记不一致",
    "both_endmembers_indirect": "两个端元均为间接带隙",
    "above_low_priority_threshold": "超过低优先级阈值",
    "borderline": "处于边界范围",
    "nac_not_applied": "未应用非解析修正",
    "incomplete_competing_set": "竞争相集合不完整",
    "offline_snapshot_scope": "仅覆盖离线数据库快照",
    "unknown_signal": "未知判据",
    "risky": "存在风险",
    "model_sha256_mismatch": "模型校验值不一致",
    "complete_or_revalidate_high_fidelity_endpoint_gaps": "补齐或重新验证高精度端元带隙",
    "run_compatible_sqs_relaxation_and_mixing_enthalpy": "使用一致设置完成合金弛豫和混合焓计算",
    "run_converged_phonon_screening": "完成收敛的声子筛查",
    "complete_same_mlip_competing_phase_hull": "使用同一机器学习势补齐竞争相凸包",
    "complete_consistent_defect_screening": "使用一致设置完成缺陷筛查",
    "recompute_stability_evidence_with_one_mlp_model": "使用同一模型重新计算稳定性证据",
    "verify_imaginary_modes_with_larger_supercells_or_dft": "使用更大超胞或 DFT 复核虚频",
    "verify_high_mixing_penalty_before_further_investment": "进一步研究前先复核较高混合焓",
    "test_additional_sqs_compositions_and_energy_convergence": "比较更多合金组分并检查能量收敛",
    "verify_competing_phases_and_hull_with_consistent_dft": "使用一致的 DFT 设置复核竞争相和凸包",
    "verify_borderline_hull_distance_with_consistent_dft": "使用一致的 DFT 设置复核边界凸包距离",
    "perform_consistent_high_fidelity_dft_validation": "使用一致设置开展高精度 DFT 验证",
    "test_multiple_sqs_compositions_and_supercell_convergence": "比较多个 SQS 组分并检查超胞收敛",
    "consider_defect_screening_for_priority_candidates": "对优先候选开展缺陷筛查",
    "deprioritize_unless_the_negative_signal_is_resolved": "负面信号解决前降低研究优先级",
    "resolve_missing_or_conflicting_evidence_before_ranking": "排序前补齐缺失证据并解决证据冲突",
}


def _recommendation_label_zh(value: object) -> str:
    """Translate display labels while retaining unrecognized source values."""
    text = "" if value is None else str(value)
    return _RECOMMENDATION_LABELS_ZH.get(
        text, "：".join(_RECOMMENDATION_LABELS_ZH.get(part, part) for part in text.split(":"))
    )


def _recommendation_list_zh(value: object) -> str:
    """Render the recommendation CSV's JSON code lists as Chinese text."""
    if value is None or value == "":
        return "—"
    try:
        entries = json.loads(str(value))
    except (TypeError, ValueError):
        return _recommendation_label_zh(value)
    if not isinstance(entries, list):
        return _recommendation_label_zh(value)
    return "；".join(_recommendation_label_zh(entry) for entry in entries) or "—"


class RecommendationReportPage(QWidget):
    """Readable Stage 12 report and evidence view for presentation/use."""

    run_requested = Signal(list, str)

    def __init__(self, project_provider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_provider = project_provider

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(7)

        header = QHBoxLayout()
        title = QLabel("综合推荐与结果报告")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.badge = QLabel("阶段 12")
        self.badge.setObjectName("stateBadge")
        header.addWidget(self.badge)
        root.addLayout(header)

        subtitle = QLabel(
            "这里汇总最终推荐结果、Markdown 报告和各阶段证据数值。"
            "推荐等级只用于后续复核优先级，不等同于材料已经被证明稳定或可合成。"
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("pageDescription")
        root.addWidget(subtitle)

        summary_box = QGroupBox("汇总")
        summary_form = QFormLayout(summary_box)
        summary_form.setContentsMargins(8, 10, 8, 8)
        self.generated_label = QLabel("-")
        self.count_label = QLabel("-")
        self.class_label = QLabel("-")
        self.evidence_label = QLabel("-")
        for label in (
            self.generated_label,
            self.count_label,
            self.class_label,
            self.evidence_label,
        ):
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        summary_form.addRow("生成时间", self.generated_label)
        summary_form.addRow("推荐数量", self.count_label)
        summary_form.addRow("分类统计", self.class_label)
        summary_form.addRow("证据等级", self.evidence_label)
        root.addWidget(summary_box)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        table_page = QWidget()
        table_layout = QVBoxLayout(table_page)
        table_layout.setContentsMargins(0, 4, 0, 0)
        self.recommendation_table = QTableWidget(0, 17)
        self.recommendation_table.setHorizontalHeaderLabels(
            [
                "排名",
                "推荐分类",
                "证据等级",
                "端元配对",
                "B 组分比例",
                "端元 A/B 带隙 (eV)",
                "混合焓 (meV/原子)",
                "声子稳定性",
                "最低频率 (THz)",
                "凸包距离 (eV/原子)",
                "相稳定性判定",
                "MP 数据来源",
                "结构编号",
                "合金结构文件",
                "端元结构文件",
                "风险提示",
                "下一步建议",
            ]
        )
        self.recommendation_table.verticalHeader().setVisible(False)
        self.recommendation_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.recommendation_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.recommendation_table.setAlternatingRowColors(True)
        self.recommendation_table.setMinimumHeight(260)
        self.recommendation_table.horizontalHeader().setStretchLastSection(True)
        for column, width in enumerate(
            [56, 100, 90, 120, 100, 170, 165, 110, 150, 170, 130, 130, 210, 230, 230, 260, 280]
        ):
            self.recommendation_table.setColumnWidth(column, width)
        table_layout.addWidget(self.recommendation_table)
        self.tabs.addTab(table_page, "推荐候选")

        report_page = QWidget()
        report_layout = QVBoxLayout(report_page)
        report_layout.setContentsMargins(0, 4, 0, 0)
        self.report_view = QTextBrowser()
        self.report_view.setOpenExternalLinks(False)
        self.report_view.setObjectName("reportViewer")
        report_layout.addWidget(self.report_view)
        self.tabs.addTab(report_page, "Markdown 报告")

        root.addWidget(self.tabs, 1)

        actions = QHBoxLayout()
        refresh = QPushButton("刷新结果")
        refresh.clicked.connect(self.refresh)
        open_report = QPushButton("打开 Markdown")
        open_report.clicked.connect(self._open_report)
        run = QPushButton("生成综合推荐")
        run.setObjectName("primaryButton")
        run.clicked.connect(self._run_recommend)
        actions.addWidget(refresh)
        actions.addStretch(1)
        actions.addWidget(open_report)
        actions.addWidget(run)
        root.addLayout(actions)

        self.refresh()

    def _project_root(self) -> Path:
        return Path(self.project_provider()).expanduser().resolve()

    def _path(self, relative: str) -> Path:
        return imported_artifact(self._project_root(), relative)

    def _summary(self) -> dict[str, Any]:
        path = self._path("12_recommend/recommendation_summary.json")
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def refresh(self) -> None:
        summary = self._summary()
        self.generated_label.setText(str(summary.get("generated_at") or "-"))
        self.count_label.setText(str(summary.get("recommendation_count") or "0"))
        self.class_label.setText(
            "；".join(
                f"{_recommendation_label_zh(label)}：{count}"
                for label, count in (summary.get("classification_counts") or {}).items()
            )
            or "—"
        )
        self.evidence_label.setText(
            "；".join(
                f"{label}：{count}"
                for label, count in (summary.get("evidence_level_counts") or {}).items()
            )
            or "—"
        )

        recommendations = _read_csv_dicts(self._path("12_recommend/recommendations.csv"))
        pairs = _row_by_pair_index(_read_csv_dicts(self._path("06_pair/final_pairs.csv")))
        mixing = _row_by_pair_index(_read_csv_dicts(self._path("09_mixing/mixing_enthalpy.csv")))
        phonons = _row_by_pair_index(_read_csv_dicts(self._path("10_phonon/phonon_summary.csv")))
        phase = _row_by_pair_index(_read_csv_dicts(self._path("11_phase/phase_stability.csv")))
        sqs_manifest = _row_by_pair_index(
            [
                {key: str(value) for key, value in row.items()}
                for row in _read_jsonl_dicts(self._path("07_sqs/sqs_manifest.jsonl"))
            ]
        )

        self.recommendation_table.setRowCount(0)
        for rec in recommendations:
            pair_key = rec.get("pair_index", "")
            pair = pairs.get(pair_key, {})
            mix = mixing.get(pair_key, {})
            phonon = phonons.get(pair_key, {})
            hull = phase.get(pair_key, {})
            sqs = sqs_manifest.get(pair_key, {})
            endmembers = " / ".join(
                item
                for item in (
                    sqs.get("endpoint_a_structure_path"),
                    sqs.get("endpoint_b_structure_path"),
                )
                if item
            )

            values = [
                rec.get("rank"),
                rec.get("classification"),
                rec.get("evidence_level"),
                f"{rec.get('comp_a') or pair.get('comp_a')} / {rec.get('comp_b') or pair.get('comp_b')}",
                rec.get("actual_fraction_b") or rec.get("target_fraction_b"),
                f"{rec.get('gap_a_eV') or pair.get('gap_a')} / {rec.get('gap_b_eV') or pair.get('gap_b')}",
                rec.get("mixing_enthalpy_meV_per_atom") or mix.get("mixing_enthalpy_meV_per_atom"),
                rec.get("dynamical_status") or phonon.get("dynamical_status"),
                rec.get("minimum_mesh_frequency_THz") or phonon.get("minimum_mesh_frequency_THz"),
                rec.get("energy_above_hull_eV_per_atom")
                or hull.get("energy_above_hull_eV_per_atom"),
                rec.get("hull_signal") or hull.get("hull_signal"),
                rec.get("mp_source_backend") or hull.get("mp_source_backend"),
                rec.get("structure_id") or phonon.get("structure_id") or hull.get("structure_id"),
                sqs.get("structure_path"),
                endmembers,
                rec.get("risks"),
                rec.get("recommended_next_steps"),
            ]
            row_index = self.recommendation_table.rowCount()
            self.recommendation_table.insertRow(row_index)
            for column, value in enumerate(values):
                display = value
                if column in (1, 7, 10, 11):
                    display = _recommendation_label_zh(value)
                elif column in (15, 16):
                    display = _recommendation_list_zh(value)
                item = QTableWidgetItem(_compact_value(display))
                item.setToolTip("" if display is None else str(display))
                item.setData(Qt.UserRole, value)
                self.recommendation_table.setItem(row_index, column, item)

        report_path = self._path("12_recommend/recommendation_report.md")
        if report_path.exists():
            text = report_path.read_text(encoding="utf-8", errors="replace")
            try:
                self.report_view.setMarkdown(text)
            except AttributeError:
                self.report_view.setPlainText(text)
        else:
            self.report_view.setPlainText(
                "尚未生成 recommendation_report.md。点击“生成综合推荐”后刷新。"
            )

    def _open_report(self) -> None:
        path = self._path("12_recommend/recommendation_report.md")
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.information(self, "报告不存在", f"尚未生成：\n{path}")

    def _run_recommend(self) -> None:
        argv = [
            "recommend",
            "--pairs",
            "06_pair/final_pairs.csv",
            "--gap-results",
            "05_gap/results_normalized.csv",
            "--mixing-enthalpy",
            "09_mixing/mixing_enthalpy.csv",
            "--phonons",
            "10_phonon/phonon_summary.csv",
            "--phase-stability",
            "11_phase/phase_stability.csv",
            "--output",
            "12_recommend/recommendations.csv",
            "--report",
            "12_recommend/recommendation_report.md",
            "--summary",
            "12_recommend/recommendation_summary.json",
        ]
        self.run_requested.emit(argv, "综合推荐")


class Dashboard(QWidget):
    """Dense project overview, closer to a CAE workbench than a slide dashboard."""

    def __init__(self, project_provider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_provider = project_provider

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)

        header = QHBoxLayout()
        self.title = QLabel("工程概览")
        self.title.setObjectName("pageTitle")
        header.addWidget(self.title)
        header.addStretch(1)
        self.state_badge = QLabel("READY")
        self.state_badge.setObjectName("stateBadge")
        header.addWidget(self.state_badge)
        layout.addLayout(header)

        self.project_path = QLabel("")
        self.project_path.setObjectName("breadcrumb")
        self.project_path.setWordWrap(False)
        layout.addWidget(self.project_path)

        info_box = QGroupBox("Project / 工程")
        info_form = QFormLayout(info_box)
        info_form.setContentsMargins(10, 10, 10, 8)
        info_form.setHorizontalSpacing(14)
        self.project_name_value = QLabel("-")
        self.project_root_value = QLabel("-")
        self.project_root_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.stage_value = QLabel(str(len(STAGES) - 1))
        self.artifact_value = QLabel("0")
        info_form.addRow("工程名称", self.project_name_value)
        info_form.addRow("工作目录", self.project_root_value)
        info_form.addRow("标准阶段", self.stage_value)
        info_form.addRow("已有产物", self.artifact_value)
        layout.addWidget(info_box)

        workflow_box = QGroupBox("Workflow Status / 工作流状态")
        workflow_layout = QVBoxLayout(workflow_box)
        workflow_layout.setContentsMargins(6, 8, 6, 6)

        self.table = QTableWidget(len(STAGES) - 1, 5)
        self.table.setHorizontalHeaderLabels(["Stage", "模块", "工作目录", "状态", "产物数"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 58)
        self.table.setColumnWidth(1, 145)
        self.table.setColumnWidth(2, 190)

        for row, (sid, name, directory) in enumerate(STAGES[1:]):
            self.table.setItem(row, 0, QTableWidgetItem(sid))
            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.table.setItem(row, 2, QTableWidgetItem(directory))

        workflow_layout.addWidget(self.table)
        layout.addWidget(workflow_box, 1)

        action_row = QHBoxLayout()
        self.hint = QLabel("双击或展开左侧工程树进入具体命令。")
        self.hint.setObjectName("smallLabel")
        action_row.addWidget(self.hint)
        action_row.addStretch(1)
        refresh = QPushButton("刷新状态")
        refresh.clicked.connect(self.refresh)
        action_row.addWidget(refresh)
        layout.addLayout(action_row)

        self.refresh()

    def refresh(self) -> None:
        root = self.project_provider()
        self.title.setText(f"{root.name} · 工程概览")
        self.project_path.setText(str(root))
        self.project_name_value.setText(root.name)
        self.project_root_value.setText(str(root))

        total_artifacts = 0
        for row, (_sid, _name, directory) in enumerate(STAGES[1:]):
            path = root / directory
            if not path.exists():
                status = "未开始"
                count = 0
            else:
                try:
                    count = sum(1 for _ in path.iterdir())
                except OSError:
                    count = 0
                status = "已建立" if count == 0 else "有产物"
            total_artifacts += count
            self.table.setItem(row, 3, QTableWidgetItem(status))
            self.table.setItem(row, 4, QTableWidgetItem(str(count)))

        self.artifact_value.setText(str(total_artifacts))


class InspectorPanel(QWidget):
    """Selection/property inspector, similar to engineering CAE applications."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ssh_probe = QProcess(self)
        self.ssh_probe.setProcessChannelMode(QProcess.MergedChannels)
        self.ssh_probe.finished.connect(self._ssh_probe_finished)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)

        title = QLabel("属性")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        selection_box = QGroupBox("Selection / 当前选择")
        form = QFormLayout(selection_box)
        form.setContentsMargins(8, 10, 8, 8)
        form.setHorizontalSpacing(8)
        self.type_value = QLabel("工程")
        self.name_value = QLabel("-")
        self.name_value.setWordWrap(True)
        self.path_value = QLabel("-")
        self.path_value.setWordWrap(True)
        self.status_value = QLabel("-")
        form.addRow("类型", self.type_value)
        form.addRow("名称", self.name_value)
        form.addRow("路径", self.path_value)
        form.addRow("状态", self.status_value)
        layout.addWidget(selection_box)

        runtime_box = QGroupBox("Connection / 连接设置")
        runtime_form = QFormLayout(runtime_box)
        runtime_form.setContentsMargins(8, 10, 8, 8)
        self.runtime_backend = QComboBox()
        self.runtime_backend.addItem("Windows Python / 当前解释器", ("windows", ""))
        self.runtime_backend.addItem("WSL Python / 自动选择", ("wsl-auto", ""))
        self.runtime_backend.addItem("WSL Python / .venv", ("wsl", WSL_VENV_ACTIVATE))
        self.runtime_backend.addItem("WSL Python / .venv-mlp", ("wsl", WSL_MLP_VENV_ACTIVATE))
        self.runtime_backend.setCurrentIndex(1)
        runtime_form.addRow("运行后端", self.runtime_backend)

        self.wsl_root = QLineEdit()
        self.wsl_root.setPlaceholderText("留空 = 自动把当前工程路径转换为 /mnt/<drive>/...")
        runtime_form.addRow("WSL 工程路径", self.wsl_root)

        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("MP_API_KEY（可选）")
        runtime_form.addRow("MP API Key", self.api_key)
        note = QLabel(
            "MP API Key 仅注入当前任务进程，不写入命令或项目文件。"
            "WSL 自动选择会用 .venv 跑前中段/SQS，用 .venv-mlp 跑 MACE、phonon 和 phase-diagram。"
        )
        note.setWordWrap(True)
        note.setObjectName("optionHelp")
        runtime_form.addRow("", note)
        layout.addWidget(runtime_box)

        ssh_box = QGroupBox("SSH Server / 远程服务器验证")
        ssh_form = QFormLayout(ssh_box)
        ssh_form.setContentsMargins(8, 10, 8, 8)
        self.ssh_host = QLineEdit()
        self.ssh_host.setPlaceholderText("服务器域名或IP")
        self.ssh_user = QLineEdit()
        self.ssh_user.setPlaceholderText("用户名")
        self.ssh_port = QLineEdit("22")
        self.ssh_key = QLineEdit()
        self.ssh_key.setPlaceholderText("可选：SSH私钥路径")
        self.ssh_remote_root = QLineEdit()
        self.ssh_remote_root.setPlaceholderText("可选：服务器工程目录")
        ssh_form.addRow("服务器", self.ssh_host)
        ssh_form.addRow("用户名", self.ssh_user)
        ssh_form.addRow("端口", self.ssh_port)
        ssh_form.addRow("私钥", self.ssh_key)
        ssh_form.addRow("远程目录", self.ssh_remote_root)
        self.ssh_test = QPushButton("验证SSH与远程环境")
        self.ssh_test.clicked.connect(self._test_ssh)
        ssh_form.addRow("", self.ssh_test)
        self.ssh_status = QLabel("未验证。只执行只读版本和路径探测，不提交计算任务。")
        self.ssh_status.setWordWrap(True)
        self.ssh_status.setObjectName("optionHelp")
        ssh_form.addRow("状态", self.ssh_status)
        layout.addWidget(ssh_box)

        layout.addStretch(1)

    def _test_ssh(self) -> None:
        host = self.ssh_host.text().strip()
        user = self.ssh_user.text().strip()
        if not host:
            QMessageBox.information(self, "SSH验证", "请先填写服务器地址。")
            return
        target = f"{user}@{host}" if user else host
        args = [
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=8",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-p",
            self.ssh_port.text().strip() or "22",
        ]
        key = self.ssh_key.text().strip()
        if key:
            args.extend(["-i", key])
        remote_root = self.ssh_remote_root.text().strip()
        probe = (
            "printf 'SSH_OK\\n'; "
            "python3 --version 2>&1; "
            "if command -v ss-screen >/dev/null 2>&1; then ss-screen --version; "
            "else printf 'SS_SCREEN_NOT_FOUND\\n'; fi"
        )
        if remote_root:
            probe += f"; if test -d {shlex.quote(remote_root)}; then printf 'REMOTE_ROOT_OK\\n'; else printf 'REMOTE_ROOT_MISSING\\n'; fi"
        args.extend([target, probe])
        self.ssh_status.setText(f"正在验证 {target} …")
        self.ssh_test.setEnabled(False)
        self.ssh_probe.start("ssh", args)

    def _ssh_probe_finished(self, exit_code: int, _exit_status) -> None:
        output = (
            bytes(self.ssh_probe.readAllStandardOutput()).decode("utf-8", errors="replace").strip()
        )
        self.ssh_test.setEnabled(True)
        if exit_code == 0 and "SSH_OK" in output:
            self.ssh_status.setText("验证成功：\n" + output)
        else:
            self.ssh_status.setText(f"验证失败（退出码 {exit_code}）：\n{output or '无输出'}")

    def set_selection(
        self,
        *,
        item_type: str,
        name: str,
        path: str,
        status: str = "",
    ) -> None:
        self.type_value.setText(item_type)
        self.name_value.setText(name)
        self.path_value.setText(path)
        self.status_value.setText(status or "-")


class DocumentStack(QStackedWidget):
    """Let the image page fit the viewport without hidden forms' height hints."""

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        if isinstance(self.currentWidget(), PhaseResultsPage):
            return False
        return super().hasHeightForWidth()

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        if isinstance(self.currentWidget(), PhaseResultsPage):
            return self.currentWidget().minimumSizeHint().height()
        return super().heightForWidth(width)


class MainWindow(QMainWindow):
    """SS-Screen desktop engineering workbench with multi-project roots."""

    def __init__(self, project_dir: str | None = None, *, settings: QSettings | None = None) -> None:
        super().__init__()
        self._display_settings = (
            settings if settings is not None else QSettings("SS-Screen", "Desktop")
        )
        self._font_size = font_size(self._display_settings.value(FONT_SETTINGS_KEY, DEFAULT_FONT_SIZE))
        self.setWindowTitle(APP_TITLE)
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        self.setMinimumSize(
            min(960, available.width()) if available else 960,
            min(600, available.height()) if available else 600,
        )
        self.resize(
            min(1600, available.width()) if available else 1600,
            min(1000, available.height()) if available else 1000,
        )

        self._pages: dict[
            tuple[str, ...],
            CommandPage | GapBundlePage | GapCollectPage | WavelengthPairPage | SqsPage | RelaxPage | StabilityPage,
        ] = {}
        self._command_lookup = self._collect_commands()
        self._current_run: RunRecord | None = None
        self._gap_collection_run: tuple[Path, tuple[str, ...]] | None = None
        self._condense_stop_file: Path | None = None
        self._stop_requested = False
        self._handoff_after_stop = False
        self._close_after_stop = False

        self._projects: list[ProjectRecord] = []
        self._active_project: ProjectRecord | None = None

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._process_error)

        self._build_ui()
        self._default_forms = capture_forms(self)
        self.workflow = WorkflowController(self)

        initial = Path(project_dir).expanduser() if project_dir else Path.cwd()
        initial = _find_project_root(initial)
        self._add_project(initial.resolve(), initialize=False, activate=True)
        self._apply_style()
        if self.workflow.settings.get("ten_micron_profile"):
            from ssscreen.gui.ten_micron_page import open_stage
            open_stage(self, 1)
        elif self.workflow.settings.get("workflow_stages"):
            self.workflow.show_parameters()

    def _collect_commands(self) -> dict[tuple[str, ...], click.Command]:
        lookup: dict[tuple[str, ...], click.Command] = {}
        for presentation in COMMANDS:
            command: click.Command = cli
            ok = True
            for part in presentation.command_path:
                if not isinstance(command, click.Group) or part not in command.commands:
                    ok = False
                    break
                command = command.commands[part]
            if ok:
                lookup[presentation.command_path] = command
        return lookup

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        self.view_menu = QMenu("视图", self)
        self.font_menu = self.view_menu.addMenu("界面字号")
        self.font_action_group = QActionGroup(self)
        self.font_action_group.setExclusive(True)
        self.font_size_actions = {}
        for points in range(MIN_FONT_SIZE, MAX_FONT_SIZE + 1):
            action = self.font_menu.addAction(f"{points} pt")
            action.setCheckable(True)
            action.setData(points)
            action.setChecked(points == self._font_size)
            self.font_action_group.addAction(action)
            self.font_size_actions[points] = action
        self.font_action_group.triggered.connect(
            lambda action: self._set_font_size(action.data())
        )
        self.font_menu.addSeparator()
        self.font_reset_action = self.font_menu.addAction("恢复默认字号（10 pt）")
        self.font_reset_action.triggered.connect(lambda: self._set_font_size(DEFAULT_FONT_SIZE))

        # Title strip: compact, neutral, engineering-software style.
        title_bar = QFrame()
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(10, 4, 10, 4)
        title_layout.setSpacing(8)

        product = QLabel("SS-SCREEN")
        product.setObjectName("productMark")
        title_layout.addWidget(product)
        subtitle = QLabel("新材料计算筛选工程工作台")
        subtitle.setObjectName("productSubtitle")
        subtitle.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title_layout.addWidget(subtitle)
        title_layout.addStretch(1)
        self.active_project_label = QLabel("当前工程：—")
        self.active_project_label.setObjectName("activeProjectLabel")
        self.active_project_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title_layout.addWidget(self.active_project_label)
        root.addWidget(title_bar)

        # Dense command toolbar.
        toolbar = QToolBar()
        self.command_toolbar = toolbar
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toolbar.setObjectName("toolBar")

        def add_tool(
            text,
            slot,
            object_name="toolButton",
            icon_name=None,
        ):
            action = (
                toolbar.addAction(app_icon(icon_name), text)
                if icon_name else toolbar.addAction(text)
            )
            action.triggered.connect(slot)
            action.setToolTip(text)
            toolbar.widgetForAction(action).setObjectName(object_name)
            return action

        add_tool(
            "新建工程",
            self.new_project,
            icon_name="new_project",
        )
        from ssscreen.gui.ten_micron_page import new_workspace

        add_tool("新建 / 打开 10 µm 工作区", lambda: new_workspace(self))

        add_tool(
            "打开工程文件.ssproject",
            self.open_project_file,
            icon_name="open_project_file",
        )

        add_tool(
            "保存 .ssproject",
            self.save_project_file,
            icon_name="save_project_file",
        )

        add_tool(
            "初始化",
            self.init_project,
            icon_name="initialize",
        )

        add_tool(
            "打开目录",
            self.open_project,
            icon_name="open_directory",
        )
        toolbar.addSeparator()
        add_tool(
            "从工作区移除",
            self.remove_active_project,
            icon_name="remove",
        )
        toolbar.addSeparator()
        self.view_action = toolbar.addAction("视图")
        self.view_action.setMenu(self.view_menu)
        self.view_button = toolbar.widgetForAction(self.view_action)
        self.view_button.setObjectName("toolButton")
        self.view_button.setPopupMode(QToolButton.InstantPopup)
        self.view_button.setToolTip("视图")
        self.run_state_label = QLabel("空闲")
        self.run_state_label.setObjectName("runStateLabel")
        self.run_progress = QProgressBar()
        self.run_progress.setObjectName("runProgress")
        self.run_progress.setRange(0, 0)
        self.run_progress.setFixedWidth(150)
        self.run_progress.setVisible(False)
        add_tool(
            "停止",
            self.stop_process,
            "stopButton",
            icon_name="stop",
        )
        self.addToolBar(Qt.TopToolBarArea, toolbar)

        workspace = QSplitter(Qt.Horizontal)
        workspace.setHandleWidth(4)

        # Left: Project Explorer
        project_panel = QFrame()
        project_panel.setObjectName("projectPanel")
        project_layout = QVBoxLayout(project_panel)
        project_layout.setContentsMargins(0, 0, 0, 0)
        project_layout.setSpacing(0)

        project_header = QLabel("工程树 / Project Explorer")
        project_header.setObjectName("panelHeader")
        project_header.setWordWrap(True)
        project_header.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        project_layout.addWidget(project_header)

        self.nav = QTreeWidget()
        self.nav.setObjectName("navigation")
        self.nav.setHeaderLabels(["工程 / 对象", "状态"])
        self.nav.setIconSize(QSize(18, 18))
        self.nav.setColumnWidth(0, 225)
        self.nav.setIndentation(17)
        self.nav.setRootIsDecorated(True)
        self.nav.setAlternatingRowColors(False)
        self.nav.itemClicked.connect(self._navigation_clicked)
        project_layout.addWidget(self.nav, 1)
        workspace.addWidget(project_panel)

        # Center: document/work area + output tabs.
        center_split = QSplitter(Qt.Vertical)
        center_split.setHandleWidth(4)
        center_split.setChildrenCollapsible(False)

        document_frame = QFrame()
        document_frame.setObjectName("documentFrame")
        document_frame.setMinimumHeight(320)
        document_layout = QVBoxLayout(document_frame)
        document_layout.setContentsMargins(0, 0, 0, 0)
        document_layout.setSpacing(0)

        document_header = QFrame()
        document_header.setObjectName("documentHeader")
        doc_head_layout = QHBoxLayout(document_header)
        doc_head_layout.setContentsMargins(8, 3, 8, 3)
        self.document_label = QLabel("工程概览")
        self.document_label.setObjectName("documentTitle")
        doc_head_layout.addWidget(self.document_label)
        doc_head_layout.addStretch(1)
        document_layout.addWidget(document_header)

        self.stack = DocumentStack()
        self.stack.currentChanged.connect(self._refresh_font_layout)
        self.dashboard = Dashboard(self.project_root)
        self.stack.addWidget(self.dashboard)

        self.dataset_source_page = DatasetSourcePage(self.project_root)
        self.dataset_source_page.run_requested.connect(self.run_command)
        self.stack.addWidget(self.dataset_source_page)

        self.composition_screen_page = CompositionScreenPage(self.project_root)
        self.composition_screen_page.run_requested.connect(self.run_command)
        self.stack.addWidget(self.composition_screen_page)

        self.structure_archive_page = StructureArchivePage(self.project_root)
        self.structure_archive_page.run_requested.connect(self.run_command)
        self.structure_archive_page.stop_requested.connect(self.stop_process)
        self.structure_archive_page.use_completed_requested.connect(self._use_completed_condense)
        self.stack.addWidget(self.structure_archive_page)
        self.composition_screen_page.structures_output.textChanged.connect(
            self._sync_composition_archive_input
        )
        self.structure_archive_page.df_follow_composition.toggled.connect(
            self._sync_composition_archive_input
        )

        self.structure_match_page = StructureMatchPage(self.project_root)
        self.structure_match_page.run_requested.connect(self.run_command)
        self.stack.addWidget(self.structure_match_page)
        self.structure_match_page.follow_stage03.toggled.connect(self._sync_structure_match_inputs)
        self.structure_archive_page.df_output_dir.textChanged.connect(self._sync_structure_match_inputs)
        self.composition_screen_page.candidates_output.textChanged.connect(self._sync_structure_match_inputs)

        self.structure_results_page = StructureResultsPage(self.project_root)
        self.stack.addWidget(self.structure_results_page)

        self.phonon_results_page = PhononResultsPage(self.project_root)
        self.stack.addWidget(self.phonon_results_page)

        self.phase_results_page = PhaseResultsPage(self.project_root, settings=self._display_settings)
        self.stack.addWidget(self.phase_results_page)

        self.recommendation_report_page = RecommendationReportPage(self.project_root)
        self.recommendation_report_page.run_requested.connect(self.run_command)
        self.stack.addWidget(self.recommendation_report_page)

        # Stage 13 is a local GUI assessment, not a Click/DFT computation.
        self.detector_assessment_page = DetectorAssessmentPage(self.project_root)
        self.detector_assessment_page.run_requested.connect(self.run_command)
        self.stack.addWidget(self.detector_assessment_page)

        self.document_scroll = QScrollArea()
        self.document_scroll.setWidgetResizable(True)
        self.document_scroll.setFrameShape(QFrame.NoFrame)
        self.document_scroll.setWidget(self.stack)
        document_layout.addWidget(self.document_scroll, 1)
        center_split.addWidget(document_frame)

        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setObjectName("bottomTabs")
        self.bottom_tabs.setMinimumHeight(110)
        self.bottom_tabs.setDocumentMode(True)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("logConsole")
        self.log.setPlaceholderText("任务输出将在此显示。")
        self.bottom_tabs.addTab(self.log, "任务输出")

        self.file_model = QFileSystemModel(self)
        self.file_model.setReadOnly(True)
        self.files = QTreeView()
        self.files.setModel(self.file_model)
        self.files.doubleClicked.connect(self._open_selected_file)
        # 右键上下文菜单
        self.files.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.files.customContextMenuRequested.connect(
            self._show_file_context_menu
        )
        self.files.setObjectName("fileTree")
        self.bottom_tabs.addTab(self.files, "工程文件")

        self.messages = QPlainTextEdit()
        self.messages.setReadOnly(True)
        self.messages.setObjectName("messageConsole")
        self.messages.setPlainText("SS-Screen 工程工作台已就绪。\n选择左侧工程节点或分析命令开始。")
        self.bottom_tabs.addTab(self.messages, "消息")

        center_split.addWidget(self.bottom_tabs)
        center_split.setStretchFactor(0, 1)
        center_split.setStretchFactor(1, 0)
        center_split.setSizes([760, 145])
        workspace.addWidget(center_split)

        # Right: properties/inspector.
        inspector_frame = QFrame()
        inspector_frame.setObjectName("inspectorFrame")
        inspector_layout = QVBoxLayout(inspector_frame)
        inspector_layout.setContentsMargins(0, 0, 0, 0)
        inspector_layout.setSpacing(0)
        inspector_header = QLabel("属性 / Properties")
        inspector_header.setObjectName("panelHeader")
        inspector_header.setWordWrap(True)
        inspector_header.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        inspector_layout.addWidget(inspector_header)
        self.inspector = InspectorPanel()
        self.inspector_scroll = QScrollArea()
        self.inspector_scroll.setWidgetResizable(True)
        self.inspector_scroll.setFrameShape(QFrame.NoFrame)
        self.inspector_scroll.setWidget(self.inspector)
        inspector_layout.addWidget(self.inspector_scroll, 1)
        self.api_key = self.inspector.api_key
        self.runtime_backend = self.inspector.runtime_backend
        self.wsl_root = self.inspector.wsl_root
        workspace.addWidget(inspector_frame)

        workspace.setSizes([300, 1020, 280])
        workspace.setStretchFactor(1, 1)
        root.addWidget(workspace, 1)

        self.statusBar().setObjectName("statusBar")
        self.statusBar().addPermanentWidget(self.run_state_label)
        self.statusBar().addPermanentWidget(self.run_progress)
        self.statusBar().showMessage("就绪")

    # ---------------- Project tree ----------------

    def _project_by_path(self, path: Path) -> ProjectRecord | None:
        resolved = path.expanduser().resolve()
        for project in self._projects:
            if project.path == resolved:
                return project
        return None

    def _add_project(
        self,
        path: Path,
        *,
        name: str | None = None,
        initialize: bool,
        activate: bool,
        settings: dict[str, Any] | None = None,
    ) -> ProjectRecord:

        path = path.expanduser().resolve()

        existing = self._project_by_path(path)

        if existing is not None:
            if settings is not None:
                existing.settings = dict(settings)

            if activate:
                self._activate_project(existing)

            return existing

        if initialize:
            self._initialize_project_path(path)

        metadata = read_project(path)
        if settings is None:
            settings = metadata.get("gui_settings", {})
        from ssscreen.ten_micron import PROFILE
        from ssscreen.gui.ten_micron_page import native_settings
        if not settings.get("ten_micron_profile") and (path / PROFILE).is_file():
            settings = {**native_settings(json.loads((path / PROFILE).read_text(encoding="utf-8"))), **settings}
        if settings.get("ten_micron_profile"):
            settings.setdefault("wsl_project_path","")
        if name is None:
            name = metadata.get("name")

        project = ProjectRecord(
            name=name or path.name or "工程",
            path=path,
            settings=dict(settings or {}),
        )

        self._projects.append(project)

        # 如果当前完全没有工程，就先把它设为 active。
        # 已经存在 active project 时，不要提前覆盖，
        # 这样 _activate_project() 才有机会保存旧工程的参数。
        if self._active_project is None:
            self._active_project = project

        if activate:
            self._activate_project(project)

        # Stage status uses the active form paths; restore them before reading
        # artifacts in custom directories when opening a saved project.
        self._rebuild_project_tree()

        return project

    def _initialize_project_path(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        for directory in PROJECT_DIRS:
            (root / directory).mkdir(parents=True, exist_ok=True)

        metadata_path = root / ".ssscreen-project.json"
        if not metadata_path.exists():
            payload = {
                "schema_version": 1,
                "name": root.name,
                "created_by": "SS-Screen GUI",
            }
            try:
                metadata_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except OSError:
                pass

    def _mp_project_paths(self, project: ProjectRecord) -> tuple[Path, Path]:
        if project is self._active_project:
            output = self.dataset_source_page.mp_output.text()
            provenance = self.dataset_source_page.mp_provenance.text()
        else:
            form = (project.settings or {}).get("forms", {}).get("dataset_source_page", {})
            output = form.get("mp_output", "01_dataset/mp.df")
            provenance = form.get("mp_provenance", "01_dataset/mp.df.provenance.json")
        return (
            _resolve_project_path(project.path, output),
            _resolve_project_path(project.path, provenance),
        )

    def _composition_project_paths(self, project: ProjectRecord) -> tuple[Path, ...]:
        defaults = {
            "candidates_output": "02_composition/composition_candidates.csv",
            "summary_output": "02_composition/composition_summary.json",
            "structures_output": "02_composition/candidates.df",
        }
        form = (project.settings or {}).get("forms", {}).get("composition_screen_page", {})
        return tuple(
            _resolve_project_path(
                project.path,
                (
                    getattr(self.composition_screen_page, key).text()
                    if project is self._active_project
                    else form.get(key, default)
                ),
            )
            for key, default in defaults.items()
        )

    def _configured_project_path(
        self, project: ProjectRecord, page_name: str, key: str, default: str
    ) -> Path:
        if project is self._active_project:
            value = getattr(getattr(self, page_name), key).text()
        else:
            value = (project.settings or {}).get("forms", {}).get(page_name, {}).get(key, default)
        return _resolve_project_path(project.path, value)

    def _stage_status(self, root: Path, directory: str) -> tuple[str, int]:
        project = self._project_by_path(root)
        if project and project.settings and project.settings.get("ten_micron_profile"):
            from ssscreen.ten_micron import CACHED
            from ssscreen.gui.ten_micron_page import marker
            sid = directory[:2]
            if sid == "13" and (root / directory / "candidate_evaluation.csv").is_file():
                return "几何数据已预置", 0
            if sid.isdigit() and int(sid) in CACHED:
                return ("已使用预计算结果" if marker(root, int(sid)).is_file() else "预计算结果已预置"), 0
        if directory == "08_relax" and project is self._active_project:
            page = self._pages.get(("stability", "relax"))
            status = page.result_status() if page else {}
            if status.get("ready"):
                return "可进入09", status["success"]
        if directory == "07_sqs" and project is self._active_project:
            page = self._pages.get(("stability", "sqs-generate"))
            status = page.result_status() if page else {}
            if status.get("ready"):
                return f"已生成，跳过 {status['skipped']}", status["written"]
        if directory == "05_gap" and project is self._active_project:
            page = self._pages.get(("gap-collect-vasp",))
            report = page._collection_report() if page else {}
            if page and page._validated(report):
                return (
                    f"已校验，成功 {report['status_counts'].get('success', 0)}",
                    report["collected_result_count"],
                )
        if project and project.settings and not project.settings.get("ten_micron_profile"):
            stage = project.settings.get("workflow_stages", {}).get(directory[:2])
            if stage:
                return stage["status"], stage["count"]
        path = root / directory
        if directory == "06_pair" and project:
            page = self._pages.get(("pair-wavelength",)) if project is self._active_project else None
            argv = (
                page.argv() if page is not None
                else (project.settings or {}).get("commands", {}).get("pair-wavelength", [])
            )
            if "--output" in argv and "--summary" in argv:
                output = _resolve_project_path(root, argv[argv.index("--output") + 1])
                summary = _resolve_project_path(root, argv[argv.index("--summary") + 1])
                try:
                    report = json.loads(summary.read_text(encoding="utf-8"))
                    with output.open(encoding="utf-8-sig", newline="") as stream:
                        reader = csv.DictReader(stream)
                        if {"mp_id_a", "mp_id_b"} <= set(reader.fieldnames or []):
                            count = sum(1 for _ in reader)
                            if count == int(report["pair_count"]):
                                return "已筛选", count
                except (OSError, ValueError, KeyError, csv.Error):
                    pass
        if directory == "05_gap" and project:
            page = self._pages.get(("gap-export",)) if project is self._active_project else None
            if page is not None:
                output = page.output_edit.text()
            else:
                argv = (project.settings or {}).get("commands", {}).get("gap-export", [])
                output = argv[argv.index("--output") + 1] if "--output" in argv else ""
            if output:
                archive = _resolve_project_path(root, output)
                if archive.suffix.lower() != ".zip":
                    archive = archive.with_name("带隙计算输入.zip")
                try:
                    with zipfile.ZipFile(archive) as handle:
                        report = json.loads(handle.read("bundle_manifest.json"))
                    return "已打包", int(report["task_count"])
                except (OSError, ValueError, KeyError, zipfile.BadZipFile):
                    pass
        if directory == "03_condensed" and project:
            archive = self._configured_project_path(
                project, "structure_archive_page", "df_output_dir", "03_condensed/local"
            )
            count = sum(1 for _ in archive.glob("*.json")) if archive.is_dir() else 0
            if count:
                return "已有描述", count
        if directory == "04_groups" and project:
            summary_path = self._configured_project_path(
                project,
                "structure_match_page",
                "summary_output",
                "04_groups/structure_match_summary.json",
            )
            try:
                report = json.loads(summary_path.read_text(encoding="utf-8"))
                return ("部分结果" if report.get("partial_run") else "有结果"), int(
                    report["group_count"]
                )
            except (OSError, ValueError, KeyError):
                pass
        if directory == "02_composition" and project:
            files = [p for p in self._composition_project_paths(project) if p.is_file()]
            if files:
                return "有产物", len(files)
        if directory == "01_dataset" and project:
            try:
                files = set(path.iterdir()) if path.is_dir() else set()
            except OSError:
                files = set()
            files.update(p for p in self._mp_project_paths(project) if p.is_file())
            if files:
                return "有产物", len(files)
        if not path.exists():
            return "未开始", 0
        try:
            count = sum(1 for _ in path.iterdir())
        except OSError:
            count = 0
        if count == 0:
            return "已建立", 0
        return "有产物", count

    def _rebuild_project_tree(self) -> None:
        self.nav.clear()
        active_path = self._active_project.path if self._active_project else None
        active_item: QTreeWidgetItem | None = None

        for project in self._projects:
            root_item = QTreeWidgetItem([project.name, ""])
            root_item.setIcon(0, app_icon("project"))
            root_item.setData(0, Qt.UserRole, ("project", str(project.path)))
            root_item.setToolTip(0, str(project.path))
            root_item.setFirstColumnSpanned(False)
            self.nav.addTopLevelItem(root_item)

            overview = QTreeWidgetItem(["工程概览", ""])
            overview.setIcon(0, app_icon("dashboard"))
            overview.setData(0, Qt.UserRole, ("dashboard", str(project.path)))
            root_item.addChild(overview)

            for group_name, stage_ids in STAGE_GROUPS:
                group_item = QTreeWidgetItem([group_name, ""])
                group_item.setIcon(0, app_icon("group"))
                group_item.setData(0, Qt.UserRole, ("group", str(project.path), group_name))
                root_item.addChild(group_item)

                for sid in stage_ids:
                    stage_info = next(item for item in STAGES if item[0] == sid)
                    _sid, stage_name, directory = stage_info
                    status, count = self._stage_status(project.path, directory)
                    status_text = status if count == 0 else f"{status} ({count})"
                    stage_item = QTreeWidgetItem([f"{sid}  {stage_name}", status_text])
                    stage_item.setIcon(0, stage_icon(sid))
                    stage_item.setData(
                        0,
                        Qt.UserRole,
                        ("stage", str(project.path), sid, directory, stage_name),
                    )
                    group_item.addChild(stage_item)

                    if sid == "01":
                        dataset_root = project.path / "01_dataset"
                        mp_df, mp_provenance = self._mp_project_paths(project)
                        wbm_df = dataset_root / "wbm.df"

                        mp_parent = QTreeWidgetItem(
                            [
                                "Materials Project",
                                "Ready" if mp_df.exists() else "未获取",
                            ]
                        )
                        mp_parent.setIcon(0, app_icon("dataset"))
                        mp_parent.setData(
                            0,
                            Qt.UserRole,
                            (
                                "dataset_object",
                                str(project.path),
                                "mp",
                                "Materials Project",
                            ),
                        )
                        stage_item.addChild(mp_parent)

                        for key, name, status_value in (
                            (
                                "mp_fetch",
                                "数据获取 / Acquisition",
                                "API / Offline",
                            ),
                            (
                                "mp_local",
                                "Local Dataset / mp.df",
                                ("已生成" if mp_df.exists() else "未生成"),
                            ),
                            (
                                "mp_provenance",
                                "Provenance / 来源记录",
                                ("已生成" if mp_provenance.exists() else "未生成"),
                            ),
                        ):
                            child = QTreeWidgetItem([name, status_value])
                            child.setData(
                                0,
                                Qt.UserRole,
                                (
                                    "dataset_object",
                                    str(project.path),
                                    key,
                                    name,
                                ),
                            )
                            mp_parent.addChild(child)

                        wbm_parent = QTreeWidgetItem(
                            [
                                "WBM Dataset",
                                "Ready" if wbm_df.exists() else "未获取",
                            ]
                        )
                        wbm_parent.setIcon(0, app_icon("dataset"))
                        wbm_parent.setData(
                            0,
                            Qt.UserRole,
                            (
                                "dataset_object",
                                str(project.path),
                                "wbm",
                                "WBM Dataset",
                            ),
                        )
                        stage_item.addChild(wbm_parent)

                        for key, name, status_value in (
                            (
                                "wbm_fetch",
                                "数据获取 / Acquisition",
                                "",
                            ),
                            (
                                "wbm_local",
                                "Local Dataset / wbm.df",
                                ("已生成" if wbm_df.exists() else "未生成"),
                            ),
                        ):
                            child = QTreeWidgetItem([name, status_value])
                            child.setData(
                                0,
                                Qt.UserRole,
                                (
                                    "dataset_object",
                                    str(project.path),
                                    key,
                                    name,
                                ),
                            )
                            wbm_parent.addChild(child)

                    elif sid == "02":
                        composition_root = project.path / "02_composition"
                        valid_ids = composition_root / "valid_ids.json"
                        candidate_file, composition_summary, structures_file = (
                            self._composition_project_paths(project)
                        )

                        candidate_count = 0
                        template_count = None

                        if composition_summary.exists():
                            try:
                                with composition_summary.open(
                                    "r",
                                    encoding="utf-8",
                                ) as handle:
                                    summary_data = json.load(handle)
                                if isinstance(summary_data, dict):
                                    candidate_count = int(
                                        summary_data.get(
                                            "candidate_rows",
                                            0,
                                        )
                                        or 0
                                    )
                                    value = summary_data.get(
                                        "template_count",
                                        None,
                                    )
                                    if value is not None:
                                        template_count = int(value)
                            except Exception:
                                pass

                        if candidate_count == 0 and candidate_file.exists():
                            try:
                                with candidate_file.open(
                                    "r",
                                    encoding="utf-8-sig",
                                    newline="",
                                ) as handle:
                                    candidate_count = sum(1 for _ in csv.DictReader(handle))
                            except Exception:
                                candidate_count = 0

                        # Valence filter remains an optional operation.
                        valence_item = QTreeWidgetItem(
                            [
                                "价态过滤（可选）",
                                "已生成" if valid_ids.exists() else "未使用",
                            ]
                        )
                        valence_item.setData(
                            0,
                            Qt.UserRole,
                            (
                                "command",
                                str(project.path),
                                ("valence-filter",),
                            ),
                        )
                        stage_item.addChild(valence_item)

                        object_status = {
                            "input": "MP / WBM / 自定义",
                            "rules": "Template screening",
                            "structures": "已生成" if structures_file.is_file() else "未生成",
                            "candidates": (f"{candidate_count} 条" if candidate_count else "未生成"),
                            "summary": (
                                (
                                    f"{template_count} templates"
                                    if template_count is not None
                                    else "已生成"
                                )
                                if composition_summary.exists()
                                else "未生成"
                            ),
                        }

                        for object_key, object_name in COMPOSITION_SCREEN_OBJECTS:
                            object_item = QTreeWidgetItem([object_name, object_status[object_key]])
                            object_item.setData(
                                0,
                                Qt.UserRole,
                                (
                                    "composition_object",
                                    str(project.path),
                                    object_key,
                                    object_name,
                                ),
                            )
                            stage_item.addChild(object_item)

                    elif sid == "03":
                        configured_archive = self._configured_project_path(
                            project, "structure_archive_page", "df_output_dir", "03_condensed/local"
                        )
                        description_count = sum(1 for _ in configured_archive.glob("*.json"))
                        manifest_ready = self._configured_project_path(
                            project,
                            "structure_archive_page",
                            "df_manifest",
                            "03_condensed/local_manifest.jsonl",
                        ).is_file()
                        index_ready = self._configured_project_path(
                            project,
                            "structure_archive_page",
                            "df_index",
                            "03_condensed/local_index.csv",
                        ).is_file()
                        validation_ready = (configured_archive.parent / "validation.csv").is_file()

                        object_status = {
                            "input": "DataFrame / Files",
                            "archive": f"{description_count} 条" if description_count else "未生成",
                            "manifest": "已生成" if manifest_ready else "未生成",
                            "index": "已生成" if index_ready else "未生成",
                            "validation": "已校验" if validation_ready else "待校验",
                        }
                        for object_key, object_name in STRUCTURE_ARCHIVE_OBJECTS:
                            object_item = QTreeWidgetItem([object_name, object_status[object_key]])
                            object_item.setData(
                                0,
                                Qt.UserRole,
                                (
                                    "structure_object",
                                    str(project.path),
                                    object_key,
                                    object_name,
                                ),
                            )
                            stage_item.addChild(object_item)

                    elif sid == "04":
                        candidate_file = self._configured_project_path(
                            project,
                            "structure_match_page",
                            "candidates_edit",
                            "02_composition/composition_candidates.csv",
                        )
                        archives = (
                            self.structure_match_page._archive_paths()
                            if project is self._active_project
                            else (project.settings or {})
                            .get("forms", {})
                            .get("structure_match_page", {})
                            .get("archives", ["03_condensed/local"])
                        )
                        archive_count = sum(
                            any(_resolve_project_path(project.path, raw).glob("*.json"))
                            for raw in archives
                        )
                        groups_file = self._configured_project_path(
                            project, "structure_match_page", "groups_output", "04_groups/groups.json"
                        )
                        summary_file = self._configured_project_path(
                            project,
                            "structure_match_page",
                            "summary_output",
                            "04_groups/structure_match_summary.json",
                        )

                        group_count = 0
                        if groups_file.exists():
                            try:
                                with groups_file.open("r", encoding="utf-8") as handle:
                                    group_data = json.load(handle)
                                if isinstance(group_data, list):
                                    group_count = len(group_data)
                                elif isinstance(group_data, dict) and "entry_idx" in group_data:
                                    entry_column = group_data.get("entry_idx", {})
                                    if isinstance(entry_column, dict):
                                        group_count = len(entry_column)
                            except Exception:
                                group_count = 0

                        input_ready = candidate_file.exists() and archive_count > 0
                        object_status = {
                            "input": "Ready" if input_ready else "待准备",
                            "rules": "X substitution",
                            "groups": (f"{group_count} groups" if group_count else "未生成"),
                            "summary": "已生成" if summary_file.exists() else "未生成",
                        }

                        for object_key, object_name in STRUCTURE_MATCH_OBJECTS:
                            object_item = QTreeWidgetItem([object_name, object_status[object_key]])
                            object_item.setData(
                                0,
                                Qt.UserRole,
                                (
                                    "structure_match_object",
                                    str(project.path),
                                    object_key,
                                    object_name,
                                ),
                            )
                            stage_item.addChild(object_item)

                    else:
                        for presentation in COMMANDS:
                            if presentation.stage != sid:
                                continue
                            if presentation.command_path not in self._command_lookup:
                                continue
                            command_item = QTreeWidgetItem([presentation.title, ""])
                            command_item.setData(
                                0,
                                Qt.UserRole,
                                ("command", str(project.path), presentation.command_path),
                            )
                            stage_item.addChild(command_item)

                group_item.setExpanded(True)

            files_item = QTreeWidgetItem(["工程文件", ""])
            files_item.setIcon(0, app_icon("files"))
            files_item.setData(0, Qt.UserRole, ("files", str(project.path)))
            root_item.addChild(files_item)

            logs_item = QTreeWidgetItem(["运行记录", ""])
            logs_item.setIcon(0, app_icon("logs"))
            logs_item.setData(0, Qt.UserRole, ("logs", str(project.path)))
            root_item.addChild(logs_item)

            root_item.setExpanded(True)

            if active_path is not None and project.path == active_path:
                active_item = root_item

        if active_item is not None:
            self.nav.setCurrentItem(active_item)

    def _navigation_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        kind = data[0]
        path = Path(data[1]).resolve()
        project = self._project_by_path(path)
        if project is None:
            return

        if self._active_project is not project:
            self._activate_project(project)

        if self.workflow.settings.get("ten_micron_profile"):
            ancestor = item
            while ancestor is not None:
                payload = ancestor.data(0, Qt.UserRole)
                if payload and payload[0] == "stage":
                    self.workflow.select_stage(payload[2])
                    break
                ancestor = ancestor.parent()

        if kind == "stage" and data[2] in {"05", "06", "07", "08", *STABILITY_PATHS}:
            item.setExpanded(True)
            if not self.workflow.settings.get("workflow_stages"):
                default_command = {
                    "05": ("gap-export",),
                    "06": ("pair-wavelength",),
                    "07": ("stability", "sqs-generate"),
                    "08": ("stability", "relax"),
                    **STABILITY_PATHS,
                }[data[2]]
                command_path = tuple(
                    self.workflow.settings.get("stage_commands", {}).get(
                        data[2], default_command
                    )
                )
                if data[2] in {"06", "07", "08", *STABILITY_PATHS}:
                    command_path = default_command
                for index in range(item.childCount()):
                    child = item.child(index)
                    child_data = child.data(0, Qt.UserRole)
                    if (
                        child_data
                        and child_data[0] == "command"
                        and tuple(child_data[2]) == command_path
                    ):
                        self.nav.setCurrentItem(child)
                        self._navigation_clicked(child, 0)
                        return

        if kind == "stage" and self.workflow.settings.get("workflow_stages"):
            self.workflow.select_stage(data[2])
            self.workflow.show_parameters()
            self.inspector.set_selection(
                item_type="工程阶段",
                name=item.text(0),
                path=str(project.path / data[3]),
                status=item.text(1),
            )
            return
        if kind == "command":
            command_path = tuple(data[2])
            presentation = next((p for p in COMMANDS if p.command_path == command_path), None)
            if presentation:
                self.workflow.select_stage(presentation.stage)

        if kind in {"project", "dashboard"}:
            self.stack.setCurrentWidget(self.dashboard)
            self.document_label.setText(f"{project.name} / 工程概览")
            self.dashboard.refresh()
            self.inspector.set_selection(
                item_type="工程",
                name=project.name,
                path=str(project.path),
                status="活动工程",
            )
            return

        if kind == "group":
            self.stack.setCurrentWidget(self.dashboard)
            self.document_label.setText(f"{project.name} / {data[2]}")
            self.inspector.set_selection(
                item_type="功能组",
                name=data[2],
                path=str(project.path),
                status="",
            )
            return

        if kind == "stage":
            sid, directory, stage_name = data[2], data[3], data[4]
            status, count = self._stage_status(project.path, directory)

            if sid == "01":
                self.dataset_source_page.select_section("mp")
                self.stack.setCurrentWidget(self.dataset_source_page)
                self.document_label.setText(f"{project.name} / 数据源")
                self.inspector.set_selection(
                    item_type="工程阶段",
                    name="Stage 01：外部材料数据源",
                    path=str(self._mp_project_paths(project)[0].parent),
                    status=status if count == 0 else f"{status} · {count} 项",
                )
            elif sid == "02":
                self.composition_screen_page.select_section("screen")
                self.stack.setCurrentWidget(self.composition_screen_page)
                self.document_label.setText(f"{project.name} / 组成模板筛选")
                self.inspector.set_selection(
                    item_type="工程阶段",
                    name="Stage 02：组成模板筛选",
                    path=str(self._composition_project_paths(project)[0].parent),
                    status=status if count == 0 else f"{status} · {count} 项",
                )
            elif sid == "03":
                self.structure_archive_page.select_section("input")
                self.stack.setCurrentWidget(self.structure_archive_page)
                self.document_label.setText(f"{project.name} / 结构描述归档")
                self.inspector.set_selection(
                    item_type="工程阶段",
                    name="Stage 03：结构描述归档",
                    path=str(
                        self.structure_archive_page._resolve(
                            self.structure_archive_page.df_output_dir.text()
                        )
                    ),
                    status=status if count == 0 else f"{status} · {count} 项",
                )
            elif sid == "04":
                self.structure_match_page.select_section("match")
                self.stack.setCurrentWidget(self.structure_match_page)
                self.document_label.setText(f"{project.name} / 结构匹配与材料分组")
                self.inspector.set_selection(
                    item_type="工程阶段",
                    name="Stage 04：结构匹配与材料分组",
                    path=str(
                        self.structure_match_page._resolve(
                            self.structure_match_page.groups_output.text()
                        ).parent
                    ),
                    status=status if count == 0 else f"{status} · {count} 项",
                )
            elif sid == "08":
                self.structure_results_page.refresh()
                self.stack.setCurrentWidget(self.structure_results_page)
                self.document_label.setText(f"{project.name} / MACE 驰豫结构")
                self.inspector.set_selection(
                    item_type="晶体结构结果",
                    name="Stage 08：MatterViz 晶体结构",
                    path=str(project.path / directory),
                    status=status if count == 0 else f"{status} · {count} 项",
                )
            elif sid == "10":
                self.phonon_results_page.refresh()
                self.stack.setCurrentWidget(self.phonon_results_page)
                self.document_label.setText(f"{project.name} / 声子谱可视化")
                self.inspector.set_selection(
                    item_type="声子谱结果",
                    name="Stage 10：频带、DOS与晶体结构",
                    path=str(project.path / directory),
                    status=status if count == 0 else f"{status} · {count} 项",
                )
            elif sid == "11":
                self.phase_results_page.refresh()
                self.stack.setCurrentWidget(self.phase_results_page)
                self.document_label.setText(f"{project.name} / 竞争相与凸包可视化")
                self.inspector.set_selection(
                    item_type="竞争相结果",
                    name="Stage 11：凸包、竞争相与晶体结构",
                    path=str(project.path / directory),
                    status=status if count == 0 else f"{status} · {count} 项",
                )
            elif sid == "12":
                self.recommendation_report_page.refresh()
                self.stack.setCurrentWidget(self.recommendation_report_page)
                self.document_label.setText(f"{project.name} / 综合推荐与结果报告")
                self.inspector.set_selection(
                    item_type="结果报告",
                    name="Stage 12：综合推荐",
                    path=str(project.path / directory),
                    status=status if count == 0 else f"{status} · {count} 项",
                )
            elif sid == "13":
                self.detector_assessment_page.refresh()
                self.stack.setCurrentWidget(self.detector_assessment_page)
                self.document_label.setText(f"{project.name} / 固溶体候选评价")
                self.inspector.set_selection(
                    item_type="候选评价",
                    name="Stage 13：固溶体候选几何评价与材料级预筛",
                    path=str(project.path / directory),
                    status=status if count == 0 else f"{status} · {count} 项",
                )
            else:
                self.stack.setCurrentWidget(self.dashboard)
                self.document_label.setText(f"{project.name} / {sid} {stage_name}")
                self.inspector.set_selection(
                    item_type="分析阶段",
                    name=f"{sid} {stage_name}",
                    path=str(project.path / directory),
                    status=status if count == 0 else f"{status} · {count} 项",
                )
            return

        if kind == "dataset_object":
            object_key, object_name = data[2], data[3]
            self.dataset_source_page.select_section(object_key)
            self.stack.setCurrentWidget(self.dataset_source_page)
            self.document_label.setText(f"{project.name} / 数据源 / {object_name}")

            if object_key.startswith("mp"):
                if object_key in {"mp_local", "mp_provenance"}:
                    item_type = "本地数据对象"
                else:
                    item_type = "外部数据源"
                object_path = project.path / "01_dataset"
            else:
                if object_key == "wbm_local":
                    item_type = "本地数据对象"
                else:
                    item_type = "外部数据源"
                object_path = project.path / "01_dataset"

            self.inspector.set_selection(
                item_type=item_type,
                name=object_name,
                path=str(object_path),
                status="",
            )
            return

        if kind == "composition_object":
            object_key, object_name = data[2], data[3]
            self.composition_screen_page.select_section(object_key)
            self.stack.setCurrentWidget(self.composition_screen_page)
            self.document_label.setText(f"{project.name} / 组成模板筛选 / {object_name}")

            if object_key in {"candidates", "summary", "structures"}:
                object_type = "组成筛选结果"
                object_path = self._composition_project_paths(project)[
                    {"candidates": 0, "summary": 1, "structures": 2}[object_key]
                ]
            else:
                object_type = "组成筛选设置"
                object_path = project.path

            self.inspector.set_selection(
                item_type=object_type,
                name=object_name,
                path=str(object_path),
                status="",
            )
            return

        if kind == "structure_object":
            object_key, object_name = data[2], data[3]
            self.structure_archive_page.select_section(object_key)
            self.stack.setCurrentWidget(self.structure_archive_page)
            self.document_label.setText(f"{project.name} / 结构描述归档 / {object_name}")
            self.inspector.set_selection(
                item_type="结构归档对象",
                name=object_name,
                path=str(project.path / "03_condensed"),
                status="",
            )
            return

        if kind == "structure_match_object":
            object_key, object_name = data[2], data[3]
            self.structure_match_page.select_section(object_key)
            self.stack.setCurrentWidget(self.structure_match_page)
            self.document_label.setText(f"{project.name} / 结构匹配与材料分组 / {object_name}")

            if object_key in {"groups", "summary"}:
                object_path = project.path / "04_groups"
                object_type = "结构匹配结果"
            else:
                object_path = project.path
                object_type = "结构匹配设置"

            self.inspector.set_selection(
                item_type=object_type,
                name=object_name,
                path=str(object_path),
                status="",
            )
            return

        if kind == "command":
            command_path = tuple(data[2])
            self._show_command_page(command_path)
            presentation = next(p for p in COMMANDS if p.command_path == command_path)
            self.document_label.setText(f"{project.name} / {presentation.title}")
            self.inspector.set_selection(
                item_type="命令",
                name=presentation.title,
                path="ss-screen " + " ".join(command_path),
                status="待运行",
            )
            return

        if kind == "files":
            self.bottom_tabs.setCurrentWidget(self.files)
            self.document_label.setText(f"{project.name} / 工程文件")
            self.inspector.set_selection(
                item_type="文件系统",
                name="工程文件",
                path=str(project.path),
                status="",
            )
            return

        if kind == "logs":
            self.bottom_tabs.setCurrentWidget(self.log)
            self.document_label.setText(f"{project.name} / 运行记录")
            self.inspector.set_selection(
                item_type="日志",
                name="运行记录",
                path=str(project.path / "logs"),
                status="",
            )
            return

    def _activate_project(
        self,
        project: ProjectRecord,
    ) -> None:

        previous = self._active_project

        # 切走之前，把旧工程当前 GUI 参数保存到内存。
        if (
            previous is not None
            and previous is not project
        ):
            previous.settings = (
                self._project_settings_snapshot()
            )

        self._active_project = project

        # 恢复新工程自己的参数。
        self._apply_project_settings(
            project.settings
        )

        self.active_project_label.setText(
            f"工程：{project.name}"
        )

        self.active_project_label.setToolTip(
            str(project.path)
        )
        self.setWindowTitle("SS-Screen V1.0 · Materials Engineering Workbench" +
                            (f" · {project.name}" if project.settings.get("ten_micron_profile") else ""))

        self._refresh_file_tree()

        self.dashboard.refresh()
        self.workflow.refresh()

    def new_project(self) -> None:
        parent = QFileDialog.getExistingDirectory(
            self,
            "选择新工程保存位置",
            str(self.project_root().parent),
        )
        if not parent:
            return

        name, ok = QInputDialog.getText(
            self,
            "新建工程",
            "工程名称：",
            text=f"Project-{len(self._projects) + 1:02d}",
        )
        if not ok or not name.strip():
            return

        path = Path(parent) / name.strip()
        if path.exists() and any(path.iterdir()):
            answer = QMessageBox.question(
                self,
                "目录非空",
                f"{path} 已存在且非空。\n是否将其作为 SS-Screen 工程打开？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        try:
            project = self._add_project(
                path,
                name=name.strip(),
                initialize=True,
                activate=True,
            )
        except OSError as exc:
            QMessageBox.critical(self, "创建工程失败", str(exc))
            return

        if project.settings.get("ten_micron_profile"):
            from ssscreen.gui.ten_micron_page import open_stage
            open_stage(self, 1)
        else:
            self.document_label.setText(f"{project.name} / 工程概览")
        self.statusBar().showMessage(f"已创建工程：{project.name}")

    def _project_settings_snapshot(self) -> dict[str, Any]:
        commands: dict[str, list[str]] = {}

        # 先保留这个工程从 .ssproject 中加载出来、
        # 但当前还没有打开过对应 GUI 页面的命令参数。
        project = self._active_project

        if (
            project is not None
            and isinstance(project.settings, dict)
        ):
            saved_commands = project.settings.get(
                "commands",
                {},
            )

            if isinstance(saved_commands, dict):
                for key, argv in saved_commands.items():
                    if isinstance(argv, list):
                        commands[str(key)] = [
                            str(value)
                            for value in argv
                        ]

        # 已经真正打开/修改过的页面，以当前 GUI 状态覆盖旧值。
        for path, page in self._pages.items():
            commands[" ".join(path)] = page.argv()

        values = dict((project.settings or {}).get("command_values", {})) if project else {}
        command_forms = dict((project.settings or {}).get("command_forms", {})) if project else {}
        for path in self._pages:
            values.pop(" ".join(path), None)
            if hasattr(self._pages[path], "form_state"):
                command_forms[" ".join(path)] = self._pages[path].form_state()

        return {
            **(project.settings or {} if project else {}),
            "artifact_aliases": read_project(project.path).get("artifacts", {}) if project else {},
            "forms": capture_forms(self),
            "command_values": values,
            "command_forms": command_forms,
            "runtime_backend":
                self.runtime_backend.currentText(),

            "wsl_project_path":
                self.wsl_root.text().strip(),

            "commands": commands,
        }

    def _sync_composition_archive_input(self) -> None:
        if self.structure_archive_page.df_follow_composition.isChecked():
            self.structure_archive_page.df_path.setText(
                self.composition_screen_page.structures_output.text()
            )

    def _sync_structure_match_inputs(self) -> None:
        page = self.structure_match_page
        if not page.follow_stage03.isChecked():
            return
        page.candidates_edit.setText(self.composition_screen_page.candidates_output.text())
        page.archive_table.setRowCount(0)
        value = self.structure_archive_page.df_output_dir.text().strip()
        if value:
            page._append_archive(self.structure_archive_page._resolve(value))
        page.refresh_inputs()

    def _use_completed_condense(self) -> None:
        if self.process.state() != QProcess.NotRunning:
            if self._condense_stop_file is None:
                QMessageBox.warning(self, "其他任务运行中", "请先等待当前任务结束。")
                return
            self._handoff_after_stop = True
            self.stop_process()
            return
        archive = self.structure_archive_page._resolve(self.structure_archive_page.df_output_dir.text())
        if not archive.is_dir() or not any(archive.glob("*.json")):
            QMessageBox.warning(self, "暂无已完成描述", "请先生成至少一个结构描述。")
            return
        self.structure_match_page.follow_stage03.setChecked(True)
        self._sync_structure_match_inputs()
        self.structure_match_page.select_section("input")
        self.stack.setCurrentWidget(self.structure_match_page)
        self.document_label.setText("04 结构匹配 · 使用 03 已完成描述")
        self.statusBar().showMessage("已接入 03 当前结果；点击“开始结构匹配”运行 04。")

    def _apply_project_settings(
        self,
        settings: dict[str, Any] | None,
    ) -> None:
        """Restore saved project settings into the GUI."""

        if not isinstance(settings, dict):
            settings = {}

        restore_forms(self, self._default_forms)
        restore_forms(self, settings.get("forms", {}))

        # --------------------------------------------------
        # Runtime backend
        # --------------------------------------------------
        backend = settings.get("runtime_backend")

        if backend:
            index = self.runtime_backend.findText(
                str(backend)
            )

            if index >= 0:
                self.runtime_backend.setCurrentIndex(
                    index
                )

        # --------------------------------------------------
        # WSL project path
        # --------------------------------------------------
        if "wsl_project_path" in settings:
            self.wsl_root.setText(
                str(
                    settings.get(
                        "wsl_project_path",
                        "",
                    )
                )
            )

        # --------------------------------------------------
        # Command pages that already exist
        # --------------------------------------------------
        commands = settings.get("commands", {})

        if not isinstance(commands, dict):
            commands = {}

        for path, page in self._pages.items():
            key = " ".join(path)
            saved_argv = commands.get(key)

            if isinstance(saved_argv, list):
                page.restore_argv(saved_argv)
            else:
                # 这个工程没有保存该页面参数，
                # 防止前一个工程的参数残留过来。
                page.reset()

            self.workflow.configure_command(page)
            if hasattr(page, "restore_form_state"):
                page.restore_form_state(settings.get("command_forms", {}).get(key, {}))

        if ("pair-wavelength",) in self._pages:
            self._pages[("pair-wavelength",)].refresh_preview()
        if ("stability", "sqs-generate") in self._pages:
            self._pages[("stability", "sqs-generate")].refresh_preview()
        if ("stability", "relax") in self._pages:
            self._pages[("stability", "relax")].refresh_preview()
        self._refresh_stability_inputs()

    def save_project_file(self) -> None:
        project = self._active_project
        if project is None:
            return
        default = project.path.parent / f"{project.name}.ssproject"
        value, _ = QFileDialog.getSaveFileName(
            self,
            "保存 SS-Screen 单文件工程",
            str(default),
            "SS-Screen Project (*.ssproject)",
        )
        if not value:
            return
        target = Path(value)
        if target.suffix.lower() != ".ssproject":
            target = target.with_suffix(".ssproject")
        try:
            project_settings = (
            self._project_settings_snapshot()
        )

            project.settings = project_settings

            manifest = create_project_file(
                project.path,
                target,
                project_settings=project_settings,
            )
        except Exception as exc:
            QMessageBox.critical(self, "保存项目失败", str(exc))
            return
        QMessageBox.information(
            self,
            "项目已保存",
            f"已写入 {manifest['artifact_count']} 个文件，"
            f"原始数据 {manifest['total_bytes'] / 1024:.1f} KiB。\n{target}",
        )
        self.statusBar().showMessage(f"已保存单文件工程：{target.name}")

    def open_project_file(self) -> None:
        value, _ = QFileDialog.getOpenFileName(
            self,
            "打开 SS-Screen 单文件工程",
            str(self.project_root()),
            "SS-Screen Project (*.ssproject)",
        )
        if not value:
            return
        source = Path(value).resolve()
        try:
            project_metadata, _manifest = inspect_project_file(source)
            profile = project_metadata.get("settings", {}).get("ten_micron_profile")
            if profile:
                from ssscreen.gui.ten_micron_page import unpack_example
                selected = QFileDialog.getExistingDirectory(self, "选择空目录作为算例工程根目录", str(source.parent))
                if not selected:
                    return
                cache_root = Path(selected).resolve()
                unpack_example(source, cache_root, profile)
            else:
                source_digest = hashlib.sha256()
                with source.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        source_digest.update(chunk)
                digest = source_digest.hexdigest()[:12]
                cache_base = (
                    Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SS-Screen" / "projects"
                )
                cache_root = cache_base / f"{source.stem}-{digest}"
                extract_project_file(source, cache_root)
            saved_settings = project_metadata.get(
                "settings",
                {},
            )
            if not isinstance(saved_settings, dict):
                saved_settings = {}
            project = self._add_project(
                cache_root,
                name=str(
                    project_metadata.get("name")
                    or source.stem
                ),
                initialize=False,
                activate=True,
                settings=saved_settings,
            )
        except Exception as exc:
            QMessageBox.critical(self, "打开项目失败", str(exc))
            return
        if self.workflow.settings.get("ten_micron_profile"):
            from ssscreen.gui.ten_micron_page import open_stage
            open_stage(self, 1)
        else:
            self.document_label.setText(f"{project.name} / 工程概览")
        self.statusBar().showMessage(f"已校验并打开：{source.name}")

    def remove_active_project(self) -> None:
        project = self._active_project
        if project is None:
            return
        if len(self._projects) == 1:
            QMessageBox.information(
                self,
                "保留一个工程",
                "工作区至少保留一个工程。请先新建或打开另一个工程。",
            )
            return

        answer = QMessageBox.question(
            self,
            "从工作区移除工程",
            f"仅从当前工作区移除“{project.name}”，不会删除磁盘文件。\n确认继续吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self._projects = [item for item in self._projects if item.path != project.path]
        self._active_project = self._projects[0] if self._projects else None
        self._rebuild_project_tree()
        if self._active_project is not None:
            self._activate_project(self._active_project)

    def project_root(self) -> Path:
        if self._active_project is not None:
            return self._active_project.path
        return Path.cwd().resolve()

    def init_project(self) -> None:
        root = self.project_root()
        try:
            self._initialize_project_path(root)
        except OSError as exc:
            QMessageBox.critical(self, "初始化失败", str(exc))
            return

        self.dashboard.refresh()
        self._refresh_file_tree()
        self._rebuild_project_tree()
        self.statusBar().showMessage(f"已初始化工程目录：{root}")

    def open_project(self) -> None:
        root = self.project_root()
        if root.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(root)))

    # ---------------- Command pages ----------------

    def _show_command_page(self, path: tuple[str, ...]) -> None:
        # Saved workspaces may still point at the former separate validation page.
        if path == ("gap-validate",):
            path = ("gap-collect-vasp",)
        elif path in {("pair",), ("gap-compare",)}:
            path = ("pair-wavelength",)
        if path == ("dataset", "mp"):
            self.dataset_source_page.select_section("mp")
            self.stack.setCurrentWidget(self.dataset_source_page)
            return

        if path == ("dataset", "wbm"):
            self.dataset_source_page.select_section("wbm")
            self.stack.setCurrentWidget(self.dataset_source_page)
            return

        if path == ("dataset", "structures"):
            self.dataset_source_page.select_section("structures")
            self.stack.setCurrentWidget(self.dataset_source_page)
            return

        if path == ("composition-screen",):
            self.composition_screen_page.select_section("screen")
            self.stack.setCurrentWidget(self.composition_screen_page)
            return

        if path in {("condense",), ("condense-index",), ("condense-validate",)}:
            self.structure_archive_page.select_section(
                "input" if path == ("condense",) else "archive"
            )
            self.stack.setCurrentWidget(self.structure_archive_page)
            return

        if path == ("structure-match",):
            self.structure_match_page.select_section("match")
            self.stack.setCurrentWidget(self.structure_match_page)
            return

        if path in STABILITY_PATHS.values() and ("stability", "relax") not in self._pages:
            self._show_command_page(("stability", "relax"))
        if path == ("stability", "relax") and ("stability", "sqs-generate") not in self._pages:
            self._show_command_page(("stability", "sqs-generate"))
        if path == ("stability", "sqs-generate") and ("pair-wavelength",) not in self._pages:
            self._show_command_page(("pair-wavelength",))
        if path == ("pair-wavelength",) and ("gap-collect-vasp",) not in self._pages:
            # Restore the upstream form even when opening 06 directly after restart.
            self._show_command_page(("gap-collect-vasp",))
        if path in self._pages:
            if isinstance(self._pages[path], (GapCollectPage, WavelengthPairPage, SqsPage, RelaxPage, StabilityPage)):
                self._pages[path].refresh_preview()
            self.stack.setCurrentWidget(self._pages[path])
            return

        command = self._command_lookup[path]
        presentation = next(item for item in COMMANDS if item.command_path == path)
        if path == ("gap-export",):
            page = GapBundlePage(
                presentation, command, self.project_root,
                lambda: (
                    self.structure_match_page.groups_output.text(),
                    self.composition_screen_page.structures_output.text(),
                ),
            )
        elif path == ("gap-collect-vasp",):
            page = GapCollectPage(
                presentation, command, self.project_root,
                self._gap_export_output, self._gap_validation_tasks,
            )
            page.pair_requested.connect(self._open_collected_gap_pairing)
        elif path == ("pair-wavelength",):
            page = WavelengthPairPage(
                presentation, command, self.project_root, self._wavelength_inputs,
            )
            page.sqs_requested.connect(self._open_wavelength_sqs)
        elif path == ("stability", "sqs-generate"):
            page = SqsPage(
                presentation, command, self.project_root, self._sqs_inputs,
                uses_demo_cache=lambda: bool(self.workflow.settings.get("ten_micron_profile")),
            )
            page.relax_requested.connect(self._open_sqs_relaxation)
        elif path == ("stability", "relax"):
            page = RelaxPage(
                presentation, command, self.project_root, self._relax_inputs,
                uses_demo_cache=lambda: bool(self.workflow.settings.get("ten_micron_profile")),
            )
            page.mixing_requested.connect(self._open_relaxation_mixing)
        elif path in STABILITY_PATHS.values():
            page = StabilityPage(
                presentation, command, self.project_root, self._stability_inputs,
                self._stability_input_status, ValueEditor,
            )
            page.next_requested.connect(self._open_stability_next)
            self._connect_stability_inputs()
        else:
            page = CommandPage(presentation, command)
        page.run_requested.connect(self.run_command)
        self._pages[path] = page
        self.stack.addWidget(page)
        self.stack.setCurrentWidget(page)
                # --------------------------------------------------
        # 如果当前工程的 .ssproject 保存了这个命令的参数，
        # 在第一次打开这个页面时恢复。
        # --------------------------------------------------
        project = self._active_project

        if (
            project is not None
            and isinstance(project.settings, dict)
        ):
            commands = project.settings.get(
                "commands",
                {},
            )

            if isinstance(commands, dict):
                saved_argv = commands.get(
                    " ".join(path)
                )

                if isinstance(saved_argv, list):
                    page.restore_argv(saved_argv)

        self.workflow.configure_command(page)
        if hasattr(page, "restore_form_state") and project:
            page.restore_form_state((project.settings or {}).get("command_forms", {}).get(" ".join(path), {}))
        self.stack.setCurrentWidget(page)

    def _wavelength_inputs(self) -> tuple[str, str, bool]:
        groups = self.structure_match_page.groups_output.text().strip()
        profile = self.workflow.settings.get("ten_micron_profile")
        if profile:
            from ssscreen.gui.ten_micron_page import check_file, marker
            from ssscreen.ten_micron import GROUPS, GAPS
            root = self.project_root()
            try:
                if marker(root,5).is_file() and self.structure_match_page._resolve(groups)==root/GROUPS:
                    check_file(root,GROUPS,profile["anchors"][GROUPS])
                    check_file(root,GAPS,profile["files"][GAPS])
                    return groups,GAPS,True
            except (OSError,ValueError):
                pass
            return groups,GAPS,False
        page = self._pages.get(("gap-collect-vasp",))
        verified = page.validated_result() if page else None
        gaps = page.output_paths()[0] if page else "05_gap/results_returned.csv"
        ready = bool(verified and self.structure_match_page._resolve(groups).is_file())
        return groups, verified or gaps, ready

    def _sqs_inputs(self) -> tuple[str, str, bool]:
        page = self._pages.get(("pair-wavelength",))
        pairs = page.output_edit.text().strip() if page else "06_pair/final_pairs.csv"
        dataset = self.composition_screen_page.structures_output.text().strip()
        ready = bool(
            pair_count(self.structure_match_page._resolve(pairs))
            and self.composition_screen_page._resolve(dataset).is_file()
        )
        # New reports can distinguish stale files; legacy pair CSVs remain usable.
        if ready and page:
            try:
                report = json.loads(page._resolve(page.summary_edit.text()).read_text(encoding="utf-8"))
                if "input_sha256" in report:
                    ready = bool(page.validated_result())
            except (OSError, ValueError, TypeError):
                pass
        return pairs, dataset, ready

    def _relax_inputs(self) -> tuple[str, str, str, bool]:
        page = self._pages.get(("stability", "sqs-generate"))
        manifest = page.manifest_edit.text().strip() if page else "07_sqs/sqs_manifest.jsonl"
        pairs, dataset, _ = self._sqs_inputs()
        ready = False
        if page:
            path = page._resolve(manifest)
            try:
                ready = bool(manifest_rows(path))
                if ready and path.with_suffix(".provenance.json").is_file():
                    ready = bool(page.validated_result())
            except (OSError, ValueError, TypeError):
                pass
        return manifest, dataset, pairs, ready

    def _stability_inputs(self, stage: str) -> dict[str, Any]:
        relax = self._pages[("stability", "relax")]
        results = relax.results_edit.text().strip()
        if stage == "09":
            return {"pairs_path": self._sqs_inputs()[0], "relax_results_path": results}
        values = {
            "pairs_path": self._sqs_inputs()[0],
            "model_path": relax.model_edit.text().strip(),
            "model_name": relax.model_name_edit.text().strip(),
            "dtype": relax.dtype_combo.currentText(),
        }
        if stage == "10":
            return {**values, "relax_results_path": results}
        source = self.dataset_source_page
        mode = source.mp_backend.currentData()
        database = source.mp_offline_db.text().strip()
        return {
            **values, "candidate_relax_results_path": results,
            "mp_backend": mode,
            "offline_db": str(imported_artifact(self.project_root(), database))
            if mode == "offline" and database else None,
            "fmax": relax.fmax_edit.text().strip(),
            "max_steps": relax.max_steps_edit.text().strip(),
            "relax_cell": relax.cell_check.isChecked(),
        }

    def _stability_input_status(self, stage: str) -> dict[str, Any]:
        if self.workflow.settings.get("ten_micron_profile"):
            from ssscreen.gui.ten_micron_page import marker, validate_cache
            try:
                root = self.project_root()
                if not marker(root,8).is_file():
                    raise ValueError("请在 08 使用预计算结果")
                validate_cache(root,self.workflow.settings["ten_micron_profile"],8)
                return {"ready":True,"message":"已核验 08 弛豫记录"}
            except (ValueError, OSError, KeyError) as exc:
                return {"ready":False,"message":str(exc)}
        status = self._pages[("stability", "relax")].result_status()
        if stage == "09":
            return status
        if status.get("evidence_valid") and status.get("usable_sqs", 0) > 0:
            return {"ready": True, "message": "08当前合金结果已核对。"}
        return {"ready": False, "message": status.get("message", "等待08当前合金结果。")}

    def _refresh_stability_inputs(self) -> None:
        for page in self._pages.values():
            if isinstance(page, StabilityPage):
                page.refresh_preview()

    def _connect_stability_inputs(self) -> None:
        if getattr(self, "_stability_inputs_connected", False):
            return
        self._stability_inputs_connected = True
        relax = self._pages[("stability", "relax")]
        for edit in (
            *relax._fields().values(),
            self._pages[("pair-wavelength",)].output_edit,
            self.dataset_source_page.mp_offline_db,
        ):
            edit.textChanged.connect(self._refresh_stability_inputs)
        relax.dtype_combo.currentTextChanged.connect(self._refresh_stability_inputs)
        relax.cell_check.toggled.connect(self._refresh_stability_inputs)
        self.dataset_source_page.mp_backend.currentIndexChanged.connect(self._refresh_stability_inputs)

    def _open_stability_next(self, stage: str) -> None:
        if stage in {"11", "12"} and self.workflow.settings.get("ten_micron_profile"):
            from ssscreen.gui.ten_micron_page import accept_cache

            accept_cache(self, stage=int(stage) - 1)
            return
        path = STABILITY_PATHS.get(stage, ("recommend",))
        self._show_command_page(path)
        if stage == "12":
            for sid in ("09", "10", "11"):
                if STABILITY_PATHS[sid] not in self._pages:
                    self._show_command_page(STABILITY_PATHS[sid])
            collect = self._pages[("gap-collect-vasp",)]
            apply_command_values(self._pages[path], {
                "pairs_path": self._sqs_inputs()[0],
                "gap_results_path": self._wavelength_inputs()[1],
                "mixing_enthalpy_path": self._pages[STABILITY_PATHS["09"]].output_paths()["result"],
                "phonons_path": self._pages[STABILITY_PATHS["10"]].output_paths()["result"],
                "phase_stability_path": self._pages[STABILITY_PATHS["11"]].output_paths()["result"],
            })
            self.stack.setCurrentWidget(self._pages[path])
        if self._active_project:
            self._active_project.settings = self._project_settings_snapshot()
        self._select_command_item(path)
        self.document_label.setText(f"{stage} / {self._pages[path].presentation.title}")
        self.statusBar().showMessage("已关联当前输入，核对本步参数与输出位置后运行。")

    def _open_relaxation_mixing(self) -> None:
        if self._active_project and self.workflow.settings.get("ten_micron_profile"):
            from ssscreen.gui.ten_micron_page import accept_cache

            accept_cache(self, stage=8)
            return
        page = self._pages.get(("stability", "relax"))
        results = page.validated_result() if page else None
        if not results or self._active_project is None:
            return
        self._open_stability_next("09")
        self.statusBar().showMessage("已带入06端元对及08弛豫结果；核对输出位置后计算混合焓。")

    def _open_sqs_relaxation(self) -> None:
        if self._active_project and self.workflow.settings.get("ten_micron_profile"):
            from ssscreen.gui.ten_micron_page import accept_cache

            accept_cache(self, stage=7)
            return
        page = self._pages.get(("stability", "sqs-generate"))
        manifest = page.validated_result() if page else None
        if not manifest or self._active_project is None:
            return
        path = ("stability", "relax")
        self._show_command_page(path)
        apply_command_values(self._pages[path], {
            "manifest_path": manifest,
            "dataset_path": self.composition_screen_page.structures_output.text(),
        })
        self._active_project.settings = self._project_settings_snapshot()
        self._select_command_item(path)
        self.document_label.setText("08 / MACE弛豫")
        self.statusBar().showMessage("已带入07 SQS清单及结构数据；核对模型和弛豫参数后运行08。")

    def _open_wavelength_sqs(self) -> None:
        page = self._pages.get(("pair-wavelength",))
        output = page.validated_result() if page else None
        if not output or self._active_project is None:
            return
        path = ("stability", "sqs-generate")
        self._show_command_page(path)
        updates = {
            "pairs_path": output,
            "dataset_path": self.composition_screen_page.structures_output.text(),
        }
        apply_command_values(self._pages[path], updates)
        self._active_project.settings = self._project_settings_snapshot()
        self._select_command_item(path)
        self.document_label.setText("07 / SQS合金")
        self.statusBar().showMessage("已带入06端元对及02结构数据；核对合金参数后运行07。")

    def _select_command_item(self, path: tuple[str, ...]) -> None:
        iterator = QTreeWidgetItemIterator(self.nav)
        while iterator.value():
            item = iterator.value()
            data = item.data(0, Qt.UserRole)
            if (
                data and data[0] == "command" and tuple(data[2]) == path
                and Path(data[1]).resolve() == self.project_root().resolve()
            ):
                item.parent().setExpanded(True)
                self.nav.setCurrentItem(item)
                self.nav.scrollToItem(item)
                self._navigation_clicked(item, 0)
                break
            iterator += 1

    def _gap_export_output(self) -> str:
        page = self._pages.get(("gap-export",))
        if page is not None:
            return page.output_edit.text()
        settings = self._active_project.settings if self._active_project else {}
        argv = (settings or {}).get("commands", {}).get("gap-export", [])
        if "--output" in argv:
            return argv[argv.index("--output") + 1]
        return "05_gap/带隙计算输入.zip"

    def _gap_validation_tasks(self) -> list[str]:
        """Reuse already registered calculation identities for CSV import."""
        settings = self._active_project.settings if self._active_project else {}
        argv = (settings or {}).get("commands", {}).get("gap-validate", [])
        sources = [argv[argv.index("--tasks") + 1]] if "--tasks" in argv else []
        values = (settings or {}).get("command_values", {}).get("gap-validate", {})
        if values.get("tasks_path"):
            sources.append(str(values["tasks_path"]))
        return list(dict.fromkeys(sources))

    def _use_collected_gaps(self) -> bool:
        """Bind verified Stage 05 output to downstream forms without executing them."""
        page = self._pages.get(("gap-collect-vasp",))
        output = page.validated_result() if page else None
        project = self._active_project
        if not output or project is None:
            return False
        settings = project.settings if project.settings is not None else {}
        project.settings = settings
        overrides = settings.setdefault("command_values", {})
        for key in ("pair-wavelength", "recommend"):
            path = (key,)
            command = self._command_lookup[path]
            updates = {}
            for option in command.params:
                if "--gap-results" in option.opts:
                    updates[option.name] = [output] if option.multiple else output
                elif key != "recommend" and "--groups" in option.opts:
                    groups = self.structure_match_page.groups_output.text()
                    updates[option.name] = [groups] if option.multiple else groups
            overrides.setdefault(key, {}).update(updates)
            if path in self._pages:
                apply_command_values(self._pages[path], updates)
        project.settings = self._project_settings_snapshot()
        return True

    def _open_collected_gap_pairing(self) -> None:
        if not self._use_collected_gaps():
            return
        self._show_command_page(("pair-wavelength",))
        iterator = QTreeWidgetItemIterator(self.nav)
        while iterator.value():
            item = iterator.value()
            data = item.data(0, Qt.UserRole)
            if (
                data
                and data[0] == "command"
                and tuple(data[2]) == ("pair-wavelength",)
                and Path(data[1]).resolve() == self.project_root().resolve()
            ):
                self.nav.setCurrentItem(item)
                self._navigation_clicked(item, 0)
                break
            iterator += 1
        self.document_label.setText("06 / 按目标波长筛选端元对")
        self.statusBar().showMessage("已带入05校验通过的带隙结果和04分组；核对目标波长后可运行配对。")

    # ---------------- Files / process ----------------

    def _refresh_file_tree(self) -> None:
        root = self.project_root()
        if not root.exists():
            self.files.setRootIndex(self.file_model.index(""))
            return

        index = self.file_model.setRootPath(str(root))
        self.files.setRootIndex(index)
        self.files.setColumnWidth(0, 360)

    def _open_selected_file(self, index) -> None:
        path = Path(self.file_model.filePath(index))
        if path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _show_file_context_menu(self, position) -> None:
        index = self.files.indexAt(position)

        if not index.isValid():
            return

        path = Path(
            self.file_model.filePath(index)
        ).resolve()

        # 这里只允许删除普通文件
        if not path.is_file():
            return

        project_root = self.project_root().resolve()

        # 安全检查：只能删除当前工程目录内部的文件
        try:
            path.relative_to(project_root)
        except ValueError:
            return

        menu = QMenu(self)

        delete_action = menu.addAction("删除文件")

        action = menu.exec(
            self.files.viewport().mapToGlobal(position)
        )

        if action == delete_action:
            self._delete_project_file(path)


    def _delete_project_file(self, path: Path) -> None:
        if not path.is_file():
            return

        project_root = self.project_root().resolve()
        path = path.resolve()

        try:
            relative = path.relative_to(project_root)
        except ValueError:
            QMessageBox.warning(
                self,
                "无法删除",
                "只能删除当前工程目录中的文件。",
            )
            return
        protected_files = {
        ".ssscreen-project.json",
        }

        if path.name in protected_files:
            QMessageBox.warning(
                self,
                "受保护的工程文件",
                f"{path.name} 是 SS-Screen 工程文件，不能在这里删除。",
            )
            return

        answer = QMessageBox.question(
            self,
            "确认删除文件",
            (
                "确定要永久删除这个文件吗？\n\n"
                f"{relative}\n\n"
                "此操作不可撤销。"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            path.unlink()
        except OSError as exc:
            QMessageBox.critical(
                self,
                "删除失败",
                f"无法删除文件：\n{path}\n\n{exc}",
            )
            return

        self.statusBar().showMessage(
            f"已删除文件：{relative}"
        )

        # 刷新相关界面
        self._refresh_file_tree()
        self._rebuild_project_tree()
        self.dashboard.refresh()
        self.structure_results_page.refresh()
        self.phonon_results_page.refresh()
        self.phase_results_page.refresh()
        self.detector_assessment_page.refresh()

    def run_command(self, argv: list[str], title: str) -> None:
        profile = self.workflow.settings.get("ten_micron_profile")
        if profile:
            from ssscreen.gui.ten_micron_page import accept_cache, validate_cache, marker
            slow = {
                ("condense",): 3, ("gap-export",): 5, ("gap-collect-vasp",): 5,
                ("stability", "sqs-generate"): 7, ("stability", "relax"): 8,
                ("stability", "phonon-run"): 10, ("stability", "phase-diagram"): 11,
            }
            stage = slow.get(tuple(argv[:2])) or slow.get(tuple(argv[:1]))
            if stage:
                self.workflow.select_stage(f"{stage:02}")
                accept_cache(self)
                return
            if argv[:1] == ["recommend"]:
                try:
                    if not marker(self.project_root(), 11).is_file():
                        raise ValueError("请先在 11 使用本算例的预计算结果")
                    validate_cache(self.project_root(),profile,11)
                except (OSError,ValueError,KeyError) as exc:
                    QMessageBox.warning(self, "检查算例输入", str(exc))
                    return
        if self.workflow.export_external(argv, title):
            return
        if self.process.state() != QProcess.NotRunning:
            QMessageBox.warning(self, "已有任务运行", "请等待当前任务结束，或先停止当前任务。")
            return

        project = self._active_project
        if project is None:
            QMessageBox.warning(self, "未选择工程", "请先新建或打开一个工程。")
            return

        root = project.path
        root.mkdir(parents=True, exist_ok=True)
        (root / "logs").mkdir(exist_ok=True)

        argv = list(argv)
        self._gap_collection_run = (
            (project.path, tuple(argv)) if argv[:1] == ["gap-collect-vasp"] else None
        )
        self._condense_stop_file = None
        self._stop_requested = False
        if argv and argv[0] == "condense":
            if "--stop-file" in argv:
                position = argv.index("--stop-file")
                del argv[position : position + 2]
            self._condense_stop_file = root / "logs" / f"condense-{uuid4().hex}.stop"
            argv.extend(["--stop-file", str(self._condense_stop_file)])
        self.structure_archive_page.stop_button.setEnabled(self._condense_stop_file is not None)

        backend_kind, backend_activate, backend_note = self._backend_for_command(argv)
        preview = self._command_preview(argv, backend_kind, backend_activate, root)
        self._current_run = RunRecord(
            started=datetime.now().isoformat(timespec="seconds"),
            command=preview,
        )

        self.log.appendPlainText("\n" + "=" * 90)
        self.log.appendPlainText(f"[PROJECT] {project.name}")
        self.log.appendPlainText(f"[TASK] {title}")
        self.log.appendPlainText(f"[CWD] {root}")
        if backend_note:
            self.log.appendPlainText(f"[GUI] {backend_note}")
        self.log.appendPlainText(f"[CMD] {preview}")
        self.log.appendPlainText("=" * 90)
        self.bottom_tabs.setCurrentWidget(self.log)
        self.run_state_label.setText(f"正在计算：{title}")
        self.run_progress.setVisible(True)
        self.run_progress.setRange(0, 0)

        env = QProcessEnvironment.systemEnvironment()
        key = self.api_key.text().strip()
        if key:
            env.insert("MP_API_KEY", key)
        env.insert("PYTHONUNBUFFERED", "1")

        self.process.setProcessEnvironment(env)
        self.process.setWorkingDirectory(str(root))
        if backend_kind == "wsl":
            program, args = self._wsl_process(argv, root, backend_activate)
        else:
            program = sys.executable
            args = ["-m", "ssscreen.cli.app", *argv]
        self.process.start(program, args)
        self.statusBar().showMessage(f"{project.name} · 运行中：{title}")

    def _recommended_wsl_activate(self, argv: list[str]) -> str:
        command_key = tuple(argv[:2])
        if command_key in MLP_COMMANDS:
            return WSL_MLP_VENV_ACTIVATE
        return WSL_VENV_ACTIVATE

    def _backend_for_command(self, argv: list[str]) -> tuple[str, str, str | None]:
        backend_kind, backend_activate = self.runtime_backend.currentData()
        if backend_kind == "wsl-auto":
            selected = self._recommended_wsl_activate(argv)
            return "wsl", selected, f"Auto backend selected: {selected}"

        command_key = tuple(argv[:2])
        if (
            backend_kind == "wsl"
            and backend_activate == WSL_MLP_VENV_ACTIVATE
            and command_key == ("stability", "sqs-generate")
        ):
            return (
                "wsl",
                WSL_VENV_ACTIVATE,
                "SQS generation uses .venv to read NumPy-2 pickle datasets; MACE stages still use .venv-mlp.",
            )

        return backend_kind, backend_activate, None

    def _command_preview(
        self,
        argv: list[str],
        backend_kind: str,
        backend_activate: str,
        root: Path,
    ) -> str:
        if backend_kind != "wsl":
            return shlex.join(["ss-screen", *argv])
        from ssscreen.gui.wsl import build_wsl_command

        converted = [self._windows_arg_to_wsl(value) for value in argv]
        command = build_wsl_command(
            self._wsl_root_for_project(root),
            self._windows_path_to_wsl(str(root)),
            backend_activate,
            converted,
        )
        return "wsl.exe bash -lc " + shlex.quote(command)

    def _wsl_process(
        self,
        argv: list[str],
        root: Path,
        backend_activate: str,
    ) -> tuple[str, list[str]]:
        from ssscreen.gui.wsl import build_wsl_command

        converted = [self._windows_arg_to_wsl(value) for value in argv]
        command = build_wsl_command(
            self._wsl_root_for_project(root),
            self._windows_path_to_wsl(str(root)),
            backend_activate,
            converted,
            api_key=self.api_key.text().strip(),
        )
        return "wsl.exe", ["bash", "-lc", command]

    def _wsl_root_for_project(self, root: Path) -> str:
        override = self.wsl_root.text().strip()
        if self.workflow.settings.get("ten_micron_profile") and not override:
            return self._windows_path_to_wsl(str(Path(__file__).resolve().parents[3]))
        if override:
            return override
        return self._windows_path_to_wsl(str(_find_project_root(root)))

    def _windows_arg_to_wsl(self, value: str) -> str:
        if PureWindowsPath(value).drive.lower().startswith(("\\\\wsl.localhost\\", "\\\\wsl$\\")):
            return self._windows_path_to_wsl(value)
        if len(value) >= 3 and value[1] == ":" and value[2] in {"\\", "/"}:
            return self._windows_path_to_wsl(value)
        return value.replace("\\", "/")

    def _windows_path_to_wsl(self, value: str) -> str:
        path = PureWindowsPath(value)
        if path.drive.lower().startswith(("\\\\wsl.localhost\\", "\\\\wsl$\\")):
            return "/" + "/".join(path.parts[1:])
        drive = path.drive.rstrip(":").lower()
        if not drive:
            return value.replace("\\", "/")
        parts = [part for part in path.parts[1:]]
        suffix = "/".join(part.replace("\\", "/") for part in parts)
        return f"/mnt/{drive}/{suffix}" if suffix else f"/mnt/{drive}"

    def stop_process(self) -> None:
        if self.process.state() == QProcess.NotRunning:
            self.statusBar().showMessage("当前没有运行中的任务")
            return
        if self._condense_stop_file is not None:
            try:
                self._condense_stop_file.write_text("stop\n", encoding="utf-8")
            except OSError as exc:
                QMessageBox.warning(self, "停止请求未发送", str(exc))
                return
            self._stop_requested = True
            self.structure_archive_page.stop_button.setEnabled(False)
            message = "已请求停止：当前结构结束后保存记录并退出，已完成描述可供 04 使用。"
            self.log.appendPlainText("\n[GUI] " + message)
            self.run_state_label.setText("正在停止：等待当前结构结束…")
            self.statusBar().showMessage(message)
            return
        self.log.appendPlainText("\n[GUI] 正在停止当前任务……")
        self.run_state_label.setText("正在停止任务…")
        self.process.terminate()
        if not self.process.waitForFinished(2000):
            self.process.kill()
        self.statusBar().showMessage("任务已停止")

    def _read_stdout(self) -> None:
        raw = bytes(self.process.readAllStandardOutput())
        self._append_log(self._decode_process_output(raw))

    def _read_stderr(self) -> None:
        raw = bytes(self.process.readAllStandardError())
        self._append_log(self._decode_process_output(raw))

    def _decode_process_output(self, raw: bytes) -> str:
        if not raw:
            return ""
        # Some WSL startup diagnostics are emitted with NUL bytes on this
        # Windows setup.  Decode them separately so the task log stays legible.
        if raw.count(b"\x00") > len(raw) // 8:
            return raw.decode("utf-16-le", errors="replace")
        return raw.decode("utf-8", errors="replace")

    def _append_log(self, text: str) -> None:
        if not text:
            return
        text = text.replace("\r", "\n")
        lines: list[str] = []
        suppressed_wsl_warning = False
        for line in text.splitlines(keepends=True):
            if "localhost" in line and ("WSL" in line or "�" in line):
                suppressed_wsl_warning = True
                continue
            lines.append(line)
        if suppressed_wsl_warning:
            lines.insert(
                0,
                "[WSL] Suppressed a Windows localhost/NAT startup warning.\n",
            )
        text = "".join(lines)
        if not text:
            return
        self.log.moveCursor(QTextCursor.End)
        self.log.insertPlainText(text)
        self.log.moveCursor(QTextCursor.End)
        if self.process.state() != QProcess.NotRunning and not self._stop_requested:
            last_line = next(
                (line.strip() for line in reversed(text.splitlines()) if line.strip()), ""
            )
            if last_line:
                self.run_state_label.setText(f"正在计算：{_compact_value(last_line, max_len=42)}")

    def _finished(self, exit_code: int, _exit_status) -> None:
        self.log.appendPlainText(f"\n[GUI] 任务结束，exit code = {exit_code}")
        self.statusBar().showMessage(f"任务结束 · 退出码 {exit_code}")
        self.run_progress.setVisible(False)
        self.run_state_label.setText("完成" if exit_code == 0 else f"结束：退出码 {exit_code}")
        stopped = self._condense_stop_file is not None and exit_code == 130
        if stopped:
            self.run_state_label.setText("已停止 · 已完成结果已保存")
            self.statusBar().showMessage("03 已停止，已完成描述与索引已保存，可继续 04。")
        self.structure_archive_page.stop_button.setEnabled(False)
        self._condense_stop_file = None
        self._stop_requested = False

        finished_command = self._current_run.command if self._current_run is not None else ""

        if self._current_run is not None:
            self._current_run.exit_code = exit_code
            self._write_run_audit(self._current_run)
            self._current_run = None

        self.dashboard.refresh()
        self.dataset_source_page.refresh_sources()
        self.composition_screen_page.refresh_inputs()
        self.composition_screen_page.refresh_results()
        self.structure_archive_page.refresh_archive()
        self.structure_match_page.refresh_inputs()
        self.structure_match_page.refresh_results()
        if ("gap-export",) in self._pages:
            self._pages[("gap-export",)].refresh_preview()
        if ("gap-collect-vasp",) in self._pages:
            collect_page = self._pages[("gap-collect-vasp",)]
            collect_page.refresh_preview()
            if exit_code == 0 and self._gap_collection_run == (
                self.project_root(), tuple(collect_page.argv())
            ):
                if self._use_collected_gaps():
                    self.statusBar().showMessage("05收集与校验完成，已衔接06端元配对。")
        self._gap_collection_run = None
        if ("pair-wavelength",) in self._pages:
            self._pages[("pair-wavelength",)].refresh_preview()
        if ("stability", "sqs-generate") in self._pages:
            self._pages[("stability", "sqs-generate")].refresh_preview()
        if ("stability", "relax") in self._pages:
            self._pages[("stability", "relax")].refresh_preview()
        self._refresh_stability_inputs()
        self.structure_results_page.refresh()
        self.phonon_results_page.refresh()
        self.phase_results_page.refresh()
        self.recommendation_report_page.refresh()
        self.detector_assessment_page.refresh()
        self._refresh_file_tree()
        self._rebuild_project_tree()

        if exit_code == 0 and " dataset mp " in f" {finished_command} ":
            mp_path = self.dataset_source_page._resolve(self.dataset_source_page.mp_output.text())
            if mp_path.is_file():
                self.composition_screen_page._append_dataframe(mp_path)
                self.composition_screen_page.refresh_inputs()
                self.dataset_source_page.select_section("local")
                self.stack.setCurrentWidget(self.dataset_source_page)

        if exit_code == 0 and " dataset wbm " in f" {finished_command} ":
            if self.dataset_source_page._resolve(self.dataset_source_page.wbm_output.text()).exists():
                self.dataset_source_page.select_section("local")
                self.stack.setCurrentWidget(self.dataset_source_page)

        if exit_code == 0 and " dataset structures " in f" {finished_command} ":
            if self.dataset_source_page._resolve(
                self.dataset_source_page.structures_output.text()
            ).exists():
                self.dataset_source_page.select_section("local")
                self.stack.setCurrentWidget(self.dataset_source_page)

        if exit_code == 0 and " composition-screen " in f" {finished_command} ":
            candidates_path = self.composition_screen_page._resolve(
                self.composition_screen_page.candidates_output.text()
            )
            summary_path = self.composition_screen_page._resolve(
                self.composition_screen_page.summary_output.text()
            )
            if candidates_path.exists() or summary_path.exists():
                self.composition_screen_page.select_section("candidates")
                self.stack.setCurrentWidget(self.composition_screen_page)

        if exit_code == 0 and " recommend " in f" {finished_command} ":
            self.recommendation_report_page.refresh()
            self.stack.setCurrentWidget(self.recommendation_report_page)

        if exit_code == 0 and " geometry-evaluate " in f" {finished_command} ":
            self.detector_assessment_page.refresh()
            self.stack.setCurrentWidget(self.detector_assessment_page)

        if self._handoff_after_stop:
            self._handoff_after_stop = False
            if stopped or exit_code == 0:
                self._use_completed_condense()
        if self._close_after_stop:
            self._close_after_stop = False
            self.close()

    def _write_run_audit(self, record: RunRecord) -> None:
        path = self.project_root() / "logs" / "gui_commands.jsonl"
        payload = {
            "timestamp": record.started,
            "project": self._active_project.name if self._active_project else None,
            "command": record.command,
            "exit_code": record.exit_code,
            "gui_version": __version__,
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError as exc:
            self.log.appendPlainText(f"[GUI] 无法写入命令审计日志：{exc}")

    def _process_error(self, error) -> None:
        self.log.appendPlainText(f"\n[GUI] QProcess 错误：{error}")
        self.run_state_label.setText(f"进程错误：{error}")

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.process.state() == QProcess.NotRunning:
            event.accept()
            return

        answer = QMessageBox.question(
            self,
            "任务仍在运行",
            "关闭 GUI 会停止当前任务。确认关闭吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            if self._condense_stop_file is not None:
                self._close_after_stop = True
                self.stop_process()
                event.ignore()
                return
            self.stop_process()
            event.accept()
        else:
            event.ignore()

    def _set_font_size(self, value: int) -> None:
        self._font_size = font_size(value)
        self.font_size_actions[self._font_size].setChecked(True)
        self._display_settings.setValue(FONT_SETTINGS_KEY, self._font_size)
        self._display_settings.sync()
        self._apply_style()

    def _refresh_font_layout(self, _index: int = 0) -> None:
        adapt_font_layout(self, self._font_size)
        if hasattr(self, "stack"):
            # Inactive plot pages have wide minimum hints. The compact collector
            # must fit the visible viewport instead of inheriting their width.
            policy = self.stack.sizePolicy()
            policy.setVerticalPolicy(
                QSizePolicy.Ignored
                if isinstance(self.stack.currentWidget(), PhaseResultsPage)
                else QSizePolicy.Preferred
            )
            policy.setHorizontalPolicy(
                QSizePolicy.Ignored
                if isinstance(self.stack.currentWidget(), (GapCollectPage, WavelengthPairPage, SqsPage, RelaxPage, StabilityPage, PhaseResultsPage))
                else QSizePolicy.Preferred
            )
            self.stack.setSizePolicy(policy)
            self.stack.updateGeometry()
        if hasattr(self, "inspector"):
            for form in self.inspector.findChildren(QFormLayout):
                form.setRowWrapPolicy(QFormLayout.WrapAllRows)
            self.runtime_backend.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            self.runtime_backend.setMinimumContentsLength(12)

    def _apply_style(self) -> None:
        # Dense neutral palette inspired by CAE/engineering desktop tools.
        font = QFont(QApplication.instance().font())
        font.setPointSize(self._font_size)
        QApplication.instance().setFont(font)
        self.setFont(font)
        stylesheet = """
            QMainWindow, QWidget {
                background: #e9eaec;
                color: #202428;
            }
            #titleBar {
                background: #30353a;
                border-bottom: 1px solid #1f2327;
                min-height: 28px;
            }
            #productMark {
                color: #ffffff;
                font-size: 13px;
                font-weight: 700;
                letter-spacing: 0;
            }
            #productSubtitle {
                color: #cbd0d5;
                font-size: 11px;
            }
            #activeProjectLabel {
                color: #e6e9ec;
                font-size: 11px;
            }
            #runStateLabel {
                color: #384047;
                font-size: 10px;
                min-width: 160px;
            }
            #runProgress {
                min-height: 12px;
                max-height: 12px;
                border: 1px solid #a8adb3;
                background: #eef0f2;
                text-align: center;
            }
            #runProgress::chunk {
                background: #506d86;
            }
            #toolBar {
                background: #d7d9dc;
                border-bottom: 1px solid #aeb2b7;
                min-height: 34px;
            }
            #toolButton, #stopButton, QToolButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 2px;
                padding: 4px 8px;
                min-height: 20px;
            }
            #toolButton:hover {
                background: #eef0f2;
                border-color: #aeb3b9;
            }
            #stopButton {
                color: #8c2424;
            }
            #stopButton:hover {
                background: #f2dddd;
                border-color: #c89a9a;
            }
            #toolbarSeparator {
                color: #a8acb1;
                margin-left: 3px;
                margin-right: 3px;
            }
            #projectPanel, #inspectorFrame {
                background: #f0f1f2;
                border: 0;
            }
            #projectPanel {
                border-right: 1px solid #9fa4aa;
            }
            #inspectorFrame {
                border-left: 1px solid #9fa4aa;
            }
            #panelHeader {
                background: #d1d4d7;
                border-bottom: 1px solid #9ea3a8;
                color: #2b3035;
                font-size: 11px;
                font-weight: 600;
                padding: 5px 7px;
                min-height: 18px;
            }
            #navigation {
                background: #f5f6f7;
                border: 0;
                outline: none;
                alternate-background-color: #eef0f2;
                font-size: 11px;
            }
            #navigation::item {
                min-height: 21px;
                padding: 1px 2px;
                border: 0;
            }
            #navigation::item:selected {
                background: #b8c9da;
                color: #17212b;
            }
            #navigation::item:hover {
                background: #dce4eb;
            }
            QHeaderView::section {
                background: #d6d8db;
                color: #30353a;
                border: 0;
                border-right: 1px solid #b3b6ba;
                border-bottom: 1px solid #a7abb0;
                padding: 4px 5px;
                font-size: 10px;
                font-weight: 600;
            }
            #documentFrame {
                background: #f7f7f8;
                border: 0;
            }
            #documentHeader {
                background: #e0e2e4;
                border-bottom: 1px solid #aeb2b7;
                min-height: 25px;
            }
            #documentTitle {
                color: #30353a;
                font-size: 11px;
                font-weight: 600;
            }
            #pageTitle {
                color: #202428;
                font-size: 16px;
                font-weight: 600;
            }
            #breadcrumb, #commandName {
                color: #56616b;
                font-size: 10px;
                font-family: Consolas, monospace;
            }
            #pageDescription {
                color: #4f5962;
                font-size: 11px;
            }
            #panelTitle {
                color: #202428;
                font-size: 12px;
                font-weight: 600;
                padding: 2px;
            }
            #stateBadge {
                background: #4f6577;
                color: white;
                border-radius: 2px;
                padding: 2px 7px;
                font-size: 9px;
                font-weight: 600;
            }
            #smallLabel, #optionHelp {
                color: #69737c;
                font-size: 9px;
            }
            QGroupBox {
                background: #f5f6f7;
                border: 1px solid #b8bcc1;
                border-radius: 1px;
                margin-top: 10px;
                padding-top: 7px;
                font-size: 10px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 7px;
                padding: 0 3px;
                color: #384047;
            }
            QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextBrowser, QTableWidget, QTreeView {
                background: #ffffff;
                border: 1px solid #adb2b7;
                border-radius: 1px;
                padding: 3px;
                selection-background-color: #9fb8cf;
                selection-color: #111820;
                font-size: 10px;
            }
            QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
                border-color: #5e7e9b;
            }
            #reportViewer {
                background: #ffffff;
                color: #202428;
                font-size: 11px;
                padding: 8px;
            }
            QPushButton {
                background: #e7e8ea;
                border: 1px solid #aeb2b7;
                border-radius: 2px;
                padding: 4px 9px;
                min-height: 20px;
                font-size: 10px;
            }
            QPushButton:hover {
                background: #f4f5f6;
                border-color: #8f959b;
            }
            #primaryButton {
                background: #506d86;
                color: white;
                border-color: #3e596f;
                font-weight: 600;
            }
            #primaryButton:hover {
                background: #607f99;
            }
            #commandPreview, #logConsole, #messageConsole {
                background: #1f2428;
                color: #d6d9dc;
                border: 1px solid #15191c;
                font-family: Consolas, monospace;
                font-size: 10px;
            }
            #bottomTabs::pane {
                border-top: 1px solid #9fa4aa;
                background: #f2f3f4;
            }
            QTabBar::tab {
                background: #d6d8db;
                border-right: 1px solid #b0b4b9;
                padding: 4px 12px;
                min-height: 18px;
                font-size: 10px;
            }
            QTabBar::tab:selected {
                background: #f2f3f4;
                font-weight: 600;
            }
            QTabWidget::pane {
                border: 1px solid #aeb2b7;
                background: #f7f7f8;
            }
            QTableWidget {
                gridline-color: #c6c9cc;
            }
            #groupsTable {
                background: #ffffff;
            }
            #statusBar {
                background: #d2d4d6;
                border-top: 1px solid #a8acb1;
                color: #3e454c;
                font-size: 9px;
            }

            QTableWidget::item {
                min-height: 22px;
                padding: 3px 5px;
            }
            QScrollBar:vertical {
                background: #e2e4e6;
                width: 12px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #a7adb3;
                min-height: 26px;
                border-radius: 2px;
            }
            QScrollBar:horizontal {
                background: #e2e4e6;
                height: 12px;
                margin: 0;
            }
            QScrollBar::handle:horizontal {
                background: #a7adb3;
                min-width: 26px;
                border-radius: 2px;
            }
            QSplitter::handle {
                background: #aeb2b7;
            }
            QMenuBar, QMenu {
                background: #f5f6f7;
                color: #202428;
            }
            QMenuBar {
                border-bottom: 1px solid #aeb2b7;
            }
            QMenuBar::item {
                background: transparent;
                padding: 4px 12px;
            }
            QMenuBar::item:selected, QMenu::item:selected {
                background: #dce4eb;
                color: #17212b;
            }
            QMenu {
                border: 1px solid #aeb2b7;
            }
            QMenu::item {
                padding: 5px 24px;
            }
            QMenu::indicator:exclusive {
                width: 10px;
                height: 10px;
                border: 1px solid #9ea3a8;
                border-radius: 5px;
                background: #ffffff;
            }
            QMenu::indicator:exclusive:checked {
                background: #506d86;
                border-color: #3e596f;
            }
            QMenu::separator {
                height: 1px;
                background: #c6c9cc;
                margin: 4px 8px;
            }
            """
        self.setStyleSheet(font_stylesheet(stylesheet, self._font_size))
        self.command_toolbar.setIconSize(QSize(self.fontMetrics().height(), self.fontMetrics().height()))
        self._refresh_font_layout()
        for viewer in self.findChildren(MatterVizView):
            viewer.setZoomFactor(self._font_size / DEFAULT_FONT_SIZE)


def run_gui(project_dir: str | None = None) -> int:
    """Run the desktop workbench and return the Qt application exit code."""
    app = QApplication.instance()
    if app is None:
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        app = QApplication([sys.argv[0]])
    if os.name == "nt" and not QFontDatabase.families():
        for filename in ("segoeui.ttf", "msyh.ttc", "consola.ttf"):
            QFontDatabase.addApplicationFont(str(Path(os.environ["WINDIR"]) / "Fonts" / filename))
        app.setFont(QFont("Microsoft YaHei UI", DEFAULT_FONT_SIZE))
    app.setApplicationName("SS-Screen")
    window = MainWindow(project_dir=project_dir)
    window.show()
    return app.exec()


def main() -> int:
    project_dir = sys.argv[1] if len(sys.argv) > 1 else None
    return run_gui(project_dir=project_dir)


if __name__ == "__main__":
    raise SystemExit(main())
