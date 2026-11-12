"""Native workbench settings and verified cache handoff for the 10 µm example."""

import json
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QTreeWidgetItemIterator

from ..ten_micron import (
    CACHED,
    DIRS,
    GAPS,
    MIXING,
    PAIRS,
    PROFILE,
    create_workspace,
    digest,
    pair_signature,
)

NAMES = (
    "离线数据源",
    "组成模板筛选",
    "结构描述归档",
    "结构匹配与材料分组",
    "带隙交接",
    "10 µm 端元配对",
    "SQS 合金",
    "MACE 弛豫",
    "混合焓",
    "声子谱",
    "竞争相与凸包",
    "综合推荐",
    "候选材料评价",
)
CACHE_DETAILS = {
    3: "1,407 份结构描述（部分覆盖）",
    5: "748 个端元的带隙记录",
    7: "108 个 SQS，8 对跳过",
    8: "222 条弛豫记录",
    10: "108 条声子记录",
    11: "76 项凸包及相图",
}


def new_workspace(parent):
    chosen = QFileDialog.getExistingDirectory(parent, "选择空目录新建，或选择已有 10 µm 工作区")
    if not chosen:
        return
    root = Path(chosen)
    if not (root / PROFILE).is_file():
        settings = QSettings("SS-Screen", "TenMicron")
        package = root.parent / "10um预计算模板.zip"
        if not package.is_file():
            package = Path(settings.value("template", "") or ".")
        if not package.is_file():
            value, _ = QFileDialog.getOpenFileName(
                parent, "选择 10 µm 预计算模板", chosen, "模板 (*.zip)"
            )
            if not value:
                return
            package = Path(value)
        try:
            create_workspace(package, root)
        except Exception as exc:
            QMessageBox.warning(parent, "创建工程失败", str(exc))
            return
        settings.setValue("template", str(package))
    parent._add_project(root, initialize=False, activate=True)
    open_stage(parent, 1)


def unpack_example(source, target, profile):
    """Publish the verified native project in the user-selected workspace."""
    from tempfile import TemporaryDirectory

    from .project_file import extract_project_file

    target = Path(target).resolve()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ValueError("请选择空目录；已有算例请直接打开其工程目录。")
    with TemporaryDirectory(dir=target.parent) as temporary:
        staged = Path(temporary) / "project"
        extract_project_file(source, staged)
        for directory in DIRS:
            (staged / directory).mkdir(exist_ok=True)
        (staged / PROFILE).write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        if target.exists():
            target.rmdir()
        staged.rename(target)


def native_settings(profile):
    commands = (
        "dataset mp",
        "composition-screen",
        "condense",
        "structure-match",
        "gap-export",
        "pair-wavelength",
        "stability sqs-generate",
        "stability relax",
        "stability mixing-enthalpy",
        "stability phonon-run",
        "stability phase-diagram",
        "recommend",
    )
    return {
        "ten_micron_profile": profile,
        "workflow_stages": {
            f"{i:02}": {"id": f"{i:02}", "name": name, "note": CACHE_DETAILS.get(i, "")}
            for i, name in enumerate(NAMES, 1)
        },
        "stage_commands": {f"{i:02}": key.split() for i, key in enumerate(commands, 1)},
        "forms": {
            "dataset_source_page": {
                "mp_backend": "offline",
                "mp_offline_db": "01_dataset/default.db",
                "mp_output_follow_input": False,
                "mp_output": "01_dataset/mp.df",
                "mp_provenance": "01_dataset/mp.df.provenance.json",
            },
            "composition_screen_page": {
                "dataframes": ["01_dataset/mp.df"],
                "max_e_hull_edit": "0",
                "binary_enabled": True,
                "ternary_enabled": True,
            },
        },
        "command_values": {
            "pair-wavelength": {
                "wavelength_um": 10,
                "min_gap_exclusive": 0,
                "max_gap_exclusive": 0.4,
            },
            "stability sqs-generate": {
                "backend": "icet",
                "seed": 101,
                "supercell": "2,2,2",
                "target_fractions": "0.5",
            },
            "stability relax": {
                "model_name": "MACE-MPA-0-medium",
                "fmax": 0.01,
                "max_steps": 500,
                "dtype": "float64",
                "relax_cell": True,
            },
            "recommend": {
                "gap_results_path": GAPS,
                "pairs_path": PAIRS,
                "mixing_enthalpy_path": MIXING,
                "phonons_path": "10_phonon/phonon_summary.csv",
                "phase_stability_path": "11_phase/phase_stability.csv",
                "promising_max_mixing": 25,
                "low_priority_mixing": 50,
                "promising_max_hull": 0.025,
                "low_priority_hull": 0.1,
            },
        },
    }


def open_stage(window, stage):
    sid = f"{stage:02}"
    iterator = QTreeWidgetItemIterator(window.nav)
    while iterator.value():
        item = iterator.value()
        data = item.data(0, Qt.UserRole)
        if (
            data
            and data[0] == "stage"
            and data[2] == sid
            and Path(data[1]) == window.project_root()
        ):
            item.parent().setExpanded(True)
            item.setExpanded(True)
            window.nav.setCurrentItem(item)
            window._navigation_clicked(item, 0)
            return
        iterator += 1


@lru_cache(maxsize=8192)
def _signature(path, size, mtime, ctime, pairs):
    return pair_signature(path) if pairs else digest(path)


def check_file(root, name, expected):
    path = root / name
    stat = path.stat()
    if (
        _signature(path, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, name == PAIRS)
        != expected
    ):
        raise ValueError(f"文件与 10 µm 算例不一致：{name}")


def marker(root, stage):
    return root / DIRS[stage - 1] / ".10um-cache-used"


def validate_cache(root, profile, stage):
    provenance = json.loads((root / "01_dataset/mp.df.provenance.json").read_text(encoding="utf-8"))
    if provenance.get("database", {}).get("sha256") != profile["database_sha256"]:
        raise ValueError("请先在 01 读取本算例的 default.db")
    for name, expected in profile["anchors"].items():
        if int(name[:2]) < stage:
            check_file(root, name, expected)
    if stage >= 10 and not (root / MIXING).is_file():
        raise ValueError("请先运行 09 混合焓")
    for prior in sorted(CACHED):
        if prior < stage and not marker(root, prior).is_file():
            raise ValueError(f"请先在 {prior:02} 使用本步预计算结果")
    for name, expected in profile["files"].items():
        if name.startswith(DIRS[stage - 1] + "/"):
            check_file(root, name, expected)


def accept_cache(window, stage=None):
    root = window.project_root()
    if stage is None:
        stage = int(window.workflow.stage)
    try:
        validate_cache(root, window.workflow.settings["ten_micron_profile"], stage)
        if stage == 11:
            window.phase_results_page.set_plot_index(root / "11_phase/plots/phase_plot_index.json")
        marker(root, stage).write_text("10um-116-v1", encoding="utf-8")
    except (OSError, ValueError, KeyError) as exc:
        QMessageBox.warning(window, "本步预计算结果尚不可用", str(exc))
        return
    window._rebuild_project_tree()
    open_stage(window, stage + 1)
    window.statusBar().showMessage(f"已使用 {stage:02} 预计算结果：{CACHE_DETAILS[stage]}")
