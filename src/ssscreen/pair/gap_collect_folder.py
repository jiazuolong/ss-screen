"""Collect a flat VASP return folder using the project's existing exported identities."""

from __future__ import annotations

import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pandas as pd
from monty.json import MontyEncoder
from pymatgen.io.vasp.outputs import Vasprun

from .gap_collect_vasp import ParsedVaspGap, _find_vasprun, _parse_vasprun, _result_record
from .gap_export import (
    GAP_SCHEMA_VERSION,
    _canonical_sha256,
    _load_gap_tasks,
    _same_formula,
    _structure_sha256,
    make_gap_task_id,
    validate_gap_results,
)

# Actual XML settings, not a user-supplied label, define the method family.
_METHOD_KEYS = (
    "GGA",
    "METAGGA",
    "LHFCALC",
    "HFSCREEN",
    "AEXX",
    "ISPIN",
    "LSORBIT",
    "LNONCOLLINEAR",
    "LDAU",
    "LUSE_VDW",
    "IVDW",
)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_source(path: Path) -> pd.DataFrame:
    if path.suffix.lower() != ".zip":
        return _load_gap_tasks(path)
    with ZipFile(path) as archive:
        payload = archive.read("tasks.csv")
        manifest = json.loads(archive.read("bundle_manifest.json"))
        if hashlib.sha256(payload).hexdigest() != manifest["files"]["tasks.csv"]:
            raise ValueError("导出包中的任务清单校验失败")
        return _load_gap_tasks(pd.read_csv(io.BytesIO(payload), keep_default_na=False))


def _select_source(
    sources: tuple[Path, ...], returned_ids: set[str]
) -> tuple[pd.DataFrame, Path, list[dict]]:
    candidates = list(dict.fromkeys(sources))
    # Support locally registered prepared tasks without asking the user to upload a CSV.
    for source in sources:
        if source.suffix.lower() == ".zip":
            candidates.extend(
                (
                    source.parent / "prepared/tasks.csv",
                    source.with_suffix("") / "prepared/tasks.csv",
                )
            )
    diagnostics = []
    matches = []
    for candidate in dict.fromkeys(candidates):
        if not candidate.is_file():
            continue
        try:
            tasks = _load_source(candidate)
        except (OSError, ValueError, KeyError) as exc:
            if candidate in sources:
                raise ValueError(f"无法读取本工程导出批次 {candidate}: {exc}") from exc
            diagnostics.append({"source": str(candidate), "error": str(exc)})
            continue
        unknown = returned_ids - set(tasks.task_id)
        diagnostics.append({"source": str(candidate), "unmatched_count": len(unknown)})
        if not unknown:
            matches.append((tasks, candidate))
    if not matches:
        raise ValueError(
            "结果中的任务ID无法完整对应本工程的同一批次。请保留原任务ID，并确认工程已关联该批次的计算记录；未对材料进行猜测匹配。"
        )
    # Prefer the current configured export; an explicit source always precedes auto-discovery.
    tasks, selected = matches[0]
    return tasks, selected, diagnostics


def _read_calculation(path: Path) -> tuple[ParsedVaspGap, dict[str, Any]]:
    """Read gap, actual method/settings and calculation geometry from the same XML."""
    try:
        run = Vasprun(
            path,
            parse_dos=False,
            parse_eigen=True,
            parse_projected_eigen=False,
            parse_potcar_file=False,
            exception_on_bad_xml=True,
        )
        parameters = dict(run.parameters)
        if not any(parameters.get(key) is not None for key in ("GGA", "METAGGA", "LHFCALC")):
            raise ValueError("XML缺少可追溯的计算方法参数")
        method_parameters = {key: parameters.get(key) for key in _METHOD_KEYS}
        if parameters.get("LDAU"):
            method_parameters.update(
                {key: parameters.get(key) for key in ("LDAUTYPE", "LDAUL", "LDAUU", "LDAUJ")}
            )
        tag = re.sub(r"[^a-z0-9]+", "", str(parameters.get("METAGGA") or "").lower())
        method = (
            f"vasp-{tag + '-' if tag else ''}{_canonical_sha256(method_parameters)[:16]}-xml-v1"
        )
        metadata = {
            "schema_version": GAP_SCHEMA_VERSION,
            "method": method,
            "calculator": "VASP",
            "backend_version": str(run.vasp_version),
            "method_parameters": method_parameters,
            "parameters": parameters,
            "incar": dict(run.incar),
            "kpoints": run.kpoints.as_dict(),
            "potcar_symbols": list(run.potcar_symbols),
            "scope": "Recorded from vasprun.xml; POTCAR binary hashes are unavailable.",
        }
        metadata = json.loads(json.dumps(metadata, cls=MontyEncoder))
        return _parse_vasprun(path, run=run), {
            "method_metadata": metadata,
            "settings_sha256": _canonical_sha256(metadata),
            "structure_sha256": _structure_sha256(run.initial_structure),
            "formula": run.initial_structure.composition.reduced_formula,
            "initial_structure": run.initial_structure.as_dict(),
            "final_structure": run.final_structure.as_dict(),
        }
    except Exception as exc:
        return ParsedVaspGap(status="failed", error=f"vasprun_parse_error: {exc}"), {}


def collect_vasp_gap_folder(
    *,
    task_sources: tuple[str | Path, ...],
    results_dir: str | Path,
    output_path: str | Path,
    report_path: str | Path | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Only folder input is supplied by the GUI user; task sources come from the project."""
    sources = tuple(Path(path) for path in task_sources)
    root, output = Path(results_dir), Path(output_path)
    report_file = (
        Path(report_path)
        if report_path
        else output.with_name(f"{output.stem}.collection-report.json")
    )
    tasks_file = output.with_name(f"{output.stem}.tasks.csv")
    provenance_file = output.with_name(f"{output.stem}.provenance.json")
    destinations = (output, tasks_file, provenance_file, report_file)
    if len({path.resolve() for path in destinations}) != len(destinations):
        raise ValueError("输出文件路径重叠")
    if any(path.exists() for path in destinations):
        raise FileExistsError("输出位置已有文件，请选择新的输出文件夹")
    if not root.is_dir():
        raise ValueError("VASP结果文件夹不存在")
    children = {
        path.name: path for path in root.iterdir() if path.is_dir() and path.name.startswith("gap-")
    }
    if not children:
        raise ValueError("请选择包含 gap-任务ID 子文件夹的总目录")
    for task_id, directory in children.items():
        if _find_vasprun(directory) is None and any(path.is_dir() for path in directory.iterdir()):
            raise ValueError(
                f"{task_id} 内存在多层目录；请将最终 vasprun.xml[.gz] 直接放在该任务文件夹下"
            )
        if (directory / "vasprun.xml").is_file() and (directory / "vasprun.xml.gz").is_file():
            raise ValueError(f"{task_id} 同时包含两份VASP结果，请只保留本次最终结果")
    tasks, source, diagnostics = _select_source(sources, set(children))
    source_sha = _sha(source)
    rows, bound_tasks, provenance, task_reports = [], [], {}, []
    for _, original in tasks.iterrows():
        source_id = str(original.task_id)
        path = _find_vasprun(root / source_id)
        if path is None:
            parsed, evidence = (
                ParsedVaspGap(status="missing", error="vasprun.xml[.gz] not found"),
                {},
            )
            xml_sha = None
        else:
            xml_sha = _sha(path)
            parsed, evidence = _read_calculation(path)
            if xml_sha != _sha(path):
                raise ValueError(f"读取过程中VASP文件发生变化：{path}")
        task = {
            key: original[key]
            for key in (
                "schema_version",
                "task_id",
                "material_id",
                "formula",
                "method",
                "structure_sha256",
            )
        }
        task.update(
            source_task_id=source_id,
            source_method=str(original.method),
            source_structure_sha256=str(original.structure_sha256),
            settings_sha256="",
        )
        if evidence:
            if not _same_formula(str(original.formula), evidence["formula"]):
                parsed = ParsedVaspGap(status="failed", error="XML元素组成与该任务对应材料不一致")
            else:
                task.update(
                    method=evidence["method_metadata"]["method"],
                    structure_sha256=evidence["structure_sha256"],
                    settings_sha256=evidence["settings_sha256"],
                )
                task["task_id"] = make_gap_task_id(
                    str(task["material_id"]), task["method"], task["structure_sha256"]
                )
        record = _result_record(
            pd.Series(task), parsed, path, settings_sha256=task["settings_sha256"]
        )
        record["source_task_id"] = source_id
        rows.append(record)
        bound_tasks.append(task)
        provenance[source_id] = {
            "vasprun_path": str(path) if path else None,
            "vasprun_sha256": xml_sha,
            **evidence,
        }
        task_reports.append(
            {
                "source_task_id": source_id,
                "task_id": task["task_id"],
                "status": parsed.status,
                "error": parsed.error,
            }
        )
    bound = _load_gap_tasks(pd.DataFrame(bound_tasks))
    results = validate_gap_results(pd.DataFrame(rows), tasks_path=bound)
    validation = results.attrs["validation_report"]
    if validation["rejected_count"]:
        errors = ", ".join(f"{key}={value}" for key, value in validation["error_counts"].items())
        raise ValueError(
            f"收集结果校验拒绝{validation['rejected_count']}条记录：{errors}；未写入结果"
        )
    counts = Counter(results.status)
    report = {
        "schema_version": GAP_SCHEMA_VERSION,
        "mode": "project-folder",
        "collector": "pymatgen.io.vasp.outputs.Vasprun",
        "task_sources": [str(path) for path in sources],
        "selected_source": str(source),
        "source_sha256": source_sha,
        "source_candidates": diagnostics,
        "tasks_path": str(tasks_file),
        "provenance_path": str(provenance_file),
        "results_dir": str(root),
        "output": str(output),
        "selected_task_count": len(tasks),
        "collected_result_count": len(results),
        "validation": validation,
        "status_counts": {
            key: counts.get(key, 0) for key in ("success", "not_converged", "failed", "missing")
        },
        "returned_directory_count": len(children),
        "task_results": task_reports,
        "missing_count": counts.get("missing", 0),
        "missing_task_ids": [row["source_task_id"] for row in rows if row["status"] == "missing"],
        "identity_note": "Source folder IDs remain unchanged. Derived result task IDs record actual XML method and input geometry; source identities are retained.",
    }
    if _sha(source) != source_sha:
        raise ValueError("收集过程中工程导出批次发生变化")
    payloads = [
        results.to_csv(index=False),
        bound.to_csv(index=False),
        json.dumps(provenance, ensure_ascii=False, indent=2, cls=MontyEncoder),
    ]
    report["output_sha256"] = hashlib.sha256(payloads[0].encode("utf-8")).hexdigest()
    report["tasks_sha256"] = hashlib.sha256(payloads[1].encode("utf-8")).hexdigest()
    payloads.append(json.dumps(report, ensure_ascii=False, indent=2))
    created = []
    try:
        for destination, payload in zip(destinations, payloads, strict=True):
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as stream:
                created.append(destination)
                stream.write(payload.encode("utf-8"))
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return results, report
