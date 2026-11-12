"""Stage 07 input/output panels with automatic upstream inputs."""

from __future__ import annotations

import copy
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
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

from .metadata import PATH_PRESETS, CommandPresentation
from .sqs_results import pair_count, resolve_path, sqs_result_status


class SqsPage(QWidget):
    run_requested = Signal(list, str)
    relax_requested = Signal()

    def __init__(
        self,
        presentation: CommandPresentation,
        command: click.Command,
        project_provider: Callable[[], Path],
        input_provider: Callable[[], tuple[str, str, bool]],
        uses_demo_cache: Callable[[], bool] = lambda: False,
    ) -> None:
        super().__init__()
        self.presentation, self.command = presentation, command
        self.project_provider, self.input_provider = project_provider, input_provider
        self.uses_demo_cache = uses_demo_cache
        self.editors = []
        root = QVBoxLayout(self)
        title = QLabel("生成 SQS 合金结构")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        root.addWidget(
            self._label("自动接入06端元对和02结构数据，设置合金生成参数，输出结构后进入08弛豫。")
        )
        columns = QHBoxLayout()
        inputs, outputs = QGroupBox("输入栏 / Inputs"), QGroupBox("输出栏 / Outputs")
        left, right = QVBoxLayout(inputs), QVBoxLayout(outputs)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.pairs_edit, self.dataset_edit = QLineEdit(), QLineEdit()
        for label, edit in (
            ("06 端元对（自动）", self.pairs_edit),
            ("02 结构数据（自动）", self.dataset_edit),
        ):
            edit.setReadOnly(True)
            form.addRow(label, edit)
        left.addLayout(form)
        self.source_label = self._label("")
        left.addWidget(self.source_label)
        refresh = QPushButton("刷新上游结果")
        refresh.clicked.connect(self.refresh_preview)
        left.addWidget(refresh)
        form = QFormLayout()
        self.fractions_edit, self.supercell_edit = QLineEdit(), QLineEdit()
        self.backend_combo = QComboBox()
        self.backend_combo.addItem("随机替换（random）", "random")
        self.backend_combo.addItem("优化 SQS（icet）", "icet")
        self.cutoffs_edit, self.steps_edit, self.seed_edit = QLineEdit(), QLineEdit(), QLineEdit()
        self.fractions_edit.setPlaceholderText("例如 0.5；多个比例用逗号分隔")
        self.supercell_edit.setPlaceholderText("例如 2,2,2")
        self.cutoffs_edit.setPlaceholderText("例如 4.0；多阶截断用逗号分隔")
        self.steps_edit.setPlaceholderText("留空由 icet 自动选择")
        for label, edit in (
            ("端元B比例 x", self.fractions_edit),
            ("超胞倍数 a,b,c", self.supercell_edit),
            ("生成方式", self.backend_combo),
            ("截断半径（Å）", self.cutoffs_edit),
            ("SQS 优化步数", self.steps_edit),
            ("随机种子", self.seed_edit),
        ):
            form.addRow(label, edit)
        left.addLayout(form)
        self.parameter_note = self._label("")
        left.addWidget(self.parameter_note)
        left.addStretch()
        form = QFormLayout()
        self.output_dir_edit = self._path_row(form, "结构输出文件夹", directory=True)
        self.manifest_edit = self._path_row(form, "SQS 清单 JSONL", directory=False)
        right.addLayout(form)
        right.addWidget(
            self._label(
                "输出合金结构、端元结构及SQS清单。清单供08读取，生成参数与来源记录会一并保存。"
            )
        )
        self.status_label = self._label("")
        right.addWidget(self.status_label)
        right.addStretch()
        self.run_button = QPushButton("生成 SQS")
        self.run_button.setObjectName("primaryButton")
        self.run_button.clicked.connect(self.emit_run)
        self.relax_button = QPushButton("进入 08 MACE弛豫")
        self.relax_button.clicked.connect(self.open_relaxation)
        right.addWidget(self.run_button)
        right.addWidget(self.relax_button)
        right.addWidget(self._label("生成成功后带入08；模型、计算设备和弛豫条件在08确认。"))
        columns.addWidget(inputs, 1)
        columns.addWidget(outputs, 1)
        root.addLayout(columns)
        root.addStretch()
        for edit in self._fields().values():
            edit.textChanged.connect(self.refresh_preview)
        self.backend_combo.currentIndexChanged.connect(self.refresh_preview)
        self.reset()

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setMinimumWidth(0)
        label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        return label

    def _resolve(self, value: str) -> Path:
        return resolve_path(self.project_provider(), value)

    def _path_row(self, form: QFormLayout, label: str, *, directory: bool) -> QLineEdit:
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        host, edit, button = QWidget(), QLineEdit(), QPushButton("…")
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        button.setMaximumWidth(34)

        def browse() -> None:
            start = str(self._resolve(edit.text()))
            value = (
                QFileDialog.getExistingDirectory(self, label, start)
                if directory
                else QFileDialog.getSaveFileName(self, label, start, "JSONL (*.jsonl)")[0]
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

    def _fields(self) -> dict[str, QLineEdit]:
        return {
            "target_fractions": self.fractions_edit,
            "supercell": self.supercell_edit,
            "cutoffs": self.cutoffs_edit,
            "sqs_steps": self.steps_edit,
            "seed": self.seed_edit,
            "output_dir": self.output_dir_edit,
            "manifest_path": self.manifest_edit,
        }

    def reset(self) -> None:
        presets = PATH_PRESETS[self.presentation.command_path]
        values = {}
        for option in self.command.params:
            default = option.get_default(click.Context(self.command))
            if default is getattr(click.core, "UNSET", None):
                default = None
            values[option.name] = presets.get(option.opts[0], default)
        self.apply_values(values)

    def apply_values(self, values: dict[str, Any]) -> None:
        # Source paths always follow the current project, including legacy saved forms.
        for key, edit in self._fields().items():
            if key in values:
                value = values[key]
                edit.setText(
                    ",".join(map(str, value))
                    if isinstance(value, (tuple, list))
                    else "" if value is None else str(value)
                )
        if "backend" in values:
            self.backend_combo.setCurrentIndex(
                max(0, self.backend_combo.findData(values["backend"]))
            )
        self.refresh_preview()

    def restore_argv(self, argv: list[str]) -> None:
        self.reset()
        values: dict[str, Any] = {}
        for option in self.command.params:
            found = [
                argv[index + 1] for index, token in enumerate(argv[:-1]) if token in option.opts
            ]
            if found:
                values[option.name] = found if option.multiple else found[-1]
        self.apply_values(values)

    def argv(self) -> list[str]:
        pairs, dataset, _ = self.input_provider()
        argv = [
            "stability",
            "sqs-generate",
            "--pairs",
            pairs,
            "--dataset",
            dataset,
            "--backend",
            self.backend_combo.currentData(),
        ]
        fields = self._fields()
        for option in self.command.params:
            if option.name not in fields:
                continue
            value = fields[option.name].text().strip()
            if value:
                items = (
                    value.replace("，", ",").replace("\n", ",").split(",")
                    if option.multiple
                    else [value]
                )
                for item in items:
                    argv.extend([option.opts[0], item.strip()])
        return argv

    def _parameters(self) -> dict[str, Any]:
        command = copy.copy(self.command)
        command.params = [copy.copy(param) for param in self.command.params]
        for param in command.params:
            if isinstance(param.type, click.Path):
                param.type = copy.copy(param.type)
                param.type.exists = False
                param.type.resolve_path = False
        with command.make_context("sqs-generate", self.argv()[2:]) as context:
            params = context.params
        if any(not math.isfinite(value) for value in params["target_fractions"]):
            raise ValueError("合金比例须为0至1之间的有限数值。")
        if any(not math.isfinite(value) or value <= 0 for value in params["cutoffs"]):
            raise ValueError("截断半径须为大于0的有限数值。")
        if params["sqs_steps"] is not None and params["sqs_steps"] < 1:
            raise ValueError("优化步数须为正整数，或留空。")
        return {
            key: list(params[key]) if isinstance(params[key], tuple) else params[key]
            for key in ("target_fractions", "supercell", "seed", "backend", "cutoffs", "sqs_steps")
        }

    def result_status(self) -> dict[str, Any]:
        try:
            pairs, dataset, ready = self.input_provider()
            if not ready:
                return {"ready": False, "message": "等待当前06端元对与02结构数据。"}
            return sqs_result_status(
                self.project_provider(),
                pairs,
                dataset,
                self.output_dir_edit.text().strip(),
                self.manifest_edit.text().strip(),
                self._parameters(),
            )
        except (click.ClickException, OSError, ValueError) as exc:
            return {"ready": False, "message": str(exc)}

    def validated_result(self) -> str | None:
        return self.manifest_edit.text().strip() if self.result_status().get("ready") else None

    def refresh_preview(self) -> None:
        pairs, dataset, ready = self.input_provider()
        self.pairs_edit.setText(pairs)
        self.dataset_edit.setText(dataset)
        for edit in (self.pairs_edit, self.dataset_edit):
            edit.setToolTip(edit.text())
            edit.setCursorPosition(0)
        count = pair_count(self._resolve(pairs)) if ready else 0
        self.source_label.setText(
            f"已自动关联06的 {count} 对端元及02结构数据。"
            if count
            else "请先完成06端元筛选并保留02结构数据，然后刷新。"
        )
        optimized = self.backend_combo.currentData() == "icet"
        self.cutoffs_edit.setEnabled(optimized)
        self.steps_edit.setEnabled(optimized)
        self.parameter_note.setText(
            "x表示替换位上端元B的比例；实际比例受超胞位点数限制。"
            + (
                "icet通过优化匹配无序合金关联函数。"
                if optimized
                else "随机替换生成初始合金结构，不进行SQS关联函数优化。"
            )
        )
        status = self.result_status()
        prefix = (
            f"已生成 {status['written']} 项，跳过 {status['skipped']} 项。\n"
            if "written" in status
            else ""
        )
        use_cache = self.uses_demo_cache()
        message = "点击“进入 08 MACE弛豫”校验本算例预置的 SQS 结果。" if use_cache else status["message"]
        self.status_label.setText(prefix + message)
        self.relax_button.setEnabled(use_cache or status["ready"])

    def emit_run(self) -> None:
        try:
            self._parameters()
            pairs, dataset, ready = self.input_provider()
            if not ready or not pair_count(self._resolve(pairs)):
                raise ValueError("请先完成06端元筛选并保留02结构数据。")
            output, manifest = self._resolve(self.output_dir_edit.text()), self._resolve(
                self.manifest_edit.text()
            )
            if not self.output_dir_edit.text().strip() or not self.manifest_edit.text().strip():
                raise ValueError("请填写结构输出目录和SQS清单路径。")
            if (
                manifest.exists()
                or manifest.with_suffix(".provenance.json").exists()
                or (output.is_dir() and any(output.iterdir()))
            ):
                raise ValueError("输出位置已有文件，请选择新的结构目录和清单路径。")
            if output.resolve() in {
                self._resolve(pairs).resolve(),
                self._resolve(dataset).resolve(),
                manifest.resolve(),
            }:
                raise ValueError("结构目录与输入文件、清单路径不能重叠。")
        except (click.ClickException, OSError, ValueError) as exc:
            QMessageBox.warning(self, "检查SQS输入与参数", str(exc))
            return
        self.run_requested.emit(self.argv(), self.presentation.title)

    def open_relaxation(self) -> None:
        if self.uses_demo_cache() or self.validated_result():
            self.relax_requested.emit()
        else:
            self.refresh_preview()
