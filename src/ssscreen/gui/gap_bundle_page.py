"""Minimal Stage 05 form: two inputs and a single ZIP output."""

from __future__ import annotations

import copy
import json
import zipfile
from collections.abc import Callable
from pathlib import Path

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
    QVBoxLayout,
    QWidget,
)

from ..config import GAP_EXPORT_MAX_ATOMS


class GapBundlePage(QWidget):
    """Use the real gap-export CLI while keeping file bookkeeping out of the form."""

    run_requested = Signal(list, str)

    def __init__(
        self,
        presentation,
        command: click.Command,
        project_provider: Callable,
        upstream_provider: Callable,
    ) -> None:
        super().__init__()
        self.presentation, self.command = presentation, command
        self.project_provider, self.upstream_provider = project_provider, upstream_provider
        self.editors = []  # Compatibility with the generic saved-command adapter.
        self._max_natoms = GAP_EXPORT_MAX_ATOMS
        self._structure_column = "structure"
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        title = QLabel("准备带隙计算输入")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        note = QLabel("把筛选后的材料结构和交接说明打包，供外部计算带隙。")
        note.setWordWrap(True)
        root.addWidget(note)
        columns = QHBoxLayout()
        input_box = QGroupBox("输入栏 / Inputs")
        left = QVBoxLayout(input_box)
        hint = QLabel("选择04的筛选结果和提供晶体结构的数据表。")
        hint.setWordWrap(True)
        left.addWidget(hint)
        form = QFormLayout()
        self.groups_edit = self._path_row(form, "04筛选结果")
        self.dataset_edit = self._path_row(form, "材料结构数据")
        left.addLayout(form)
        use_upstream = QPushButton("读取上一步输出")
        use_upstream.clicked.connect(self.use_upstream)
        left.addWidget(use_upstream)
        self.scope_label = QLabel()
        self.scope_label.setWordWrap(True)
        left.addWidget(self.scope_label)
        left.addStretch()
        output_box = QGroupBox("输出栏 / Outputs")
        right = QVBoxLayout(output_box)
        hint = QLabel("生成一个ZIP压缩包，可直接复制到外部计算机器。")
        hint.setWordWrap(True)
        right.addWidget(hint)
        form = QFormLayout()
        self.output_edit = self._path_row(form, "压缩包保存位置", save=True)
        right.addLayout(form)
        contents = QLabel(
            "包内包含：任务清单、全部任务结构、结果填写模板、计算条件模板、来源记录和使用说明。"
        )
        contents.setWordWrap(True)
        right.addWidget(contents)
        self.result_label = QLabel("尚未导出")
        self.result_label.setWordWrap(True)
        right.addWidget(self.result_label)
        right.addStretch()
        columns.addWidget(input_box, 1)
        columns.addWidget(output_box, 1)
        root.addLayout(columns)
        actions = QHBoxLayout()
        actions.addStretch()
        self.run_button = QPushButton("导出计算压缩包")
        self.run_button.setObjectName("primaryButton")
        self.run_button.clicked.connect(self.emit_run)
        actions.addWidget(self.run_button)
        root.addLayout(actions)
        root.addStretch()
        self.output_edit.textChanged.connect(self.refresh_preview)
        self.reset()

    def _resolve(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else Path(self.project_provider()) / path

    def _path_row(self, form: QFormLayout, label: str, *, save: bool = False) -> QLineEdit:
        host = QWidget()
        layout = QHBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit()
        button = QPushButton("…")
        button.setMaximumWidth(34)

        def browse() -> None:
            base = str(self._resolve(edit.text()) if edit.text() else self.project_provider())
            if save:
                value, _ = QFileDialog.getSaveFileName(self, "保存计算压缩包", base, "ZIP (*.zip)")
            else:
                value, _ = QFileDialog.getOpenFileName(self, "选择输入文件", base)
            if value:
                path = Path(value)
                if save and not path.suffix:
                    path = path.with_suffix(".zip")
                try:
                    value = path.relative_to(self.project_provider()).as_posix()
                except ValueError:
                    value = str(path)
                edit.setText(value)

        button.clicked.connect(browse)
        layout.addWidget(edit, 1)
        layout.addWidget(button)
        form.addRow(label, host)
        return edit

    def use_upstream(self) -> None:
        groups, dataset = self.upstream_provider()
        self.groups_edit.setText(groups)
        self.dataset_edit.setText(dataset)

    def reset(self) -> None:
        self._max_natoms, self._structure_column = GAP_EXPORT_MAX_ATOMS, "structure"
        self.use_upstream()
        self.output_edit.setText("05_gap/带隙计算输入.zip")
        self.refresh_preview()

    def apply_values(self, values: dict) -> None:
        for name, edit in (("groups_path", self.groups_edit), ("dataset_path", self.dataset_edit)):
            value = values.get(name, values.get(name.removesuffix("_path")))
            if value:
                edit.setText(str(value))
        if values.get("output"):
            output = Path(values["output"])
            if output.suffix.lower() != ".zip":
                output = output.with_name("带隙计算输入.zip")
            self.output_edit.setText(str(output))
        if values.get("max_natoms") is not None:
            self._max_natoms = int(values["max_natoms"])
        if values.get("structure_col"):
            self._structure_column = str(values["structure_col"])
        self.refresh_preview()

    def restore_argv(self, argv: list[str]) -> None:
        command = copy.copy(self.command)
        command.params = [copy.copy(param) for param in self.command.params]
        for param in command.params:
            if isinstance(param.type, click.Path):
                param.type = copy.copy(param.type)
                param.type.exists = False
                param.type.resolve_path = False
        args = list(argv)
        if args[:1] == ["gap-export"]:
            args = args[1:]
        with command.make_context("gap-export", args) as context:
            self.apply_values(context.params)

    def argv(self) -> list[str]:
        return [
            "gap-export",
            "--bundle",
            "--groups",
            self.groups_edit.text().strip(),
            "--dataset",
            self.dataset_edit.text().strip(),
            "--max-natoms",
            str(self._max_natoms),
            "--structure-column",
            self._structure_column,
            "--output",
            self.output_edit.text().strip(),
        ]

    def missing_required(self) -> list[str]:
        return [
            name
            for name, edit in (
                ("04筛选结果", self.groups_edit),
                ("材料结构数据", self.dataset_edit),
                ("压缩包保存位置", self.output_edit),
            )
            if not edit.text().strip()
        ]

    def emit_run(self) -> None:
        missing = self.missing_required()
        if missing:
            QMessageBox.warning(self, "缺少输入", "请填写：" + "、".join(missing))
            return
        if self._resolve(self.output_edit.text()).suffix.lower() != ".zip":
            QMessageBox.warning(self, "输出文件", "请将压缩包文件名设为 .zip 结尾。")
            return
        self.run_requested.emit(self.argv(), self.presentation.title)

    def refresh_preview(self) -> None:
        self.scope_label.setText(
            f"导出范围：沿用最多 {self._max_natoms} 原子的设置；跳过清单会放入包内。"
        )
        path = self._resolve(self.output_edit.text().strip())
        if not path.is_file():
            self.result_label.setText("尚未导出")
            return
        try:
            with zipfile.ZipFile(path) as archive:
                report = json.loads(archive.read("bundle_manifest.json"))
            self.result_label.setText(
                f"已生成：{report['task_count']} 个材料任务，跳过 {report['skipped_count']} 项。"
            )
        except (OSError, ValueError, KeyError, zipfile.BadZipFile):
            self.result_label.setText("目标文件已存在；请检查内容或选择新的文件名。")
