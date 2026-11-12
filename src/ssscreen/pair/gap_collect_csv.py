"""Import prepared gap CSVs against identities already registered in the project."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from .gap_collect_folder import _select_source, _sha
from .gap_collect_vasp import ParsedVaspGap, _result_record
from .gap_export import GAP_SCHEMA_VERSION, validate_gap_results


def collect_gap_csv(
    *,
    task_sources: tuple[str | Path, ...],
    results_csv: str | Path,
    output_path: str | Path,
    report_path: str | Path | None = None,
    library_method: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Validate before publishing; retain failed calculations and explicit missing tasks."""
    sources = tuple(Path(path) for path in task_sources)
    source_csv, output = Path(results_csv), Path(output_path)
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
    csv_sha = _sha(source_csv)
    raw = pd.read_csv(source_csv, keep_default_na=False, dtype=str)
    if raw.empty:
        raise ValueError("结果CSV没有材料记录")
    if "task_id" not in raw or not raw.task_id.str.strip().all():
        raise ValueError("CSV需保留本软件结果格式中的task_id，不能只提供材料名称和带隙")
    audit = []
    if library_method is not None:
        from .gap_library import match_library

        if len(sources) != 1 or sources[0].suffix.lower() != ".zip":
            raise ValueError("历史库匹配需要当前工程的一个05导出压缩包")
        selected = sources[0]
        task_sha = _sha(selected)
        tasks, matched, audit = match_library(selected, raw, library_method)
        diagnostics = []
        results = validate_gap_results(matched, tasks_path=tasks)
    else:
        tasks, selected, diagnostics = _select_source(sources, set(raw.task_id.str.strip()))
        task_sha = _sha(selected)
        results = validate_gap_results(source_csv, tasks_path=tasks)
    validation = results.attrs["validation_report"]
    if validation["rejected_count"]:
        errors = ", ".join(
            f"{key}={value}" for key, value in validation["error_counts"].items()
        )
        raise ValueError(
            f"CSV校验拒绝{validation['rejected_count']}条记录：{errors}；未写入结果"
        )
    missing = set(validation["missing_task_ids"])
    missing_rows = [
        _result_record(
            task,
            ParsedVaspGap(status="missing", error="结果CSV未包含此任务"),
            None,
            settings_sha256=str(task.get("settings_sha256", "")),
        )
        for _, task in tasks.iterrows()
        if task.task_id in missing
    ]
    if missing_rows:
        results = pd.DataFrame.from_records(
            [*results.to_dict("records"), *missing_rows]
        )
    # A failed calculation must not supply a gap for downstream screening.
    results["is_direct"] = results["is_direct"].astype(object)
    results["transition"] = results["transition"].astype(object)
    results.loc[
        results.status != "success", ["band_gap", "is_direct", "transition"]
    ] = [
        float("nan"),
        None,
        "",
    ]
    counts = results.status.value_counts().to_dict()
    report = {
        "schema_version": GAP_SCHEMA_VERSION,
        "mode": "project-library" if library_method is not None else "project-csv",
        "library_method": library_method,
        "matches": audit,
        "collector": "ssscreen.pair.gap_export.validate_gap_results",
        "task_sources": [str(path) for path in sources],
        "selected_source": str(selected),
        "source_sha256": task_sha,
        "source_candidates": diagnostics,
        "results_csv": str(source_csv),
        "input_sha256": csv_sha,
        "tasks_path": str(tasks_file),
        "provenance_path": str(provenance_file),
        "output": str(output),
        "selected_task_count": len(tasks),
        "collected_result_count": len(results),
        "status_counts": {
            **{key: 0 for key in ("success", "not_converged", "failed", "missing")},
            **{str(key): int(value) for key, value in counts.items()},
        },
        "missing_count": int(counts.get("missing", 0)),
        "missing_task_ids": sorted(missing),
        "validation": validation,
        "identity_note": "Original CSV task identities and methods are preserved; no XML parsing or calculation was performed.",
    }
    provenance = {
        "source_csv": str(source_csv),
        "input_sha256": csv_sha,
        "task_source": str(selected),
        "task_source_sha256": task_sha,
        "scope": "Import of prepared CSV; values and calculation statuses come from the supplied table, not a new XML parse.",
        "non_success_gap_policy": "Non-success band gaps/directness/transitions are cleared; original CSV is unchanged.",
    }
    if csv_sha != _sha(source_csv) or task_sha != _sha(selected):
        raise ValueError("导入过程中输入CSV或工程任务记录发生变化")
    payloads = [
        results.to_csv(index=False),
        tasks.to_csv(index=False),
        json.dumps(provenance, ensure_ascii=False, indent=2),
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
