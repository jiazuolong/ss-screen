"""Stage 08: automatic SQS inputs, MACE controls and Stage 09 handoff."""

from __future__ import annotations

import copy
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
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
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .metadata import PATH_PRESETS, CommandPresentation
from .relax_results import (
    manifest_rows,
    relaxation_status,
    requires_endpoint_dataset,
    structure_path,
)
from .sqs_results import resolve_path


class RelaxPage(QWidget):
    run_requested = Signal(list, str)
    mixing_requested = Signal()

    def __init__(
        self,
        presentation: CommandPresentation,
        command: click.Command,
        project_provider: Callable[[], Path],
        input_provider: Callable[[], tuple[str, str, str, bool]],
        uses_demo_cache: Callable[[], bool] = lambda: False,
    ) -> None:
        super().__init__()
        self.presentation, self.command = presentation, command
        self.project_provider, self.input_provider = project_provider, input_provider
        self.uses_demo_cache = uses_demo_cache
        self.editors = []
        self.external_mode = False
        root = QVBoxLayout(self)
        title = QLabel("MACE 结构弛豫")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        root.addWidget(
            self._label(
                "接入07合金及端元结构，使用同一MACE模型优化结构并计算能量，供09混合焓使用。"
            )
        )
        columns = QHBoxLayout()
        inputs, outputs = QGroupBox("输入栏 / Inputs"), QGroupBox("输出栏 / Outputs")
        left, right = QVBoxLayout(inputs), QVBoxLayout(outputs)
        form = QFormLayout()
        self.manifest_edit, self.dataset_edit = QLineEdit(), QLineEdit()
        for label, edit in (
            ("07 SQS清单（自动）", self.manifest_edit),
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
        self.model_edit = self._path_row(form, "MACE 模型文件", mode="model")
        self.model_name_edit = QLineEdit()
        self.model_name_edit.setPlaceholderText("可选，用于标识结果来源")
        form.addRow("模型名称", self.model_name_edit)
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        self.device_combo, self.dtype_combo = QComboBox(), QComboBox()
        self.device_combo.setEditable(True)
        self.device_combo.addItems(["cpu", "cuda", "cuda:0"])
        self.dtype_combo.addItems(["float32", "float64"])
        row.addWidget(self.device_combo, 1)
        row.addWidget(QLabel("精度"))
        row.addWidget(self.dtype_combo, 1)
        form.addRow("计算设备", host)
        self.fmax_edit, self.max_steps_edit = QLineEdit(), QLineEdit()
        form.addRow("力收敛阈值（eV/Å）", self.fmax_edit)
        form.addRow("最大弛豫步数", self.max_steps_edit)
        left.addLayout(form)
        self.endmembers_check = QCheckBox("同时弛豫端元（供09使用）")
        self.cell_check = QCheckBox("同时优化晶胞")
        left.addWidget(self.endmembers_check)
        left.addWidget(self.cell_check)
        self.advanced_toggle = QToolButton()
        self.advanced_toggle.setText("续算与运行范围")
        self.advanced_toggle.setCheckable(True)
        left.addWidget(self.advanced_toggle)
        self.advanced_panel = QWidget()
        advanced = QFormLayout(self.advanced_panel)
        self.limit_edit = QLineEdit()
        self.limit_edit.setPlaceholderText("留空处理全部任务")
        self.retry_check = QCheckBox("重试失败项")
        self.overwrite_check = QCheckBox("覆盖已有结果并重新计算")
        advanced.addRow("任务数量上限", self.limit_edit)
        advanced.addRow(self.retry_check)
        advanced.addRow(self.overwrite_check)
        self.advanced_panel.hide()
        self.advanced_toggle.toggled.connect(self.advanced_panel.setVisible)
        left.addWidget(self.advanced_panel)
        left.addWidget(
            self._label(
                "默认沿用相同配置下的已有结果；未收敛或质量检查未通过的能量不会作为09的可用证据。"
            )
        )
        left.addStretch()
        form = QFormLayout()
        self.output_dir_edit = self._path_row(form, "弛豫输出文件夹", mode="directory")
        self.results_edit = self._path_row(form, "弛豫结果 JSONL", mode="results")
        right.addLayout(form)
        right.addWidget(
            self._label(
                "输出优化后的结构、逐结构运行记录，以及包含能量、力、应力和收敛状态的结果表。"
            )
        )
        self.status_label, self.mode_note = self._label(""), self._label("")
        right.addWidget(self.status_label)
        right.addWidget(self.mode_note)
        right.addStretch()
        self.run_button = QPushButton("开始 MACE弛豫")
        self.run_button.setObjectName("primaryButton")
        self.run_button.clicked.connect(self.emit_run)
        self.mixing_button = QPushButton("进入 09 混合焓")
        self.mixing_button.clicked.connect(self.open_mixing)
        right.addWidget(self.run_button)
        right.addWidget(self.mixing_button)
        right.addWidget(self._label("有可用的合金和两端元能量后，带入09核对输出位置再计算混合焓。"))
        columns.addWidget(inputs, 1)
        columns.addWidget(outputs, 1)
        root.addLayout(columns)
        root.addStretch()
        for form in self.findChildren(QFormLayout):
            form.setRowWrapPolicy(QFormLayout.WrapLongRows)
            form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for edit in self._fields().values():
            edit.textChanged.connect(self.refresh_preview)
        for check in self._checks().values():
            check.toggled.connect(self.refresh_preview)
        self.device_combo.currentTextChanged.connect(self.refresh_preview)
        self.dtype_combo.currentTextChanged.connect(self.refresh_preview)
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

    def _path_row(self, form: QFormLayout, label: str, *, mode: str) -> QLineEdit:
        host, edit, button = QWidget(), QLineEdit(), QPushButton("…")
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        button.setMaximumWidth(34)

        def browse() -> None:
            start = str(self._resolve(edit.text()))
            if mode == "directory":
                value = QFileDialog.getExistingDirectory(self, label, start)
            elif mode == "model":
                value = QFileDialog.getOpenFileName(
                    self, label, start, "模型 (*.model *.pt *.pth);;所有文件 (*)"
                )[0]
            else:
                value = QFileDialog.getSaveFileName(self, label, start, "JSONL (*.jsonl)")[0]
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
            "model_path": self.model_edit,
            "model_name": self.model_name_edit,
            "fmax": self.fmax_edit,
            "max_steps": self.max_steps_edit,
            "limit": self.limit_edit,
            "output_dir": self.output_dir_edit,
            "results_path": self.results_edit,
        }

    def _checks(self) -> dict[str, QCheckBox]:
        return {
            "include_endmembers": self.endmembers_check,
            "relax_cell": self.cell_check,
            "retry_failed": self.retry_check,
            "overwrite": self.overwrite_check,
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
        for name, edit in self._fields().items():
            if name in values:
                edit.setText("" if values[name] is None else str(values[name]))
        for name, check in self._checks().items():
            if name in values:
                check.setChecked(bool(values[name]))
        if "device" in values:
            self.device_combo.setCurrentText(str(values["device"]))
        if "dtype" in values:
            self.dtype_combo.setCurrentText(str(values["dtype"]))
        self.advanced_toggle.setChecked(
            bool(
                self.limit_edit.text()
                or self.retry_check.isChecked()
                or self.overwrite_check.isChecked()
            )
        )
        self.refresh_preview()

    def restore_argv(self, argv: list[str]) -> None:
        self.reset()
        values = {}
        for option in self.command.params:
            for index, token in enumerate(argv):
                if token in option.opts:
                    if option.is_flag:
                        values[option.name] = True
                    elif index + 1 < len(argv):
                        values[option.name] = argv[index + 1]
                elif token in option.secondary_opts:
                    values[option.name] = False
        self.apply_values(values)

    def argv(self) -> list[str]:
        manifest, dataset, _, _ = self.input_provider()
        argv = [
            "stability",
            "relax",
            "--manifest",
            manifest,
            "--backend",
            "mace",
            "--device",
            self.device_combo.currentText(),
            "--dtype",
            self.dtype_combo.currentText(),
        ]
        try:
            needs_dataset = self.endmembers_check.isChecked() and requires_endpoint_dataset(
                self._resolve(manifest)
            )
        except (OSError, ValueError, TypeError):
            needs_dataset = False
        if needs_dataset and dataset:
            argv.extend(["--dataset", dataset])
        for option in self.command.params:
            if option.name in self._fields():
                value = self._fields()[option.name].text().strip()
                if value:
                    argv.extend([option.opts[0], value])
            elif option.name in self._checks():
                if self._checks()[option.name].isChecked():
                    argv.append(option.opts[0])
                elif option.secondary_opts:
                    argv.append(option.secondary_opts[0])
        return argv

    def _parameters(self) -> dict[str, Any]:
        if not self.output_dir_edit.text().strip() or not self.results_edit.text().strip():
            raise ValueError("请设置弛豫输出文件夹和结果JSONL。")
        command = copy.copy(self.command)
        command.params = [copy.copy(param) for param in self.command.params]
        for param in command.params:
            if isinstance(param.type, click.Path):
                param.type = copy.copy(param.type)
                param.type.exists = False
                param.type.resolve_path = False
        with command.make_context("relax", self.argv()[2:]) as context:
            values = context.params
        if not math.isfinite(values["fmax"]):
            raise ValueError("力收敛阈值须为正的有限数值。")
        return values

    def set_external_mode(self, external: bool) -> None:
        self.external_mode = external
        self.run_button.setText("导出外部执行命令" if external else "开始 MACE弛豫")
        self.mode_note.setText(
            "本工程的MACE在外部环境运行；导出命令执行后，将结果及结构放回所设输出位置并刷新。"
            if external
            else ""
        )
        self.refresh_preview()

    def result_status(self) -> dict[str, Any]:
        try:
            manifest, dataset, pairs, ready = self.input_provider()
            if not ready:
                return {"ready": False, "message": "等待07当前SQS清单及结构。"}
            parameters = self._parameters()
            parameters["dataset_path"] = dataset or None
            return relaxation_status(
                self.project_provider(),
                manifest,
                pairs,
                self.results_edit.text().strip(),
                self.output_dir_edit.text().strip(),
                parameters,
                external=self.external_mode,
            )
        except (click.ClickException, OSError, ValueError) as exc:
            return {"ready": False, "message": str(exc)}

    def validated_result(self) -> str | None:
        return self.results_edit.text().strip() if self.result_status().get("ready") else None

    def refresh_preview(self) -> None:
        manifest, dataset, _, ready = self.input_provider()
        self.manifest_edit.setText(manifest)
        self.dataset_edit.setText(dataset)
        for edit in (self.manifest_edit, self.dataset_edit):
            edit.setToolTip(edit.text())
            edit.setCursorPosition(0)
        self.source_label.setText(
            "已自动关联07当前SQS清单；02数据仅作为旧清单的端元结构补充。"
            if ready
            else "07当前输出尚未就绪，请生成SQS后刷新。"
        )
        status = self.result_status()
        prefix = (
            f"成功 {status['success']}，未收敛 {status['not_converged']}，失败 {status['failed']}。\n"
            if "success" in status
            else ""
        )
        use_cache = self.uses_demo_cache()
        message = "点击“进入 09 混合焓”校验本算例预置的弛豫结果。" if use_cache else status["message"]
        self.status_label.setText(prefix + message)
        self.mixing_button.setEnabled(use_cache or status["ready"])

    def emit_run(self) -> None:
        try:
            params = self._parameters()
            manifest, dataset, _, ready = self.input_provider()
            if not ready:
                raise ValueError("请先完成07当前SQS生成。")
            if not self.external_mode and not self._resolve(self.model_edit.text()).is_file():
                raise ValueError("请选择本地可用的MACE模型文件。")
            path = self._resolve(manifest)
            for row in manifest_rows(path):
                required = [row["structure_path"]]
                if params["include_endmembers"]:
                    for side in ("a", "b"):
                        value = row.get(f"endpoint_{side}_structure_path")
                        if value:
                            required.append(value)
                        elif not self._resolve(dataset).is_file():
                            raise ValueError("旧清单缺少端元结构，且02结构数据不可用。")
                if any(
                    not structure_path(self.project_provider(), path, value).is_file()
                    for value in required
                ):
                    raise ValueError("07清单中的结构文件缺失。")
            output, results = self._resolve(self.output_dir_edit.text()), self._resolve(
                self.results_edit.text()
            )
            inputs = {
                path.resolve(),
                self._resolve(dataset).resolve(),
                self._resolve(self.model_edit.text()).resolve(),
            }
            if (
                results.resolve() in inputs
                or output.resolve() in inputs
                or results.resolve() == output.resolve()
            ):
                raise ValueError("输出位置不能覆盖输入文件，结果文件不能与输出目录重合。")
        except (click.ClickException, OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(self, "检查弛豫输入与参数", str(exc))
            return
        self.run_requested.emit(self.argv(), self.presentation.title)

    def open_mixing(self) -> None:
        if self.uses_demo_cache() or self.validated_result():
            self.mixing_requested.emit()
        else:
            self.refresh_preview()
