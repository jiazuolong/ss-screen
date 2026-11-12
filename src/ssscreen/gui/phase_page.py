"""Per-target phase plots produced by the calculation environment."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from PySide6.QtCore import QSettings, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .sqs_results import file_sha256, resolve_path
from .workflow_project import imported_artifact


def read_plot_index(path: Path) -> tuple[dict, dict[str, list[dict]]]:
    index = json.loads(path.read_text(encoding="utf-8"))
    if index.get("schema_version") != 1 or not index.get("plots"):
        raise ValueError("相图索引为空或版本不支持。")
    entries = path.parent / index["entries"]
    if file_sha256(entries) != index["entries_sha256"]:
        raise ValueError("绘图明细已变化，请重新绘图。")
    scope = resolve_path(path.parent, index["scope_summary"])
    if file_sha256(scope) != index["scope_summary_sha256"]:
        raise ValueError("相稳定性结果已变化，请重新绘图。")
    groups = {}
    with entries.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            groups.setdefault(row["target_structure_id"], []).append(row)
    ids = [plot["target_structure_id"] for plot in index["plots"]]
    if len(set(ids)) != len(ids) or set(ids) != set(groups):
        raise ValueError("相图与竞争相分组不一致。")
    return index, groups


class PhaseResultsPage(QWidget):
    def __init__(self, project_provider, parent=None, *, settings=None):
        super().__init__(parent)
        from .visualization import MatterVizView, ScaledImage

        self.project_provider = project_provider
        self.settings = settings if settings is not None else QSettings("SS-Screen", "Desktop")
        self.index, self.groups, self.rows = {}, {}, []
        self.index_path = Path()
        root = QVBoxLayout(self)
        title = QLabel("竞争相与凸包结果")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("目标合金"))
        self.selector = QComboBox()
        self.selector.setMinimumContentsLength(20)
        self.selector.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.selector.currentIndexChanged.connect(self._target_changed)
        toolbar.addWidget(self.selector, 1)
        load = QPushButton("加载相图")
        load.clicked.connect(self._choose_index)
        toolbar.addWidget(load)
        refresh = QPushButton("刷新结果")
        refresh.clicked.connect(self.refresh)
        toolbar.addWidget(refresh)
        root.addLayout(toolbar)
        self.count_label = QLabel()
        self.count_label.setWordWrap(True)
        self.count_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        root.addWidget(self.count_label)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        plot_page = QWidget()
        plot_layout = QVBoxLayout(plot_page)
        self.image = ScaledImage()
        self.image.setMinimumSize(360, 280)
        self.image.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        plot_layout.addWidget(self.image, 1)
        exports = QHBoxLayout()
        self.png_button, self.svg_button = QPushButton("打开原图 PNG"), QPushButton(
            "打开矢量图 SVG"
        )
        self.png_button.clicked.connect(lambda: self._open_plot("png"))
        self.svg_button.clicked.connect(lambda: self._open_plot("svg"))
        exports.addStretch()
        exports.addWidget(self.png_button)
        exports.addWidget(self.svg_button)
        plot_layout.addLayout(exports)
        self.tabs.addTab(plot_page, "相图")
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["相结构 ID", "组成", "角色", "凸包距离 (eV/atom)", "目标"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, 5):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.tabs.addTab(self.table, "当前目标的竞争相")
        self.viewer = MatterVizView()
        self.tabs.addTab(self.viewer, "所选相结构（MatterViz）")
        root.addWidget(self.tabs, 1)
        self.refresh()

    def _root(self):
        return Path(self.project_provider()).expanduser().resolve()

    def _settings_key(self):
        project_id = hashlib.sha256(str(self._root()).casefold().encode()).hexdigest()
        return f"phase_plot_indexes/{project_id}"

    def set_plot_index(self, path: Path):
        read_plot_index(path)
        self.settings.setValue(self._settings_key(), str(path.resolve()))
        self.settings.sync()
        self.refresh()

    def _choose_index(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "加载相图索引", str(self._root()), "相图索引 (phase_plot_index.json)"
        )
        if path:
            try:
                self.set_plot_index(Path(path))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                QMessageBox.warning(self, "无法加载相图", str(exc))

    def refresh(self):
        previous = self.selector.currentData()
        self.selector.blockSignals(True)
        self.selector.clear()
        self.index, self.groups, self.rows = {}, {}, []
        self.table.setRowCount(0)
        path = self.settings.value(self._settings_key(), "")
        self.index_path = (
            Path(path)
            if path
            else imported_artifact(self._root(), "11_phase/phase_plot_index.json")
        )
        try:
            self.index, self.groups = read_plot_index(self.index_path)
            for plot in self.index["plots"]:
                label = (
                    f"配对 {plot['pair_index']} · {plot['composition']} · {plot['chemical_system']}"
                )
                self.selector.addItem(label, plot["target_structure_id"])
            position = self.selector.findData(previous)
            self.selector.setCurrentIndex(max(position, 0))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.count_label.setText(
                "尚无可用相图，请加载 phase_plot_index.json。完整数值见“结果清单 / 来源”。"
            )
            self.count_label.setToolTip(str(exc))
        self.selector.blockSignals(False)
        self._target_changed()

    def _plot(self):
        target = self.selector.currentData()
        return next(
            (p for p in self.index.get("plots", []) if p["target_structure_id"] == target), None
        )

    def _plot_path(self, kind):
        plot = self._plot()
        if not plot:
            return None
        path = self.index_path.parent / plot[kind]
        if not path.is_file() or file_sha256(path) != plot[f"{kind}_sha256"]:
            return None
        return path

    def _target_changed(self):
        self.table.setRowCount(0)
        self.rows = self.groups.get(self.selector.currentData(), [])
        plot = self._plot()
        path = self._plot_path("png")
        self.image.set_image(path or Path())
        if not path:
            self.image.setText("尚无可用相图，或图片文件已变化。")
        self.png_button.setEnabled(path is not None)
        self.svg_button.setEnabled(self._plot_path("svg") is not None)
        self.tabs.setTabEnabled(2, False)
        if plot:
            self.count_label.setText(
                f"{self.selector.count()} 个目标 · 当前 {len(self.rows)} 个相 · 目标凸包距离 "
                f"{plot['energy_above_hull_eV_per_atom']:.6f} eV/atom。"
                "\n0 K MACE能量凸包；包含目标合金，绿点为稳定相，黄点为凸包上方相，红星为目标。"
            )
            self.count_label.setToolTip(str(self.index_path))
        for row in self.rows:
            target = row["is_target"].lower() == "true"
            values = [
                row["phase_structure_id"],
                row["phase_composition"],
                "目标合金" if target else ("其他合金" if row["phase_role"] == "sqs" else "竞争相"),
                f"{float(row['phase_e_above_augmented_hull_eV_per_atom']):.6f}",
                "是" if target else "否",
            ]
            position = self.table.rowCount()
            self.table.insertRow(position)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(position, column, item)
        if self.rows:
            target_row = next(
                i for i, row in enumerate(self.rows) if row["is_target"].lower() == "true"
            )
            self.table.selectRow(target_row)

    def _open_plot(self, kind):
        path = self._plot_path(kind)
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _selection_changed(self):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return
        row = self.rows[indexes[0].row()]
        key = "candidate_structures" if row["phase_role"] == "sqs" else "competing_structures"
        directory = self.index.get(key)
        path = (
            resolve_path(self.index_path.parent, directory) / f"{row['phase_structure_id']}.json"
            if directory
            else Path()
        )
        self.tabs.setTabEnabled(2, path.is_file())
        if path.is_file():
            self.viewer.load_structure(path, row["phase_composition"])
