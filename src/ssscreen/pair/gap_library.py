"""Associate portable historical gap results with the current stage 05 export."""

import json
from collections import Counter
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import numpy as np
import pandas as pd
from pymatgen.core import Lattice
from scipy.optimize import linear_sum_assignment

from ..config import GAP_PENDING_METHOD
from .gap_collect_folder import _load_source
from .gap_export import _canonical_sha256, _same_formula, make_gap_task_id

BASIS_TOLERANCE = 1e-10
SITE_TOLERANCE_ANGSTROM = 1e-8


def _sites(structure):
    keys, coordinates = [], []
    for site in structure["sites"]:
        keys.append(_canonical_sha256({k: v for k, v in site.items() if k not in ("abc", "xyz")}))
        coordinates.append(site["abc"])
    return keys, np.array(coordinates)


def _equivalent(left, right):
    # Geometry check adapted from 演示/05带隙交接/prepare_existing_mbj.py.
    def metadata(structure):
        return {k: v for k, v in structure.items() if k not in ("sites", "lattice")}

    if metadata(left) != metadata(right):
        return False
    a, b = left["lattice"], right["lattice"]
    if a["pbc"] != [True] * 3 or b["pbc"] != a["pbc"]:
        return False
    transform = np.array(a["matrix"]) @ np.linalg.inv(b["matrix"])
    basis = np.rint(transform)
    if (
        not np.allclose(transform, basis, rtol=0, atol=BASIS_TOLERANCE)
        or abs(round(np.linalg.det(basis))) != 1
    ):
        return False
    ka, xa = _sites(left)
    kb, xb = _sites(right)
    if not ka or Counter(ka) != Counter(kb):
        return False
    lattice = Lattice(b["matrix"])
    xa = xa @ transform
    for origin, key in enumerate(kb):
        if key != ka[0]:
            continue
        shifted = xa + xb[origin] - xa[0]
        for species in set(ka):
            distances = lattice.get_all_distances(
                shifted[np.array(ka) == species], xb[np.array(kb) == species]
            )
            rows, cols = linear_sum_assignment(distances)
            if distances[rows, cols].max() > SITE_TOLERANCE_ANGSTROM:
                break
        else:
            return True
    return False


def match_library(source: Path, raw: pd.DataFrame, method: str):
    required = {
        "method",
        "material_id",
        "formula",
        "task_id",
        "structure_sha256",
        "status",
        "band_gap",
    }
    if required - set(raw.columns):
        raise ValueError("历史库缺少列：" + ", ".join(sorted(required - set(raw.columns))))
    if method and method not in set(raw.method):
        raise ValueError(f"历史库中没有计算方法 {method}")
    selected = raw[raw.method == method] if method else raw
    by_material = dict(tuple(selected.groupby("material_id")))
    try:
        pending = _load_source(source)
        with ZipFile(source) as archive:
            tasks, rows, audit = [], [], []
            for task in pending.to_dict("records"):
                current = json.loads(archive.read(task["structure_json_path"]))
                current.pop("@version", None)
                if _canonical_sha256(current) != task["structure_sha256"]:
                    raise ValueError(f"导出结构哈希不一致：{task['material_id']}")
                material = task["material_id"]
                group = by_material.get(material)
                matches = []
                if group is not None:
                    for record in group.to_dict("records"):
                        if (
                            task["method"] != GAP_PENDING_METHOD
                            and task["method"] != record["method"]
                        ):
                            continue
                        sha = record["structure_sha256"]
                        if make_gap_task_id(material, record["method"], sha) != record["task_id"]:
                            raise ValueError(f"历史任务身份无效：{material}")
                        if not _same_formula(record["formula"], task["formula"]):
                            continue
                        historical = None
                        if record.get("structure_json"):
                            historical = json.loads(record["structure_json"])
                            if _canonical_sha256(historical) != sha:
                                raise ValueError(f"历史结构哈希不一致：{material}")
                        if sha == task["structure_sha256"]:
                            matches.append((record, "exact"))
                        elif historical and _equivalent(current, historical):
                            matches.append((record, "equivalent"))
                entry = {"material_id": material, "export_task_id": task["task_id"]}
                if len(matches) == 1:
                    record, reason = matches[0]
                    record.pop("structure_json", None)
                    rows.append(record)
                    task["export_structure_sha256"] = task["structure_sha256"]
                    task["export_task_id"] = task["task_id"]
                    task = {
                        **task,
                        **{k: record[k] for k in ("task_id", "method", "structure_sha256")},
                    }
                    entry["historical_task_id"] = record["task_id"]
                else:
                    reason = (
                        "ambiguous"
                        if matches
                        else ("unverified" if group is not None else "missing")
                    )
                entry["match"] = reason
                audit.append(entry)
                tasks.append(task)
    except (KeyError, BadZipFile, TypeError, np.linalg.LinAlgError) as exc:
        raise ValueError(f"无法核验历史库或当前导出包：{exc}") from exc
    frame = pd.DataFrame(rows, columns=raw.columns.drop("structure_json", errors="ignore"))
    return pd.DataFrame(tasks), frame, audit
