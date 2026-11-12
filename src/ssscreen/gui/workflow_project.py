"""Saved workflow settings for the native workbench (no scientific execution)."""

from __future__ import annotations

import csv
import json
import shlex
from pathlib import Path


def read_project(root: Path) -> dict:
    path = root / ".ssscreen-project.json"
    if not path.is_file():
        container = root / ".ssscreen" / "project.json"
        if not container.is_file():
            return {}
        project = json.loads(container.read_text(encoding="utf-8-sig"))
        settings = project.get("settings", {})
        return {
            "name": project.get("name"),
            "gui_settings": settings,
            "artifacts": settings.get("artifact_aliases", {}),
        }
    return json.loads(path.read_text(encoding="utf-8-sig"))


def imported_artifact(root: Path, value: str) -> Path:
    """Prefer a newly generated artifact; otherwise use its recorded source."""
    path = Path(value)
    if path.is_absolute():
        return path
    local = root / path
    if local.exists():
        return local
    source = read_project(root).get("artifacts", {}).get(path.as_posix())
    return Path(source) if source else local


def mp_output_paths(root: Path, database: str = "") -> tuple[str, str]:
    """Default MP outputs beside the selected database, relative to the project if possible."""
    root = root.resolve()
    parent = (
        imported_artifact(root, database.strip()).expanduser().resolve().parent
        if database.strip()
        else root / "01_dataset"
    )
    paths = []
    for name in ("mp.df", "mp.df.provenance.json"):
        path = parent / name
        try:
            path = path.relative_to(root)
        except ValueError:
            pass
        paths.append(path.as_posix())
    return paths[0], paths[1]


def capture_forms(window) -> dict:
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QLineEdit,
        QSpinBox,
    )

    result = {}
    for name in FORM_PAGES:
        page = getattr(window, name)
        values = {}
        for key, widget in vars(page).items():
            if isinstance(widget, QLineEdit):
                values[key] = widget.text()
            elif isinstance(widget, QCheckBox):
                values[key] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                values[key] = widget.currentText()
            elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                values[key] = widget.value()
        if hasattr(page, "_dataframe_paths"):
            values["dataframes"] = [str(p) for p in page._dataframe_paths()]
        if hasattr(page, "_archive_paths"):
            values["archives"] = [str(p) for p in page._archive_paths()]
        result[name] = values
    return result


FORM_PAGES = (
    "dataset_source_page",
    "composition_screen_page",
    "structure_archive_page",
    "structure_match_page",
    "detector_assessment_page",
)


def restore_forms(window, forms: dict) -> None:
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QLineEdit,
        QSpinBox,
    )

    for name, values in forms.items():
        if name not in FORM_PAGES:
            continue
        page = getattr(window, name)
        values = dict(values)
        if name == "composition_screen_page" and "nelems_edit" in values:
            # Legacy projects selected one element count in a text field.
            count = str(values.pop("nelems_edit"))
            values.setdefault("binary_enabled", count == "2")
            values.setdefault("ternary_enabled", count == "3")
        if name == "structure_archive_page" and "df_path" in values:
            values.setdefault("df_follow_composition", False)
        if name == "structure_match_page" and ("candidates_edit" in values or "archives" in values):
            values.setdefault("follow_stage03", False)
        if name == "dataset_source_page":
            page._restoring_mp_settings = True
        for key, value in values.items():
            widget = getattr(page, key, None)
            if isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QComboBox):
                index = widget.findData(value)
                if index < 0:
                    index = widget.findText(str(value))
                if index >= 0:
                    widget.setCurrentIndex(index)
            elif isinstance(widget, (QDoubleSpinBox, QSpinBox)):
                widget.setValue(value)
        if name == "dataset_source_page":
            # Old saved projects keep their explicit output paths. New projects
            # persist the follow-input checkbox with the other native controls.
            if "mp_output_follow_input" not in values and (
                "mp_output" in values or "mp_provenance" in values
            ):
                page.mp_output_follow_input.setChecked(False)
            page._restoring_mp_settings = False
            page._sync_mp_output_paths()
        if "dataframes" in values:
            page.df_table.setRowCount(0)
            for path in values["dataframes"]:
                page._append_dataframe(path)
        if "archives" in values:
            page.archive_table.setRowCount(0)
            for path in values["archives"]:
                page._append_archive(Path(path))
    if hasattr(window, "_sync_composition_archive_input"):
        window._sync_composition_archive_input()
    if hasattr(window, "_sync_structure_match_inputs"):
        window._sync_structure_match_inputs()


def apply_command_values(page, values: dict) -> None:
    if hasattr(page, "apply_values"):
        page.apply_values(values)
        return
    for option, editor in page.editors:
        if option.name in values:
            editor.set_value(values[option.name])
    page.refresh_preview()


class WorkflowController:
    """Bind a saved run to the existing native pages, controls and viewers."""

    def __init__(self, window):
        from PySide6.QtWidgets import QComboBox, QLabel, QToolBar

        self.window = window
        self.stage = "01"
        self.toolbar = QToolBar("工程流程", window)
        self.toolbar.setMovable(False)
        window.addToolBarBreak()
        window.addToolBar(self.toolbar)
        self.caption = QLabel()
        self.toolbar.addWidget(self.caption)
        self.toolbar.addSeparator()
        from .ten_micron_page import accept_cache
        self.cache_action = self.toolbar.addAction("使用预计算结果并进入下一步",lambda: accept_cache(window))
        self.toolbar.addAction("本步参数", self.show_parameters)
        self.toolbar.addAction("本步结果", self.show_results)
        self.toolbar.addAction("结果清单 / 来源", self.show_tables)
        self.toolbar.addSeparator()
        self.variants = QComboBox()
        self.variants.setMinimumWidth(240)
        self.variants.activated.connect(self.apply_variant)
        self.variants_action = self.toolbar.addWidget(self.variants)
        self.toolbar.setVisible(False)
        self.results_page = None
        self.geometry_settings = None

    @property
    def settings(self):
        project = self.window._active_project
        return (project.settings or {}) if project else {}

    def refresh(self):
        self.toolbar.setVisible(bool(self.settings.get("workflow_stages")))
        self.select_stage(self.stage)
        geometry = self.window.detector_assessment_page
        external = "geometry-evaluate" in self.settings.get("external_commands", [])
        geometry.geometry_button.setText("导出几何计算命令" if external else "计算几何指标")
        if self.settings.get("workflow_stages"):
            if self.geometry_settings is None:
                self.geometry_settings = make_geometry_settings(self.window)
                geometry.tabs.addTab(self.geometry_settings, "几何计算参数")
            self.geometry_settings.load()

    def select_stage(self, sid):
        from ..ten_micron import CACHED
        self.stage = sid
        self.cache_action.setVisible(bool(self.settings.get("ten_micron_profile")) and sid.isdigit() and int(sid) in CACHED)
        stage = self.settings.get("workflow_stages", {}).get(sid, {})
        self.caption.setText(f"  {sid} {stage.get('name', '')} · {stage.get('status', '')}  ")
        self.caption.setToolTip(stage.get("note", ""))
        self.variants.clear()
        for variant in self.settings.get("variants", {}).get(sid, []):
            if sid in {"07", "08", "09", "10", "11"}:
                continue  # These stages now follow their current upstream forms.
            self.variants.addItem(variant["label"], variant)
        self.variants_action.setVisible(self.variants.count() > 0)

    def show_parameters(self):
        w = self.window
        command = self.settings.get("stage_commands", {}).get(self.stage)
        if self.stage == "06":
            command = ("pair-wavelength",)
        elif self.stage == "07":
            command = ("stability", "sqs-generate")
        elif self.stage == "08":
            command = ("stability", "relax")
        elif self.stage in {"09", "10", "11"}:
            from .stability_page import STABILITY_PATHS

            command = STABILITY_PATHS[self.stage]
        if command:
            w._show_command_page(tuple(command))
        elif self.stage == "13":
            w.detector_assessment_page.refresh()
            w.stack.setCurrentWidget(w.detector_assessment_page)
        w.document_label.setText(f"{w._active_project.name} / {self.stage} 参数设置")
        stage = self.settings.get("workflow_stages", {}).get(self.stage, {})
        w.statusBar().showMessage(stage.get("note", ""))

    def apply_variant(self, index):
        variant = self.variants.itemData(index)
        if not variant:
            return
        restore_forms(self.window, variant.get("forms", {}))
        for key, values in variant.get("command_values", {}).items():
            path = tuple(key.split())
            if path not in self.window._command_lookup:
                continue
            self.window._show_command_page(path)
            apply_command_values(self.window._pages[path], values)
        self.show_parameters()
        self.window.statusBar().showMessage(variant.get("note", variant["label"]))

    def show_results(self):
        w = self.window
        pages = {
            "08": w.structure_results_page,
            "10": w.phonon_results_page,
            "11": w.phase_results_page,
            "12": w.recommendation_report_page,
            "13": w.detector_assessment_page,
        }
        if self.stage in pages:
            page = pages[self.stage]
            page.refresh()
            w.stack.setCurrentWidget(page)
            w.document_label.setText(f"{w._active_project.name} / {self.stage} 计算结果")
        else:
            self.show_tables()

    def show_tables(self):
        if self.results_page is None:
            self.results_page = make_results_page(self.window)
            self.window.stack.addWidget(self.results_page)
        stage = self.settings.get("workflow_stages", {}).get(self.stage, {})
        self.results_page.show_stage(stage)
        self.window.stack.setCurrentWidget(self.results_page)
        self.window.document_label.setText(
            f"{self.window._active_project.name} / {self.stage} 结果清单"
        )

    def configure_command(self, page):
        key = " ".join(page.presentation.command_path)
        values = self.settings.get("command_values", {}).get(key, {})
        apply_command_values(page, values)
        external = key in self.settings.get("external_commands", [])
        default_label = {"gap-export": "导出计算压缩包", "gap-collect-vasp": "开始收集结果"}.get(
            key, "运行任务"
        )
        if hasattr(page, "set_external_mode"):
            page.set_external_mode(external)
        elif not external and key in {"pair-wavelength", "stability sqs-generate"}:
            page.run_button.setText("生成 SQS" if key == "stability sqs-generate" else "筛选端元对")
            page.refresh_preview()
        elif not external and key == "gap-collect-vasp":
            page.refresh_preview()
        else:
            page.run_button.setText("导出外部执行命令" if external else default_label)

    def export_external(self, argv, title) -> bool:
        if not any(
            argv[: len(key.split())] == key.split()
            for key in self.settings.get("external_commands", [])
        ):
            return False
        root = self.window.project_root()
        target = root / "external_commands"
        target.mkdir(exist_ok=True)
        name = "_".join(argv[:2]) if argv[0] == "stability" else argv[0]
        path = target / f"{name}.json"
        payload = {
            "title": title,
            "argv": argv,
            "local_working_directory": str(root),
            "note": "命令记录；外部机器须映射输入、输出、模型路径。未启动本地计算。",
            "existing_bundles": self.settings.get("external_bundles", []),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(shlex.join(["ss-screen", *argv]))
        self.window.log.appendPlainText(
            f"[外部执行] {title}\n命令已复制；文件：{path}\n{payload['note']}"
        )
        self.window.bottom_tabs.setCurrentWidget(self.window.log)
        self.window.statusBar().showMessage(f"已导出命令：{path}")
        return True


def make_results_page(window):
    from PySide6.QtCore import QAbstractTableModel, QSortFilterProxyModel, Qt, QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import (
        QComboBox,
        QLabel,
        QLineEdit,
        QPushButton,
        QTableView,
        QVBoxLayout,
        QWidget,
    )

    class CsvModel(QAbstractTableModel):
        def __init__(self, rows, columns, parent):
            super().__init__(parent)
            self.rows, self.columns = rows, columns

        def rowCount(self, parent=None):
            return 0 if parent is not None and parent.isValid() else len(self.rows)

        def columnCount(self, parent=None):
            return 0 if parent is not None and parent.isValid() else len(self.columns)

        def data(self, index, role=Qt.DisplayRole):
            if index.isValid() and role in (Qt.DisplayRole, Qt.ToolTipRole):
                return self.rows[index.row()].get(self.columns[index.column()], "")

        def headerData(self, section, orientation, role=Qt.DisplayRole):
            if role == Qt.DisplayRole:
                return self.columns[section] if orientation == Qt.Horizontal else str(section + 1)

    class Results(QWidget):
        def __init__(self):
            super().__init__()
            layout = QVBoxLayout(self)
            self.note = QLabel()
            self.note.setWordWrap(True)
            layout.addWidget(self.note)
            self.selector = QComboBox()
            self.selector.currentIndexChanged.connect(self.load_table)
            layout.addWidget(self.selector)
            self.search = QLineEdit()
            self.search.setPlaceholderText("搜索材料、编号或状态（所有列）")
            layout.addWidget(self.search)
            self.table = QTableView()
            self.table.setAlternatingRowColors(True)
            layout.addWidget(self.table, 1)
            self.source = QComboBox()
            layout.addWidget(self.source)
            button = QPushButton("打开选中的原始文件 / 目录")
            button.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.source.currentText()))
            )
            layout.addWidget(button)
            self.proxy = QSortFilterProxyModel(self)
            self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
            self.proxy.setFilterKeyColumn(-1)
            self.search.textChanged.connect(self.proxy.setFilterFixedString)
            self.table.setModel(self.proxy)

        def show_stage(self, stage):
            self.note.setText(
                f"{stage.get('id', '')} {stage.get('name', '')} · {stage.get('status', '')}\n{stage.get('note', '')}"
            )
            self.search.clear()
            self.selector.clear()
            for table in stage.get("tables", []):
                self.selector.addItem(
                    f"{table['label']} · {table.get('rows', '')} 行", table["path"]
                )
            self.source.clear()
            self.source.addItems([s["path"] for s in stage.get("sources", [])])

        def load_table(self, index):
            value = self.selector.itemData(index)
            if not value:
                return
            path = Path(value)
            if not path.is_absolute():
                path = window.project_root() / path
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
                columns = reader.fieldnames or []
            old = self.proxy.sourceModel()
            self.proxy.setSourceModel(CsvModel(rows, columns, self))
            if old:
                old.deleteLater()
            for column in range(len(columns)):
                self.table.setColumnWidth(column, 155)

    return Results()


def make_geometry_settings(window):
    """Edit scalar geometry settings using the workbench's original form style."""
    from PySide6.QtWidgets import (
        QCheckBox,
        QDoubleSpinBox,
        QFormLayout,
        QGroupBox,
        QLabel,
        QLineEdit,
        QPushButton,
        QScrollArea,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )

    class GeometrySettings(QScrollArea):
        def __init__(self):
            super().__init__()
            self.setWidgetResizable(True)
            self.setMinimumHeight(250)
            self.payload = {}
            self.editors = []

        def load(self):
            page = window.detector_assessment_page
            path = page._resolve(page.geometry_config.text())
            if not path.is_file():
                return
            self.payload = json.loads(path.read_text(encoding="utf-8-sig"))
            body = QWidget()
            layout = QVBoxLayout(body)
            self.editors = []
            note = QLabel("参数用于外部几何计算；合金带隙未启用。修改后点击保存，再导出计算命令。")
            note.setWordWrap(True)
            layout.addWidget(note)
            for section, label in (
                ("detector_context", "目标波长 / 应用条件"),
                ("lattice", "端元晶格匹配"),
                ("substrate", "衬底匹配"),
                ("existing_property_thresholds", "已有材料性质阈值"),
                ("execution", "执行设置"),
            ):
                group = QGroupBox(label)
                form = QFormLayout(group)
                for key, value in self.payload.get(section, {}).items():
                    if isinstance(value, (dict, list)) or value is None:
                        continue
                    if isinstance(value, bool):
                        editor = QCheckBox()
                        editor.setChecked(value)
                    elif isinstance(value, int):
                        editor = QSpinBox()
                        editor.setRange(-100000000, 100000000)
                        editor.setValue(value)
                    elif isinstance(value, float):
                        editor = QDoubleSpinBox()
                        editor.setDecimals(8)
                        editor.setRange(-1e9, 1e9)
                        editor.setValue(value)
                    else:
                        editor = QLineEdit(str(value))
                    form.addRow(key, editor)
                    self.editors.append((section, key, editor))
                layout.addWidget(group)
            button = QPushButton("保存到本工程几何配置")
            button.clicked.connect(self.save)
            layout.addWidget(button)
            self.message = QLabel(str(path))
            self.message.setWordWrap(True)
            layout.addWidget(self.message)
            self.setWidget(body)

        def save(self):
            for section, key, editor in self.editors:
                if isinstance(editor, QCheckBox):
                    value = editor.isChecked()
                elif isinstance(editor, (QDoubleSpinBox, QSpinBox)):
                    value = editor.value()
                else:
                    value = editor.text()
                self.payload[section][key] = value
            page = window.detector_assessment_page
            path = page._resolve(page.geometry_config.text())
            path.parent.mkdir(exist_ok=True)
            path.write_text(
                json.dumps(self.payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            window.detector_assessment_page.geometry_config.setText(str(path))
            self.message.setText(f"已保存：{path}")

    return GeometrySettings()
