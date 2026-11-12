"""Stage 06: follow upstream results and hand verified pairs to Stage 07."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
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

from ..material_assessment import PHOTON_ENERGY_EV_UM
from .metadata import CommandPresentation


class WavelengthPairPage(QWidget):
    run_requested = Signal(list, str)
    sqs_requested = Signal()

    def __init__(
        self,
        presentation: CommandPresentation,
        command: click.Command,
        project_provider: Callable[[], Path],
        input_provider: Callable[[], tuple[str, str, bool]],
    ) -> None:
        super().__init__()
        self.presentation, self.command = presentation, command
        self.project_provider, self.input_provider = project_provider, input_provider
        self.editors = []
        root = QVBoxLayout(self)
        title = QLabel("按目标波长筛选端元对")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        root.addWidget(
            self._label("使用04分组和05已校验带隙，筛选带隙范围覆盖目标光子能量的端元组合。")
        )
        columns = QHBoxLayout()
        inputs, outputs = QGroupBox("输入栏 / Inputs"), QGroupBox("输出栏 / Outputs")
        left, right = QVBoxLayout(inputs), QVBoxLayout(outputs)
        form = QFormLayout()
        self.groups_edit, self.gaps_edit = QLineEdit(), QLineEdit()
        for label, edit in (
            ("04 材料分组（自动）", self.groups_edit),
            ("05 带隙结果（自动）", self.gaps_edit),
        ):
            edit.setReadOnly(True)
            form.addRow(label, edit)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        left.addLayout(form)
        self.source_label = self._label("")
        left.addWidget(self.source_label)
        refresh = QPushButton("刷新上游结果")
        refresh.clicked.connect(self.refresh_preview)
        left.addWidget(refresh)
        form = QFormLayout()
        self.wavelength_edit, self.min_gap_edit, self.max_gap_edit = (
            QLineEdit(),
            QLineEdit(),
            QLineEdit(),
        )
        self.wavelength_edit.setPlaceholderText("必填，例如 10")
        self.min_gap_edit.setPlaceholderText("可选，留空不限制")
        self.max_gap_edit.setPlaceholderText("可选，留空不限制")
        for label, edit in (
            ("目标波长（μm）", self.wavelength_edit),
            ("带隙严格下限（eV）", self.min_gap_edit),
            ("带隙严格上限（eV）", self.max_gap_edit),
        ):
            form.addRow(label, edit)
        left.addLayout(form)
        self.energy_label = self._label("")
        left.addWidget(self.energy_label)
        left.addWidget(
            self._label(
                "上下限作用于两个端元，等于边界的材料不保留。带隙方法随05结果继承，逐端元保留来源；同一材料有多条成功结果时需先整理05输入。"
            )
        )
        left.addStretch()
        form = QFormLayout()
        self.output_edit = self._file_row(form, "端元对 CSV", "CSV (*.csv)")
        self.summary_edit = self._file_row(form, "筛选报告 JSON", "JSON (*.json)")
        right.addLayout(form)
        right.addWidget(self._label("CSV供07生成SQS使用；报告记录筛选条件、覆盖情况和配对数量。"))
        self.status_label = self._label("")
        right.addWidget(self.status_label)
        right.addStretch()
        self.run_button = QPushButton("筛选端元对")
        self.run_button.setObjectName("primaryButton")
        self.run_button.clicked.connect(self.emit_run)
        self.sqs_button = QPushButton("进入 07 SQS合金")
        self.sqs_button.clicked.connect(self.open_sqs)
        right.addWidget(self.run_button)
        right.addWidget(self.sqs_button)
        right.addWidget(
            self._label("筛选完成且有可用端元对后，可带入07；进入下一步后核对合金参数再运行。")
        )
        columns.addWidget(inputs, 1)
        columns.addWidget(outputs, 1)
        root.addLayout(columns)
        root.addStretch()
        for edit in (
            self.wavelength_edit,
            self.min_gap_edit,
            self.max_gap_edit,
            self.output_edit,
            self.summary_edit,
        ):
            edit.textChanged.connect(self.refresh_preview)
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

    def _file_row(self, form: QFormLayout, label: str, file_filter: str) -> QLineEdit:
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        host, edit, button = QWidget(), QLineEdit(), QPushButton("…")
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        button.setMaximumWidth(34)

        def browse() -> None:
            value, _ = QFileDialog.getSaveFileName(
                self, label, str(self._resolve(edit.text())), file_filter
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
        self.wavelength_edit.clear()
        self.min_gap_edit.clear()
        self.max_gap_edit.clear()
        self.output_edit.setText("06_pair/final_pairs.csv")
        self.summary_edit.setText("06_pair/summary.json")
        self.refresh_preview()

    def apply_values(self, values: dict[str, Any]) -> None:
        # Upstream paths and methods always follow the current project, even for old saves.
        for key, edit in (
            ("wavelength_um", self.wavelength_edit),
            ("min_gap_exclusive", self.min_gap_edit),
            ("max_gap_exclusive", self.max_gap_edit),
            ("output", self.output_edit),
            ("summary", self.summary_edit),
        ):
            if key in values:
                value = values[key]
                if key == "wavelength_um" and value is not None:
                    try:
                        value = str(float(value))
                    except ValueError:
                        pass
                edit.setText("" if value is None else str(value))
        self.refresh_preview()

    def restore_argv(self, argv: list[str]) -> None:
        # Read option strings without requiring files or a wavelength in unfinished forms.
        self.reset()
        values = {}
        for option, name in (
            ("--target-wavelength-um", "wavelength_um"),
            ("--min-gap-exclusive", "min_gap_exclusive"),
            ("--max-gap-exclusive", "max_gap_exclusive"),
            ("--output", "output"),
            ("--summary", "summary"),
        ):
            if option in argv and argv.index(option) + 1 < len(argv):
                values[name] = argv[argv.index(option) + 1]
        self.apply_values(values)

    def argv(self) -> list[str]:
        groups, gaps, _ready = self.input_provider()
        args = [
            "pair-wavelength",
            "--groups",
            groups,
            "--gap-results",
            gaps,
            "--allow-mixed-methods",
        ]
        for option, edit in (
            ("--target-wavelength-um", self.wavelength_edit),
            ("--min-gap-exclusive", self.min_gap_edit),
            ("--max-gap-exclusive", self.max_gap_edit),
            ("--output", self.output_edit),
            ("--summary", self.summary_edit),
        ):
            if edit.text().strip():
                args.extend([option, edit.text().strip()])
        return args

    def _parameters(self) -> dict[str, float | None]:
        wave = float(self.wavelength_edit.text())
        lower = float(self.min_gap_edit.text()) if self.min_gap_edit.text().strip() else None
        upper = float(self.max_gap_edit.text()) if self.max_gap_edit.text().strip() else None
        if not math.isfinite(wave) or wave <= 0:
            raise ValueError("目标波长必须是大于0的有限数值。")
        if any(
            value is not None and (not math.isfinite(value) or value < 0)
            for value in (lower, upper)
        ):
            raise ValueError("带隙上下限必须为非负有限数值。")
        if lower is not None and upper is not None and lower >= upper:
            raise ValueError("带隙下限必须小于上限。")
        return {
            "target_wavelength_um": wave,
            "min_gap_exclusive_eV": lower,
            "max_gap_exclusive_eV": upper,
        }

    def _result_report(self) -> dict[str, Any]:
        try:
            groups, gaps, ready = self.input_provider()
            if not ready:
                return {}
            data = json.loads(self._resolve(self.summary_edit.text()).read_text(encoding="utf-8"))
            if any(data.get(key) != value for key, value in self._parameters().items()):
                return {}
            if data.get("selected_method") != "mixed_sources" or not data.get(
                "allow_mixed_methods"
            ):
                return {}
            expected = {
                "groups": [hashlib.sha256(self._resolve(groups).read_bytes()).hexdigest()],
                "gaps": [hashlib.sha256(self._resolve(gaps).read_bytes()).hexdigest()],
            }
            if data.get("input_sha256") != expected:
                return {}
            output = self._resolve(self.output_edit.text())
            if hashlib.sha256(output.read_bytes()).hexdigest() != data.get("output_sha256"):
                return {}
            with output.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if not {"mp_id_a", "mp_id_b"} <= set(reader.fieldnames or []):
                    return {}
                count = sum(1 for _ in reader)
            return data if count == data.get("pair_count") else {}
        except (OSError, ValueError, TypeError):
            return {}

    def validated_result(self) -> str | None:
        data = self._result_report()
        return self.output_edit.text().strip() if data.get("pair_count", 0) > 0 else None

    def refresh_preview(self) -> None:
        groups, gaps, ready = self.input_provider()
        self.groups_edit.setText(groups)
        self.gaps_edit.setText(gaps)
        for edit in (self.groups_edit, self.gaps_edit):
            edit.setToolTip(edit.text())
            edit.setCursorPosition(0)
        self.source_label.setText(
            "已自动关联04分组和05校验通过的带隙结果。"
            if ready
            else "等待上游结果：请完成04分组及05收集/导入校验，然后刷新。"
        )
        try:
            parameters = self._parameters()
            self.energy_label.setText(
                f"目标光子能量：{PHOTON_ENERGY_EV_UM / parameters['target_wavelength_um']:.6f} eV；端元带隙范围需覆盖此值。"
            )
        except ValueError:
            self.energy_label.setText("请填写有效的目标波长和可选带隙范围。")
        data = self._result_report()
        count = data.get("pair_count", 0)
        self.sqs_button.setEnabled(count > 0)
        if data:
            self.status_label.setText(
                f"筛选完成：{count} 对端元。"
                + ("可进入07生成SQS。" if count else "没有符合条件的端元对，请调整条件。")
            )
        elif self._resolve(self.output_edit.text()).is_file():
            self.status_label.setText(
                "该位置已有结果；请重新筛选以确认当前输入、条件和结果一致，再进入07。"
            )
        else:
            self.status_label.setText("尚未生成本次筛选结果。")

    def emit_run(self) -> None:
        try:
            self._parameters()
            groups, gaps, ready = self.input_provider()
            if not ready:
                raise ValueError("请先完成04分组和05收集/导入带隙结果。")
            if not self.output_edit.text().strip() or not self.summary_edit.text().strip():
                raise ValueError("请填写端元对CSV和筛选报告路径。")
            destinations = {
                self._resolve(edit.text()).resolve()
                for edit in (self.output_edit, self.summary_edit)
            }
            if len(destinations) != 2 or destinations & {
                self._resolve(value).resolve() for value in (groups, gaps)
            }:
                raise ValueError("输出文件须互不相同，且不能覆盖输入文件。")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "检查筛选参数", str(exc))
            return
        self.run_requested.emit(self.argv(), self.presentation.title)

    def open_sqs(self) -> None:
        if self.validated_result():
            self.sqs_requested.emit()
        else:
            self.refresh_preview()
