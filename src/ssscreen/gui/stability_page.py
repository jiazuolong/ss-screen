"""Stages 09–11: live upstream inputs and separate calculation/output controls."""

from __future__ import annotations

import copy
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
from PySide6.QtCore import QSignalBlocker, Signal
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
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .metadata import PATH_PRESETS, CommandPresentation, option_label_zh
from .sqs_results import resolve_path

STABILITY_PATHS = {
    "09": ("stability", "mixing-enthalpy"),
    "10": ("stability", "phonon-run"),
    "11": ("stability", "phase-diagram"),
}
SOURCE_FIELDS = {
    "09": {"pairs_path": "06 端元对（自动）", "relax_results_path": "08 弛豫结果（自动）"},
    "10": {"relax_results_path": "08 弛豫结果（自动）", "model_path": "08 MACE模型（自动）"},
    "11": {
        "candidate_relax_results_path": "08 弛豫结果（自动）",
        "model_path": "08 MACE模型（自动）",
        "mp_backend": "01 数据模式（自动）",
        "offline_db": "01 离线数据库（自动）",
    },
}
INHERITED_MODEL = {"model_path", "model_name", "dtype"}
INHERITED_RELAXATION = {"fmax", "max_steps", "relax_cell"}
PRIMARY_FIELDS = {
    "09": set(),
    "10": {
        "include_endmembers",
        "supercell",
        "displacement",
        "mesh",
        "band_points",
        "imaginary_tolerance",
        "device",
    },
    "11": {"mp_max_e_hull", "max_phase_atoms", "screening_cutoff", "device", "allow_incomplete"},
}
OUTPUT_FIELDS = {
    "09": {"output_path": "混合焓结果 CSV", "summary_path": "计算摘要 JSON"},
    "10": {"output_dir": "声子输出文件夹"},
    "11": {"output_dir": "竞争相输出文件夹"},
}
NEXT_STAGE = {"09": "10", "10": "11", "11": "12"}
NEXT_LABEL = {"09": "进入 10 声子谱", "10": "进入 11 竞争相 / 凸包", "11": "进入 12 综合推荐"}
RUN_LABEL = {"09": "计算混合焓", "10": "开始声子计算", "11": "开始竞争相与凸包计算"}


class StabilityPage(QWidget):
    run_requested = Signal(list, str)
    next_requested = Signal(str)

    def __init__(
        self,
        presentation: CommandPresentation,
        command: click.Command,
        project_provider: Callable[[], Path],
        input_provider: Callable[[str], dict[str, Any]],
        input_validator: Callable[[str], dict[str, Any]],
        editor_factory: Callable[..., QWidget],
    ) -> None:
        super().__init__()
        self.presentation, self.command = presentation, command
        self.stage = presentation.stage
        self.project_provider = project_provider
        self.input_provider, self.input_validator = input_provider, input_validator
        self.external_mode = False
        self.editors = []
        self.source_edits: dict[str, QLineEdit] = {}
        self.source_names = set(SOURCE_FIELDS[self.stage])
        if self.stage != "09":
            self.source_names |= INHERITED_MODEL
        if self.stage == "11":
            self.source_names |= INHERITED_RELAXATION
        root = QVBoxLayout(self)
        title = QLabel(presentation.title)
        title.setObjectName("pageTitle")
        root.addWidget(title)
        descriptions = {
            "09": "自动读取06端元对与08能量，计算合金相对两端元的混合焓。",
            "10": "自动读取08弛豫结构和MACE模型，设置超胞与采样参数后计算声子谱。",
            "11": "自动读取08弛豫结果及01数据源，用相同MACE条件计算竞争相与凸包。",
        }
        root.addWidget(self._label(descriptions[self.stage]))
        columns = QHBoxLayout()
        inputs, outputs = QGroupBox("输入栏 / Inputs"), QGroupBox("输出栏 / Outputs")
        left, right = QVBoxLayout(inputs), QVBoxLayout(outputs)
        source_form = self._form()
        for name, label in SOURCE_FIELDS[self.stage].items():
            edit = QLineEdit()
            edit.setReadOnly(True)
            self.source_edits[name] = edit
            source_form.addRow(label, edit)
        left.addLayout(source_form)
        self.source_note = self._label("")
        left.addWidget(self.source_note)
        refresh = QPushButton("刷新上游结果")
        refresh.clicked.connect(self.refresh_preview)
        left.addWidget(refresh)
        primary, output_form = self._form(), self._form()
        self.advanced_toggle = QToolButton()
        self.advanced_toggle.setText("更多计算与续算参数")
        self.advanced_toggle.setCheckable(True)
        self.advanced_panel = QWidget()
        advanced = self._form()
        self.advanced_panel.setLayout(advanced)
        self.advanced_panel.hide()
        self.advanced_toggle.toggled.connect(self.advanced_panel.setVisible)
        presets = PATH_PRESETS[presentation.command_path]
        for option in command.params:
            if option.name in self.source_names or option.name in {"structure_ids", "help"}:
                continue
            editor = editor_factory(option, preset=presets.get(option.opts[0]))
            if option.name == "supercell":
                editor.widget.setPlaceholderText("留空按最小边长自动扩胞")
            self.editors.append((option, editor))
            editor.changed.connect(self.refresh_preview)
            editor.setToolTip(option.help or "")
            if option.name in OUTPUT_FIELDS[self.stage]:
                output_form.addRow(OUTPUT_FIELDS[self.stage][option.name], editor)
            else:
                target = primary if option.name in PRIMARY_FIELDS[self.stage] else advanced
                target.addRow(option_label_zh(option.name), editor)
        left.addLayout(primary)
        if advanced.rowCount():
            left.addWidget(self.advanced_toggle)
            left.addWidget(self.advanced_panel)
        if self.stage == "09":
            left.addWidget(
                self._label("使用08中具有相同能量基准的合金和两端元结果，无需另选模型。")
            )
        else:
            left.addWidget(
                self._label("处理当前08批次的全部合金；旧批次的结构编号列表不再限制新输入。")
            )
        left.addStretch()
        right.addLayout(output_form)
        products = {
            "09": "输出每项合金的混合焓、端元参考能量及成功/缺失状态。",
            "10": "输出位移任务、力结果、phonon_summary.csv、频带/DOS图和计算报告。",
            "11": "输出竞争相结构与能量、phase_stability.csv、hull_entries.csv及计算摘要。",
        }
        right.addWidget(self._label(products[self.stage]))
        self.status_label, self.mode_note = self._label(""), self._label("")
        right.addWidget(self.status_label)
        right.addWidget(self.mode_note)
        if self.stage in {"10", "11"}:
            self.library_button = QPushButton("从全量结果库匹配本批")
            self.library_button.clicked.connect(self.import_library)
            right.addWidget(self.library_button)
        right.addStretch()
        reset = QPushButton("恢复本步默认参数")
        reset.clicked.connect(self.reset)
        right.addWidget(reset)
        self.run_button = QPushButton(RUN_LABEL[self.stage])
        self.run_button.setObjectName("primaryButton")
        self.run_button.clicked.connect(self.emit_run)
        right.addWidget(self.run_button)
        self.next_button = QPushButton(NEXT_LABEL[self.stage])
        self.next_button.clicked.connect(lambda: self.next_requested.emit(NEXT_STAGE[self.stage]))
        right.addWidget(self.next_button)
        right.addWidget(self._label("进入下一步可核对参数；计算由各页面的运行按钮启动。"))
        columns.addWidget(inputs, 1)
        columns.addWidget(outputs, 1)
        root.addLayout(columns)
        root.addStretch()
        self.refresh_preview()

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setMinimumWidth(0)
        label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        return label

    @staticmethod
    def _form() -> QFormLayout:
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        return form

    def _resolve(self, value: str | Path) -> Path:
        return resolve_path(self.project_provider(), str(value))

    def editor(self, name: str):
        return next(editor for option, editor in self.editors if option.name == name)

    def reset(self) -> None:
        for _, editor in self.editors:
            blocker = QSignalBlocker(editor.widget)
            editor.reset()
            del blocker
        self.advanced_toggle.setChecked(False)
        self.refresh_preview()

    def apply_values(self, values: dict[str, Any]) -> None:
        if self.stage == "10" and "min_supercell_length" in values and "supercell" not in values:
            # Imported runs can explicitly use automatic expansion without a
            # supercell option. Do not replace that choice with the GUI preset.
            values = {**values, "supercell": None}
        for option, editor in self.editors:
            if option.name in values:
                value = values[option.name]
                if value is getattr(click.core, "UNSET", None):
                    value = None
                blocker = QSignalBlocker(editor.widget)
                editor.set_value(value)
                del blocker
        self.refresh_preview()

    def _parser(self, *, callbacks: bool) -> click.Command:
        command = copy.copy(self.command)
        command.params = [copy.copy(param) for param in command.params]
        for param in command.params:
            if not callbacks:
                param.callback = None
            if isinstance(param.type, click.Path):
                param.type = copy.copy(param.type)
                param.type.exists = False
                param.type.resolve_path = False
        return command

    def restore_argv(self, argv: list[str]) -> None:
        command = self._parser(callbacks=False)
        with command.make_context(command.name, argv[2:]) as context:
            self.apply_values(context.params)

    def argv(self) -> list[str]:
        values = self.input_provider(self.stage)
        argv = list(self.presentation.command_path)
        for option in self.command.params:
            if option.name not in self.source_names:
                continue
            value = values.get(option.name)
            if option.is_bool_flag:
                if value:
                    argv.append(option.opts[0])
                elif option.secondary_opts:
                    argv.append(option.secondary_opts[0])
            elif value is not None and str(value).strip():
                argv.extend([option.opts[0], str(value)])
        for _, editor in self.editors:
            argv.extend(editor.argv())
        return argv

    def _parameters(self) -> dict[str, Any]:
        for name in OUTPUT_FIELDS[self.stage]:
            if self.editor(name).is_empty():
                raise ValueError("请设置本步输出位置。")
        command = self._parser(callbacks=True)
        with command.make_context(command.name, self.argv()[2:]) as context:
            values = context.params
        if any(isinstance(value, float) and not math.isfinite(value) for value in values.values()):
            raise ValueError("计算参数须为有限数值。")
        return values

    def output_paths(self) -> dict[str, str]:
        values = {
            name: self.editor(name).values()[0] if self.editor(name).values() else ""
            for name in OUTPUT_FIELDS[self.stage]
        }
        if self.stage == "09":
            return {"result": values["output_path"], "summary": values["summary_path"]}
        directory = Path(values["output_dir"])
        if self.stage == "10":
            return {"result": str(directory / "phonon_summary.csv")}
        return {
            "result": str(directory / "phase_stability.csv"),
            "entries": str(directory / "hull_entries.csv"),
        }

    def set_external_mode(self, external: bool) -> None:
        self.external_mode = external
        self.run_button.setText("导出外部执行命令" if external else RUN_LABEL[self.stage])
        self.mode_note.setText(
            "本工程在外部环境运行此步骤；导出后执行，将结果放回所设输出目录。" if external else ""
        )

    def refresh_preview(self) -> None:
        if hasattr(self,"library_button"):
            self.library_button.setVisible(not (Path(self.project_provider())/"ten_micron.json").is_file())
        values = self.input_provider(self.stage)
        for name, edit in self.source_edits.items():
            edit.setText(str(values.get(name) or ""))
            edit.setToolTip(edit.text())
            edit.setCursorPosition(0)
        if self.stage == "09":
            note = "输入始终跟随06和08当前输出位置。"
        else:
            note = f"继承08：{values.get('model_name') or 'MACE'}，精度 {values.get('dtype', '')}。"
            if self.stage == "11":
                note += (
                    f"\n弛豫力阈值 {values.get('fmax')}，最大 {values.get('max_steps')} 步，"
                    + ("优化晶胞。" if values.get("relax_cell") else "固定晶胞。")
                )
                offline = values.get("mp_backend") == "offline"
                self.source_edits["offline_db"].setEnabled(offline)
                for name in ("thermo_type", "api_timeout"):
                    self.editor(name).setEnabled(not offline)
            else:
                for name in ("min_supercell_length",):
                    self.editor(name).setEnabled(self.editor("supercell").is_empty())
        self.source_note.setText(note)
        result = values.get("relax_results_path") or values.get("candidate_relax_results_path")
        found = bool(result and self._resolve(result).is_file())
        self.status_label.setText(
            "已找到08结果文件；运行时核对当前批次。" if found else "等待08当前弛豫结果。"
        )

    def import_library(self):
        values = self.input_provider(self.stage)
        kind = "phonon" if self.stage == "10" else "phase"
        library, _ = QFileDialog.getOpenFileName(self, "选择声子全量库" if kind=="phonon" else "选择凸包全量库",
                                                  str(self.project_provider()), "结果库 (*.csv)")
        if not library:
            return
        result = self.output_paths()["result"]
        prompt = f"匹配当前合金并写入 {result}。未命中标记为缺失；已有不同结果会先备份。继续？"
        if QMessageBox.question(self, "从全量库匹配", prompt) != QMessageBox.Yes:
            return
        argv = ["stability","match-library","--kind",kind,"--library",library,
                "--relaxation",values.get("relax_results_path") or values["candidate_relax_results_path"],
                "--pairs",values["pairs_path"],"--output",result]
        if kind=="phase" and values.get("offline_db"):
            argv.extend(["--database",values["offline_db"]])
        self.run_requested.emit(argv, "匹配历史声子结果" if kind=="phonon" else "匹配历史凸包结果")

    def emit_run(self) -> None:
        try:
            params = self._parameters()
            status = self.input_validator(self.stage)
            if not status.get("ready"):
                raise ValueError(status.get("message", "上游结果尚未就绪。"))
            if self.stage != "09" and not self.external_mode:
                if not self._resolve(params["model_path"]).is_file():
                    raise ValueError("08模型文件在本地不存在，请先在08选择可用模型。")
                if self.stage == "11" and params["mp_backend"] == "offline":
                    if (
                        not params["offline_db"]
                        or not self._resolve(params["offline_db"]).is_file()
                    ):
                        raise ValueError("01离线数据库不可用，请先在01设置数据库。")
            inputs = {
                self._resolve(value).resolve()
                for name, value in self.input_provider(self.stage).items()
                if value
                and name
                in {
                    "pairs_path",
                    "relax_results_path",
                    "candidate_relax_results_path",
                    "model_path",
                    "offline_db",
                }
            }
            outputs = [self._resolve(params[name]).resolve() for name in OUTPUT_FIELDS[self.stage]]
            if len(set(outputs)) != len(outputs) or any(path in inputs for path in outputs):
                raise ValueError("输出不能覆盖输入，两个输出文件不能使用同一路径。")
        except (click.ClickException, OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(self, "检查输入与计算参数", str(exc))
            return
        self.run_requested.emit(self.argv(), self.presentation.title)
