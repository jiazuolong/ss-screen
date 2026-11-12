"""Stage 05 collection from raw VASP output or prepared CSV results."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path

import click
import pandas as pd
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class GapCollectPage(QWidget):
    """Keep task association internal while the user chooses a folder or CSV."""

    run_requested = Signal(list, str)
    pair_requested = Signal()

    def __init__(
        self,
        presentation,
        command,
        project_provider: Callable,
        export_provider: Callable,
        csv_task_provider: Callable | None = None,
    ):
        super().__init__()
        self.presentation, self.command = presentation, command
        self.project_provider, self.export_provider = project_provider, export_provider
        self.csv_task_provider = csv_task_provider or (lambda: [])
        self.editors = []
        self._registered_sources: list[str] = []
        self._output_name, self._report_override = "results_returned.csv", ""
        root = QVBoxLayout(self)
        title = QLabel("收集 / 导入带隙结果")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        root.addWidget(
            self._label(
                "选择原始计算文件或整理好的CSV，自动收集、校验并生成可供06端元配对使用的结果。"
            )
        )
        columns = QHBoxLayout()
        input_box, output_box = QGroupBox("输入栏 / Inputs"), QGroupBox("输出栏 / Outputs")
        left, right = QVBoxLayout(input_box), QVBoxLayout(output_box)
        form = QFormLayout()
        self.input_mode = QComboBox()
        self.input_mode.addItem("VASP 原始计算文件", "vasp")
        self.input_mode.addItem("整理好的 CSV 文件", "csv")
        self.input_mode.addItem("从历史结果库匹配", "library")
        form.addRow("输入类型", self.input_mode)
        left.addLayout(form)
        self.vasp_panel = QWidget()
        vasp_layout = QVBoxLayout(self.vasp_panel)
        vasp_layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        self.results_edit = self._directory_row(form, "VASP结果文件夹")
        vasp_layout.addLayout(form)
        vasp_layout.addWidget(
            self._label(
                "VASP结果/  ← 选择这个总目录\n    gap-任务ID1/\n        vasprun.xml\n    gap-任务ID2/\n        vasprun.xml"
            )
        )
        vasp_layout.addWidget(
            self._label(
                "每个任务目录直接放最终的 vasprun.xml 或 vasprun.xml.gz。任务ID保持与本工程导出批次一致。"
            )
        )
        left.addWidget(self.vasp_panel)
        self.csv_panel = QWidget()
        csv_layout = QVBoxLayout(self.csv_panel)
        csv_layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        self.csv_edit = self._directory_row(form, "带隙结果CSV", csv_file=True)
        self.method_box = QComboBox()
        self.method_box.addItem("自动匹配唯一记录", "")
        self.method_label = QLabel("历史计算方法")
        form.addRow(self.method_label, self.method_box)
        csv_layout.addLayout(form)
        csv_layout.addWidget(
            self._label(
                "选择已整理的带隙结果表，例如 results_import.csv 或 results_normalized.csv。\n"
                "请保留本软件结果模板中的任务ID、材料ID、化学式、方法、结构哈希、带隙（eV）及计算状态；导入时自动校验。"
            )
        )
        left.addWidget(self.csv_panel)
        self.source_label = self._label("")
        left.addWidget(self.source_label)
        left.addStretch()
        form = QFormLayout()
        self.output_dir_edit = self._directory_row(form, "输出文件夹")
        right.addLayout(form)
        self.output_label, self.status_label = self._label(""), self._label("")
        right.addWidget(self.output_label)
        right.addWidget(self.status_label)
        right.addStretch()
        columns.addWidget(input_box, 1)
        columns.addWidget(output_box, 1)
        root.addLayout(columns)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.pair_button = QPushButton("进入06端元配对")
        self.pair_button.clicked.connect(self.open_pairing)
        self.run_button = QPushButton("收集并校验结果")
        self.run_button.setObjectName("primaryButton")
        self.run_button.clicked.connect(self.emit_run)
        buttons.addWidget(self.pair_button)
        buttons.addWidget(self.run_button)
        root.addLayout(buttons)
        self.mode_note = self._label("")
        root.addWidget(self.mode_note)
        root.addStretch()
        self.results_edit.textChanged.connect(self.refresh_preview)
        self.csv_edit.textChanged.connect(self._load_methods)
        self.input_mode.currentIndexChanged.connect(self._load_methods)
        self.method_box.currentIndexChanged.connect(self.refresh_preview)
        self.csv_edit.textChanged.connect(self.refresh_preview)
        self.input_mode.currentIndexChanged.connect(self.refresh_preview)
        self.output_dir_edit.textChanged.connect(self._output_changed)
        self.reset()

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setMinimumWidth(0)
        label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        return label

    def _resolve(self, value: str) -> Path:
        if os.name == "nt" and value.startswith("/mnt/") and len(value) > 7 and value[6] == "/":
            value = value[5].upper() + ":/" + value[7:]
        path = Path(value).expanduser()
        return path if path.is_absolute() else Path(self.project_provider()) / path

    def _directory_row(self, form: QFormLayout, label: str, *, csv_file: bool = False) -> QLineEdit:
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        edit, button = QLineEdit(), QPushButton("…")
        button.setMaximumWidth(34)

        def browse():
            if csv_file:
                value, _ = QFileDialog.getOpenFileName(
                    self, label, str(self._resolve(edit.text())), "CSV文件 (*.csv)"
                )
            else:
                value = QFileDialog.getExistingDirectory(
                    self, label, str(self._resolve(edit.text()))
                )
            if value:
                try:
                    value = Path(value).relative_to(self.project_provider()).as_posix()
                except ValueError:
                    pass
                edit.setText(value)

        button.clicked.connect(browse)
        row.addWidget(edit, 1)
        row.addWidget(button)
        form.addRow(label, host)
        return edit

    def reset(self) -> None:
        self._registered_sources = []
        self._output_name, self._report_override = "results_returned.csv", ""
        self.results_edit.clear()
        self.csv_edit.clear()
        self.csv_edit.setPlaceholderText("选择已整理的带隙结果CSV")
        self.input_mode.setCurrentIndex(0)
        self.results_edit.setPlaceholderText("选择含 gap-任务ID 子文件夹的总目录")
        self.output_dir_edit.setText(str(Path(self.export_provider()).parent))
        self.refresh_preview()

    def is_library(self) -> bool:
        return self.input_mode.currentData() == "library"

    def _load_methods(self) -> None:
        if not self.is_library():
            return
        previous = self.method_box.currentData()
        try:
            methods = pd.read_csv(self._resolve(self.csv_edit.text()), usecols=["method"],
                                  dtype=str, keep_default_na=False)["method"].unique()
        except (OSError, ValueError):
            methods = []
        self.method_box.blockSignals(True)
        self.method_box.clear()
        self.method_box.addItem("自动匹配唯一记录", "")
        for method in sorted(filter(None, methods)):
            self.method_box.addItem(method, method)
        self.method_box.setCurrentIndex(max(0, self.method_box.findData(previous)))
        self.method_box.blockSignals(False)

    def task_sources(self) -> list[str]:
        if self.is_library():
            return [self.export_provider()] if self.export_provider() else []
        extra = self.csv_task_provider() if self.is_csv() else []
        candidates = list(
            dict.fromkeys([self.export_provider(), *self._registered_sources, *extra])
        )
        candidates = [value for value in candidates if value]
        existing = [value for value in candidates if self._resolve(value).is_file()]
        return existing or candidates

    def is_csv(self) -> bool:
        return self.input_mode.currentData() in {"csv", "library"}

    def input_edit(self) -> QLineEdit:
        return self.csv_edit if self.is_csv() else self.results_edit

    def _output_changed(self) -> None:
        self._report_override = ""
        self.refresh_preview()

    def output_paths(self) -> tuple[str, str]:
        root = Path(self.output_dir_edit.text().strip())
        return str(root / self._output_name), self._report_override or str(
            root / "collection-report.json"
        )

    def argv(self) -> list[str]:
        output, report = self.output_paths()
        args = [
            "gap-collect-vasp",
            "--results-csv" if self.is_csv() else "--results-dir",
            self.input_edit().text().strip(),
            "--output",
            output,
            "--report",
            report,
        ]
        if self.is_library():
            args.append("--historical-library")
            if self.method_box.currentData():
                args.extend(["--library-method", self.method_box.currentData()])
        for source in self.task_sources():
            args.extend(["--task-source", source])
        return args

    def apply_values(self, values: dict) -> None:
        if "results_dir" in values:
            self.results_edit.setText(str(values["results_dir"] or ""))
        if "results_csv" in values:
            self.csv_edit.setText(str(values["results_csv"] or ""))
        if values.get("results_csv") is not None:
            self.input_mode.setCurrentIndex(2 if values.get("historical_library") else 1)
            self.method_box.setCurrentIndex(max(0, self.method_box.findData(values.get("library_method", ""))))
        elif values.get("results_dir") is not None:
            self.input_mode.setCurrentIndex(0)
        if values.get("output_path"):
            output = Path(values["output_path"])
            self._output_name = output.name
            self.output_dir_edit.setText(str(output.parent))
        if "report_path" in values:
            self._report_override = str(values["report_path"] or "")
        if "task_sources" in values or "tasks_path" in values:
            self._registered_sources = [
                str(value) for value in values.get("task_sources", ()) if value
            ]
            if values.get("tasks_path"):
                self._registered_sources.append(str(values["tasks_path"]))
        self.refresh_preview()

    def restore_argv(self, argv: list[str]) -> None:
        command = copy.copy(self.command)
        command.params = [copy.copy(param) for param in self.command.params]
        for param in command.params:
            if isinstance(param.type, click.Path):
                param.type = copy.copy(param.type)
                param.type.exists = False
                param.type.resolve_path = False
        args = argv[1:] if argv[:1] == ["gap-collect-vasp"] else argv
        with command.make_context("gap-collect-vasp", list(args)) as context:
            values = context.params
            for option, name in (
                ("--tasks", "tasks_path"),
                ("--results-dir", "results_dir"),
                ("--results-csv", "results_csv"),
            ):
                if option in args and args[args.index(option) + 1] == "":
                    values[name] = ""
            if values.get("report_path") is None:
                output = Path(values["output_path"])
                values["report_path"] = output.with_name(f"{output.stem}.collection-report.json")
            self.apply_values(values)

    def form_state(self) -> dict:
        return {
            "input_mode": self.input_mode.currentData(),
            "library_method": self.method_box.currentData(),
            "results_dir": self.results_edit.text(),
            "results_csv": self.csv_edit.text(),
        }

    def restore_form_state(self, state: dict) -> None:
        if "results_dir" in state:
            self.results_edit.setText(str(state["results_dir"]))
        if "results_csv" in state:
            self.csv_edit.setText(str(state["results_csv"]))
        if state.get("input_mode") in {"vasp", "csv", "library"}:
            self.input_mode.setCurrentIndex(self.input_mode.findData(state["input_mode"]))
            self.method_box.setCurrentIndex(max(0, self.method_box.findData(state.get("library_method", ""))))
        self.refresh_preview()

    def missing_required(self) -> list[str]:
        return [
            name
            for name, edit in (
                (
                    "带隙结果CSV" if self.is_csv() else "VASP结果文件夹",
                    self.input_edit(),
                ),
                ("输出文件夹", self.output_dir_edit),
            )
            if not edit.text().strip()
        ]

    def _collection_report(self) -> dict:
        output, report = self.output_paths()
        try:
            data = json.loads(self._resolve(report).read_text(encoding="utf-8"))
            expected = {"library": "project-library", "csv": "project-csv", "vasp": "project-folder"}
            if data.get("mode") != expected[self.input_mode.currentData()]:
                return {}
            if self.is_library() and data.get("library_method") != self.method_box.currentData():
                return {}
            if (
                self._resolve(data["results_csv" if self.is_csv() else "results_dir"]).resolve()
                != self._resolve(self.input_edit().text()).resolve()
            ):
                return {}
            if self._resolve(data["output"]).resolve() != self._resolve(output).resolve():
                return {}
            if not {self._resolve(p).resolve() for p in data["task_sources"]} <= {
                self._resolve(p).resolve() for p in self.task_sources()
            }:
                return {}
            if (
                hashlib.sha256(self._resolve(data["selected_source"]).read_bytes()).hexdigest()
                != data["source_sha256"]
            ):
                return {}
            for path, key in (
                (output, "output_sha256"),
                (data["tasks_path"], "tasks_sha256"),
            ):
                if hashlib.sha256(self._resolve(path).read_bytes()).hexdigest() != data[key]:
                    return {}
            if (
                self.is_csv()
                and hashlib.sha256(self._resolve(self.csv_edit.text()).read_bytes()).hexdigest()
                != data["input_sha256"]
            ):
                return {}
            return data
        except (OSError, ValueError, KeyError, TypeError):
            return {}

    def refresh_preview(self) -> None:
        csv_mode = self.is_csv()
        self.method_label.setVisible(self.is_library())
        self.method_box.setVisible(self.is_library())
        self.vasp_panel.setVisible(not csv_mode)
        self.csv_panel.setVisible(csv_mode)
        self.run_button.setText("导入并校验CSV" if csv_mode else "收集并校验结果")
        self.mode_note.setText(
            "材料对应关系由工程自动关联，无需另选任务清单。CSV保留已有计算结果和状态，不重新解析VASP文件。"
            if csv_mode
            else "材料对应关系由当前工程自动关联，计算条件从VASP文件读取，无需另选任务清单。"
        )
        if self.is_library():
            self.run_button.setText("匹配历史带隙")
            self.mode_note.setText("选择共享 results.csv。按材料、结构和计算方法核验；多条记录同时匹配时可选择计算方法。")
        connected = any(self._resolve(value).is_file() for value in self.task_sources())
        self.source_label.setText(
            "已自动关联本工程的任务记录。"
            if connected
            else "本工程尚无导出批次，请先完成“导出带隙计算压缩包”。"
        )
        output, report = self.output_paths()
        self.output_label.setText(
            f"自动生成：\n已校验带隙结果表：{output}\n收集与校验报告：{report}\n材料对应关系和计算来源会同时保存；结果可直接用于06。"
        )
        data = self._collection_report()
        if data:
            counts = data["status_counts"]
            self.status_label.setText(
                (
                    "已收集并通过记录校验："
                    if self._validated(data)
                    else "已有旧版收集结果，需重新收集并校验："
                )
                + "，".join(
                    f"{label} {counts.get(key, 0)}"
                    for key, label in (
                        ("success", "成功"),
                        ("not_converged", "未收敛"),
                        ("failed", "失败"),
                        ("missing", "缺失"),
                        ("skipped", "跳过"),
                        ("pending", "待计算"),
                        ("running", "计算中"),
                        ("cancelled", "已取消"),
                    )
                    if key in {"success", "not_converged", "failed", "missing"} or counts.get(key)
                )
            )
            if self.is_library():
                review = sum(row["match"] in {"unverified", "ambiguous"} for row in data["matches"])
                self.status_label.setText(self.status_label.text() + f"（缺失项中待核验 {review}）")
        else:
            self.status_label.setText("当前输入尚无对应收集结果")
        ready = self._validated(data) and data.get("status_counts", {}).get("success", 0) > 0
        self.pair_button.setEnabled(ready)
        if self._validated(data) and not ready:
            self.status_label.setText(self.status_label.text() + "。暂无成功带隙，不能进行06配对。")

    @staticmethod
    def _validated(data: dict) -> bool:
        validation = data.get("validation", {})
        return validation.get("rejected_count") == 0 and validation.get("accepted_count", 0) > 0

    def validated_result(self) -> str | None:
        """Recheck source/output identities before handing off a successful batch."""
        data = self._collection_report()
        if self._validated(data) and data.get("status_counts", {}).get("success", 0) > 0:
            return self.output_paths()[0]
        return None

    def emit_run(self) -> None:
        try:
            missing = self.missing_required()
            if missing:
                raise ValueError("请填写：" + "、".join(missing))
            root = self._resolve(self.input_edit().text().strip())
            if self.is_csv():
                if not root.is_file() or root.suffix.lower() != ".csv":
                    raise ValueError("请选择整理好的带隙结果CSV文件。")
            elif not root.is_dir() or not any(
                path.is_dir() and path.name.startswith("gap-") for path in root.iterdir()
            ):
                raise ValueError("请选择包含 gap-任务ID 子文件夹的VASP结果总目录。")
            if not any(self._resolve(value).is_file() for value in self.task_sources()):
                raise ValueError("当前工程尚未关联导出批次，请先完成“导出带隙计算压缩包”。")
            output, report = map(self._resolve, self.output_paths())
            destinations = (
                output,
                report,
                output.with_name(f"{output.stem}.tasks.csv"),
                output.with_name(f"{output.stem}.provenance.json"),
            )
            if len({path.resolve() for path in destinations}) != len(destinations) or any(
                path.exists() for path in destinations
            ):
                raise ValueError("输出位置已有文件或路径重叠，请选择新的输出文件夹。")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "检查输入输出", str(exc))
            return
        self.run_requested.emit(self.argv(), self.presentation.title)

    def open_pairing(self) -> None:
        if self.validated_result():
            self.pair_requested.emit()
        else:
            self.refresh_preview()
