"""Collect batch VASP band-gap results into the SS-Screen result contract."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from pymatgen.io.vasp.outputs import Vasprun

from .gap_export import GAP_RESULT_COLUMNS, GAP_SCHEMA_VERSION, _load_method_metadata

GAP_TASK_IDENTITY_COLUMNS = {
    "task_id",
    "material_id",
    "formula",
    "method",
    "structure_sha256",
}
VASPRUN_FILENAMES = ("vasprun.xml", "vasprun.xml.gz")


@dataclass(frozen=True)
class ParsedVaspGap:
    """Result fields extracted from one VASP calculation."""

    status: str
    band_gap: float | None = None
    is_direct: bool | None = None
    transition: str = ""
    error: str = ""
    backend_version: str = ""


def _completed_at(path: Path) -> str:
    timestamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return timestamp.isoformat(timespec="seconds").replace("+00:00", "Z")


def _find_vasprun(task_dir: Path) -> Path | None:
    for filename in VASPRUN_FILENAMES:
        candidate = task_dir / filename
        if candidate.is_file():
            return candidate
    return None


def _parse_vasprun(path: Path, *, run: Any = None) -> ParsedVaspGap:
    try:
        run = (
            run
            if run is not None
            else Vasprun(
                path,
                parse_dos=False,
                parse_eigen=True,
                parse_projected_eigen=False,
                parse_potcar_file=False,
                exception_on_bad_xml=False,
            )
        )
    except Exception as exc:
        return ParsedVaspGap(status="failed", error=f"vasprun_parse_error: {exc}")

    version = str(getattr(run, "vasp_version", "") or "")
    if not bool(getattr(run, "converged", False)):
        electronic = bool(getattr(run, "converged_electronic", False))
        ionic = bool(getattr(run, "converged_ionic", False))
        return ParsedVaspGap(
            status="not_converged",
            error=f"VASP not converged (electronic={electronic}, ionic={ionic})",
            backend_version=version,
        )

    try:
        gap, _cbm, _vbm, is_direct = run.eigenvalue_band_properties
        gap = float(gap)
        transition = ""
        try:
            transition = str(run.get_band_structure().get_band_gap().get("transition", ""))
        except Exception:
            pass
    except Exception as exc:
        return ParsedVaspGap(
            status="failed",
            error=f"band_gap_parse_error: {exc}",
            backend_version=version,
        )

    if not pd.notna(gap) or gap < 0:
        return ParsedVaspGap(
            status="failed",
            error=f"invalid parsed band gap: {gap}",
            backend_version=version,
        )
    return ParsedVaspGap(
        status="success",
        band_gap=gap,
        is_direct=bool(is_direct),
        transition=transition,
        backend_version=version,
    )


def _result_record(
    task: pd.Series,
    parsed: ParsedVaspGap,
    vasprun_path: Path | None,
    *,
    settings_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": GAP_SCHEMA_VERSION,
        "task_id": str(task["task_id"]),
        "material_id": str(task["material_id"]),
        "formula": str(task["formula"]),
        "method": str(task["method"]),
        "band_gap": parsed.band_gap,
        "is_direct": parsed.is_direct,
        "transition": parsed.transition,
        "status": parsed.status,
        "error": parsed.error,
        "structure_sha256": str(task["structure_sha256"]),
        "settings_sha256": settings_sha256 or str(task.get("settings_sha256", "") or ""),
        "backend": "VASP",
        "backend_version": parsed.backend_version,
        "completed_at": _completed_at(vasprun_path) if vasprun_path is not None else "",
    }


def collect_vasp_gap_results(
    *,
    tasks_path: str | Path,
    results_dir: str | Path,
    output_path: str | Path,
    report_path: str | Path | None = None,
    method_metadata_path: str | Path | None = None,
    task_ids: tuple[str, ...] = (),
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Collect all selected ``task_id/vasprun.xml`` calculations under a directory."""
    tasks_path = Path(tasks_path)
    results_dir = Path(results_dir)
    output_path = Path(output_path)
    report_path = (
        Path(report_path)
        if report_path is not None
        else output_path.with_name(f"{output_path.stem}.collection-report.json")
    )

    tasks = pd.read_csv(tasks_path, keep_default_na=False)
    missing_columns = sorted(GAP_TASK_IDENTITY_COLUMNS - set(tasks.columns))
    if missing_columns:
        raise ValueError(f"missing required gap-task columns: {', '.join(missing_columns)}")
    if tasks["task_id"].duplicated().any():
        raise ValueError("gap task table contains duplicate task_id values")

    metadata, settings_sha256 = _load_method_metadata(method_metadata_path)
    if metadata is not None:
        metadata_method = str(metadata.get("method", metadata.get("method_id", ""))).strip()
        task_methods = set(tasks["method"].astype(str))
        if task_methods != {metadata_method}:
            raise ValueError(
                "method metadata does not match task methods: "
                f"metadata={metadata_method}, tasks={', '.join(sorted(task_methods))}"
            )
        if "settings_sha256" in tasks:
            expected = set(tasks["settings_sha256"].astype(str)) - {""}
            if expected - {settings_sha256}:
                raise ValueError("method metadata settings do not match the task settings_sha256")

    known_task_ids = set(tasks["task_id"].astype(str))
    requested = list(dict.fromkeys(task_ids))
    unknown = sorted(set(requested) - known_task_ids)
    if unknown:
        raise ValueError(f"unknown task_id selection: {', '.join(unknown)}")
    if requested:
        tasks = tasks[tasks["task_id"].astype(str).isin(requested)].copy()

    records: list[dict[str, Any]] = []
    missing_task_ids: list[str] = []
    task_reports: list[dict[str, Any]] = []
    for _, task in tasks.iterrows():
        task_id = str(task["task_id"])
        vasprun_path = _find_vasprun(results_dir / task_id)
        if vasprun_path is None:
            missing_task_ids.append(task_id)
            parsed = ParsedVaspGap(status="missing", error="vasprun.xml[.gz] not found")
        else:
            parsed = _parse_vasprun(vasprun_path)
        records.append(
            _result_record(
                task,
                parsed,
                vasprun_path,
                settings_sha256=settings_sha256,
            )
        )
        task_reports.append(
            {
                "task_id": task_id,
                "status": parsed.status,
                "vasprun_path": str(vasprun_path) if vasprun_path is not None else None,
                "error": parsed.error or None,
            }
        )

    results = pd.DataFrame(records, columns=GAP_RESULT_COLUMNS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_path, index=False)

    status_counts = Counter(str(record["status"]) for record in records)
    discovered_task_ids = sorted(path.name for path in results_dir.iterdir() if path.is_dir())
    unexpected_task_ids = sorted(set(discovered_task_ids) - known_task_ids)
    report = {
        "schema_version": GAP_SCHEMA_VERSION,
        "collector": "pymatgen.io.vasp.outputs.Vasprun",
        "tasks_path": str(tasks_path),
        "results_dir": str(results_dir),
        "method_metadata_path": (
            str(method_metadata_path) if method_metadata_path is not None else None
        ),
        "settings_sha256": settings_sha256 or None,
        "selected_task_count": int(len(tasks)),
        "collected_result_count": int(len(results)),
        "status_counts": {
            status: status_counts.get(status, 0)
            for status in ("success", "not_converged", "failed", "missing")
        },
        "missing_count": len(missing_task_ids),
        "missing_task_ids": missing_task_ids,
        "discovered_task_ids": discovered_task_ids,
        "unexpected_task_ids": unexpected_task_ids,
        "task_results": task_reports,
        "output": str(output_path),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return results, report
