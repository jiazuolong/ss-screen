"""Result visualization widgets for the desktop workbench."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .phase_page import PhaseResultsPage as PhaseResultsPage
from .workflow_project import imported_artifact


def _csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class MatterVizView(QWebEngineView):
    """Offline MatterViz host that accepts local structure files from Python."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(360, 320)
        self.settings().setAttribute(
            QWebEngineSettings.WebAttribute.WebGLEnabled, True
        )
        self.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )
        self._pending: tuple[str, str, str] | None = None
        self._ready = False
        self.loadFinished.connect(self._loaded)
        index = Path(__file__).with_name("matterviz_dist") / "index.html"
        if index.is_file():
            self.load(QUrl.fromLocalFile(str(index.resolve())))
        else:
            self.setHtml("<h3>MatterViz resources are not built.</h3>")

    def _loaded(self, ok: bool) -> None:
        """Wait for the JS bridge after HTML load; do not override MatterViz CSS.

        loadFinished only means index.html loaded, not that Svelte's
        ssScreenLoadStructure global is already registered.
        """
        self._ready = ok
        if not ok:
            print("[SS-Screen MatterViz] index.html load failed", flush=True)
            return
        if self._pending is not None:
            payload = self._pending
            self._pending = None
            self._send(*payload)

    def load_structure(self, path: Path, label: str | None = None) -> None:
        if not path.is_file():
            print(f"[SS-Screen MatterViz] missing file: {path}", flush=True)
            return
        content = path.read_text(encoding="utf-8", errors="replace")
        payload = (content, path.name, label or path.stem)
        if self._ready:
            self._send(*payload)
        else:
            self._pending = payload

    def _send(self, content: str, filename: str, label: str) -> None:
        arguments = ", ".join(
            json.dumps(value, ensure_ascii=False) for value in (content, filename, label)
        )
        # The retry runs *inside the webpage* and does not depend on Qt's
        # runJavaScript return-value callback, which can be unreliable on WSL.
        script = f"""(() => {{
          const values = [{arguments}];
          let retries = 0;
          const deliver = () => {{
            if (typeof window.ssScreenLoadStructure !== 'function') {{
              if (retries++ < 100) {{
                setTimeout(deliver, 100);
              }} else {{
                console.error('SSSCREEN_BRIDGE_NOT_READY after 10 seconds');
              }}
              return;
            }}
            Promise.resolve(window.ssScreenLoadStructure(...values))
              .then(() => console.info('SSSCREEN_JSON_LOADED ' + values[1]))
              .catch(err => console.error('SSSCREEN_JSON_LOAD_FAILED', err));
          }};
          deliver();
        }})()"""
        self.page().runJavaScript(script)


class StructureResultsPage(QWidget):
    """Browse relaxed and generated structures with the embedded MatterViz viewer."""

    def __init__(self, project_provider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_provider = project_provider
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        header = QHBoxLayout()
        title = QLabel("晶体结构可视化")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        refresh = QPushButton("刷新结构")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        layout.addLayout(header)

        self.selector = QComboBox()
        # Debounce rapid combo-box choices; only the last one is rendered.
        self._pending_selection_index = -1
        self._last_structure_signature = None
        self._selection_timer = QTimer(self)
        self._selection_timer.setSingleShot(True)
        self._selection_timer.setInterval(160)
        self._selection_timer.timeout.connect(self._apply_pending_selection)
        self.selector.activated.connect(self._queue_selection_change)
        layout.addWidget(self.selector)
        self.viewer = MatterVizView()
        self.viewer.setMinimumHeight(460)
        layout.addWidget(self.viewer, 1)
        self.refresh()

    def _root(self) -> Path:
        return Path(self.project_provider()).expanduser().resolve()

    def refresh(self) -> None:
        self._selection_timer.stop()
        self._pending_selection_index = -1
        current = self.selector.currentData()

        self.selector.blockSignals(True)
        self.selector.clear()

        patterns = (
            "07_sqs/structures/**/*.json",
            "08_relax/structures/**/*.json",
            "10_phonon/inputs/**/structures/reference.json",
            "11_phase/relaxation/structures/*.json",
        )

        seen: set[Path] = set()

        # External runs retain their structures in their original directories.
        index_path = imported_artifact(self._root(), "08_relax/structure_index.csv")
        for row in _csv_rows(index_path):
            path = Path(row["path"])
            if path.is_file() and path.resolve() not in seen:
                seen.add(path.resolve())
                self.selector.addItem(row.get("label", path.name), str(path))

        for pattern in patterns:
            for path in sorted(self._root().glob(pattern)):
                resolved = path.resolve()

                if resolved in seen:
                    continue

                seen.add(resolved)

                label = path.relative_to(
                    self._root()
                ).as_posix()

                self.selector.addItem(
                    label,
                    str(resolved),
                )

        target_index = -1

        if self.selector.count() > 0:
            target_index = 0

            if current:
                found = self.selector.findData(current)
                if found >= 0:
                    target_index = found

            self.selector.setCurrentIndex(target_index)

        self.selector.blockSignals(False)

        # 初始化时只加载一次
        if target_index >= 0:
            self._selection_changed(target_index)

    def _queue_selection_change(self, index: int) -> None:
        self._pending_selection_index = index
        self._selection_timer.start()

    def _apply_pending_selection(self) -> None:
        index = self._pending_selection_index
        self._pending_selection_index = -1
        if index >= 0:
            self._selection_changed(index)

    def _selection_changed(self, index: int) -> None:
        if index < 0:
            return

        data = self.selector.itemData(index)

        if not data:
            return

        path = Path(str(data))
        print("=" * 60, flush=True)
        print("当前工程根目录:", self._root(), flush=True)
        print("当前选择的结构:", self.selector.itemText(index), flush=True)
        print("实际 JSON 路径:", path.resolve(), flush=True)
        print("文件是否存在:", path.is_file(), flush=True)
        print("=" * 60, flush=True)

        if not path.is_file():
            return

        # Re-selecting an unchanged file should not rebuild its 3D scene.
        file_stat = path.stat()
        signature = (str(path.resolve()), file_stat.st_mtime_ns, file_stat.st_size)
        if signature == self._last_structure_signature:
            return
        self._last_structure_signature = signature

        self.viewer.load_structure(
            path,
            self.selector.itemText(index),
        )


class ScaledImage(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source = QPixmap()
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(360, 280)
        self.setText("尚无图像")

    def set_image(self, path: Path) -> None:
        self._source = QPixmap(str(path)) if path.is_file() else QPixmap()
        self._rescale()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self) -> None:
        if self._source.isNull():
            self.setPixmap(QPixmap())
            self.setText("尚无声子频带/DOS图")
            return
        self.setText("")
        self.setPixmap(
            self._source.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )


class PhononResultsPage(QWidget):
    """Stage 10 summary, generated band/DOS image and linked structure viewer."""

    def __init__(self, project_provider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_provider = project_provider
        self.rows: list[dict[str, str]] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        header = QHBoxLayout()
        title = QLabel("声子谱结果")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        refresh = QPushButton("刷新结果")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        overview = QWidget()
        overview_layout = QVBoxLayout(overview)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["结构", "角色", "状态", "动力学", "最低频率(THz)", "虚频数", "力覆盖率"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.setMinimumWidth(570)
        header_view = self.table.horizontalHeader()
        for column in range(4):
            header_view.setSectionResizeMode(column, QHeaderView.Stretch)
        for column in range(4, 7):
            header_view.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        splitter.addWidget(self.table)

        self.image = ScaledImage()
        splitter.addWidget(self.image)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        overview_layout.addWidget(splitter, 1)
        self.tabs.addTab(overview, "频带、DOS 与结果表")

        self.viewer = MatterVizView()
        self.viewer.setMinimumHeight(520)
        self.tabs.addTab(self.viewer, "对应晶体（MatterViz）")
        root.addWidget(self.tabs, 1)
        self.refresh()

    def _root(self) -> Path:
        return Path(self.project_provider()).expanduser().resolve()

    def refresh(self) -> None:
        self.rows = _csv_rows(imported_artifact(self._root(), "10_phonon/phonon_summary.csv"))
        self.table.setRowCount(0)
        keys = (
            "structure_id",
            "structure_role",
            "status",
            "dynamical_status",
            "minimum_mesh_frequency_THz",
            "significant_imaginary_mode_count",
            "force_coverage",
        )
        for row in self.rows:
            position = self.table.rowCount()
            self.table.insertRow(position)
            for column, key in enumerate(keys):
                self.table.setItem(position, column, QTableWidgetItem(row.get(key, "")))
        if self.rows:
            self.table.selectRow(0)

    def _selection_changed(self) -> None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return
        row = self.rows[indexes[0].row()]
        phonon_id = row.get("phonon_id", "")
        result_dir = self._root() / "10_phonon" / "results" / phonon_id
        plot = Path(row["plot_path"]) if row.get("plot_path") else result_dir / "phonon_band_dos.png"
        self.image.set_image(plot)
        structure = (
            self._root() / "10_phonon" / "inputs" / phonon_id / "structures" / "reference.json"
        )
        if row.get("reference_structure_path"):
            structure = Path(row["reference_structure_path"])
        self.viewer.load_structure(structure, row.get("structure_id") or phonon_id)
