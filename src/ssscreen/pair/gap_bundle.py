"""Portable Stage 05 input ZIP built using the existing gap export contract."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

import pandas as pd

from .. import __version__
from ..config import GAP_EXPORT_MAX_ATOMS, GAP_PENDING_METHOD
from ..data.io import load_group_df
from .gap_export import _calculation_structure, export_gap_candidates

_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
_FORMATS = ("json", "cif", "poscar")
_PATH_COLUMNS = (
    "structure_path",
    "structure_json_path",
    "structure_cif_path",
    "structure_poscar_path",
)


def _sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def export_gap_bundle(
    groups_path: str | Path,
    dataset_path: str | Path,
    output: str | Path,
    *,
    max_natoms: int = GAP_EXPORT_MAX_ATOMS,
    structure_col: str = "structure",
) -> dict:
    """Produce one ZIP, with portable structures, tasks, templates, provenance and instructions."""
    groups_path, dataset_path, output = map(Path, (groups_path, dataset_path, output))
    if output.suffix.lower() != ".zip":
        raise ValueError("压缩包输出文件必须以 .zip 结尾")
    if output.exists():
        raise FileExistsError(f"输出已存在，请选择新的压缩包文件名：{output}")
    if max_natoms < 1:
        raise ValueError("max_natoms must be positive")
    groups = load_group_df(groups_path)
    ids = list(dict.fromkeys(str(mid) for group in groups for mid in group.mp_ids))
    if any(not _SAFE_ID.fullmatch(mid) or mid.endswith(".") for mid in ids):
        raise ValueError("材料ID包含不适合结构文件名的字符")
    dataset = pd.read_pickle(dataset_path)
    if not dataset.index.is_unique:
        raise ValueError("结构数据集包含重复材料ID")
    if structure_col not in dataset:
        raise ValueError(f"结构数据集缺少字段：{structure_col}")
    missing = sorted(set(ids) - set(dataset.index))
    if missing:
        raise ValueError(f"结构数据集缺少 {len(missing)} 个候选材料：{', '.join(missing[:5])}")
    skipped = [
        {"material_id": mid, "natoms": size, "reason": "max_natoms"}
        for mid in ids
        if (size := len(_calculation_structure(dataset.loc[mid], structure_col))) > max_natoms
    ]
    if len(skipped) == len(ids):
        raise ValueError("当前分组与原子数范围内没有可导出的材料")
    source_hashes = {"groups_sha256": _sha256(groups_path), "dataset_sha256": _sha256(dataset_path)}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".gap-bundle-", dir=output.parent) as temporary:
        staging = Path(temporary) / "package"
        staging.mkdir()
        tasks = export_gap_candidates(
            groups_path,
            dataset_path,
            staging / "tasks.csv",
            method=GAP_PENDING_METHOD,
            structure_dir=staging / "structures",
            structure_formats=_FORMATS,
            results_template=staging / "results_template.csv",
            method_metadata_template=staging / "method_metadata.json",
            structure_col=structure_col,
            max_natoms=max_natoms,
        )
        for column in _PATH_COLUMNS:
            tasks[column] = tasks[column].map(
                lambda value: Path(value).relative_to(staging).as_posix()
            )
        tasks.to_csv(staging / "tasks.csv", index=False)
        pd.DataFrame(skipped, columns=["material_id", "natoms", "reason"]).to_csv(
            staging / "skipped_materials.csv", index=False
        )
        shutil.copyfile(groups_path, staging / "groups.json")
        shutil.copyfile(
            Path(__file__).with_name("gap_bundle_prepare.py"), staging / "prepare_calculation.py"
        )
        provenance = {
            **source_hashes,
            "groups_file": groups_path.name,
            "dataset_file": dataset_path.name,
            "structure_column": structure_col,
            "max_natoms": max_natoms,
            "group_count": len(groups),
            "candidate_material_count": len(ids),
            "task_count": len(tasks),
            "skipped_count": len(skipped),
            "scope": "Members of the supplied groups only; the upstream screening may be partial.",
            "ssscreen_version": __version__,
        }
        (staging / "provenance.json").write_text(
            json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (staging / "README_zh.md").write_text(
            f"""# 带隙计算输入包

本包包含{len(groups)}个输入结构组、{len(tasks)}个去重材料任务。沿用最多{max_natoms}原子的导出范围；跳过{len(skipped)}项，详见skipped_materials.csv。

## 文件

- tasks.csv：待交接任务、材料ID、结构哈希及结构相对路径。
- structures/：全部任务的JSON、CIF和POSCAR（.vasp）结构。
- groups.json：本次04分组，含任务与原结构组的关联。
- results_template.csv：待返回的带隙表，初始状态为pending，未填写的值不代表零带隙。
- method_metadata.json：由实际计算人员填写的软件、方法和计算条件。
- provenance.json、bundle_manifest.json：输入来源校验和、导出范围及逐文件SHA256。
- prepare_calculation.py：用实际方法生成正式任务/返回模板，仅需Python标准库。

## VASP结果文件夹回传（GUI推荐）

1. 保留根目录tasks.csv中的原任务ID，在外部计算对应结构。
2. 将各材料最终带隙计算的输出按“VASP结果/gap-原任务ID/vasprun.xml”组织；也支持vasprun.xml.gz。任务目录内直接放该文件，不添加mbj等中间层。
3. 回到原SS-Screen工程，在05“收集VASP带隙结果”中只选择VASP结果总目录。软件自动使用本工程导出的ZIP关联材料，从XML记录实际计算条件和结构，并保留原任务对应关系。无需在GUI另选或上传tasks.csv。
4. 收集后点击“进入结果校验”。若从prepared任务计算，则本工程也需保留那批prepared任务对应记录；请勿自行改目录中的任务ID。

## 手工CSV回传（其他外部平台兼容方式）

1. 解压到任意目录。表中所有结构路径相对于解压根目录，无需本机原始数据库。
2. 实际计算人员填写method_metadata.json，包括实际method标识、calculator、functional及真实settings等条件。
3. 运行 `python prepare_calculation.py`，生成prepared/tasks.csv、prepared/results_template.csv、prepared/method_metadata.json。原始任务保持不变，新任务保留pending_task_id映射。prepared内任务表的结构路径仍相对于解压根目录。
4. 使用所选外部计算软件计算structures中的晶体；将实际带隙（eV）、直接性、success/not_converged/failed等状态填入prepared/results_template.csv，另存为results_returned.csv。保留任务身份、结构和设置哈希，失败项不填零值冒充成功。
5. 回传results_returned.csv、prepared/tasks.csv和prepared/method_metadata.json，在SS-Screen的05“校验外部带隙结果”中分别选择这三项输入。校验后再进入06。

此包是材料结构和数据交接输入，不包含已计算的带隙或已确定的DFT设置。INCAR、KPOINTS、赝势、作业脚本等由实际计算人员按所选方法准备。已有计算结果应保留其真实身份并通过对应表回填，不能直接替换待定方法字段。
""",
            encoding="utf-8",
        )
        if source_hashes != {
            "groups_sha256": _sha256(groups_path),
            "dataset_sha256": _sha256(dataset_path),
        }:
            raise ValueError("导出过程中输入文件发生变化，请重试")
        manifest = {
            "schema_version": 1,
            "kind": "ssscreen-gap-input-bundle",
            "pending_method": GAP_PENDING_METHOD,
            **provenance,
            "files": {
                path.relative_to(staging).as_posix(): _sha256(path)
                for path in sorted(staging.rglob("*"))
                if path.is_file()
            },
        }
        (staging / "bundle_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        archive_path = Path(temporary) / "bundle.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(staging).as_posix())
        # Exclusive publication preserves any file created by another run in the meantime.
        created = False
        try:
            with output.open("xb") as target, archive_path.open("rb") as source:
                created = True
                shutil.copyfileobj(source, target)
                target.flush()
                os.fsync(target.fileno())
        except FileExistsError:
            raise
        except BaseException:
            if created:
                output.unlink(missing_ok=True)
            raise
    return manifest
