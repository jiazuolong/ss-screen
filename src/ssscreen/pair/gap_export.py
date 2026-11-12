"""Export external band-gap tasks and validate returned result bundles."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd
from monty.serialization import dumpfn
from pymatgen.core import Composition, Structure

from ..data.io import load_group_df

GAP_SCHEMA_VERSION = 1
GAP_RESULT_REQUIRED_COLUMNS = {
    "material_id",
    "formula",
    "method",
    "band_gap",
    "is_direct",
    "transition",
    "status",
}
GAP_TASK_REQUIRED_COLUMNS = {
    "schema_version",
    "task_id",
    "material_id",
    "formula",
    "method",
    "structure_sha256",
}
GAP_RESULT_COLUMNS = [
    "schema_version",
    "task_id",
    "material_id",
    "formula",
    "method",
    "band_gap",
    "is_direct",
    "transition",
    "status",
    "error",
    "structure_sha256",
    "settings_sha256",
    "backend",
    "backend_version",
    "completed_at",
]
GAP_SUCCESS_STATUSES = frozenset({"success", "completed", "ok"})
GAP_KNOWN_STATUSES = GAP_SUCCESS_STATUSES | frozenset(
    {"failed", "missing", "not_converged", "skipped", "pending", "running", "cancelled"}
)
STRUCTURE_FORMAT_EXTENSIONS = {"json": ".json", "cif": ".cif", "poscar": ".vasp"}
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_TASK_ID_RE = re.compile(r"^gap-[0-9a-f]{24}$")


def _formula(value: Any) -> str:
    if isinstance(value, Composition):
        return value.reduced_formula
    return str(value)


def _calculation_structure(row: pd.Series, structure_col: str) -> Structure:
    structure = row[structure_col]
    if (
        "primitive_structure" in row
        and row["primitive_structure"] is not None
        and not pd.isna(row["primitive_structure"])
    ):
        structure = row["primitive_structure"]
    return structure


def _structure_natoms(row: pd.Series, structure_col: str) -> int:
    return len(_calculation_structure(row, structure_col))


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _structure_sha256(structure: Structure) -> str:
    return _canonical_sha256(structure.as_dict())


def make_gap_task_id(material_id: str, method: str, structure_sha256: str) -> str:
    """Return the deterministic public identifier for an external gap task."""
    digest = _canonical_sha256(
        {
            "schema_version": GAP_SCHEMA_VERSION,
            "material_id": material_id,
            "method": method,
            "structure_sha256": structure_sha256,
        }
    )
    return f"gap-{digest[:24]}"


def _safe_file_stem(value: object) -> str:
    text = str(value)
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in text)
    return safe or "material"


def _normalise_structure_formats(formats: Sequence[str]) -> tuple[str, ...]:
    normalised = tuple(dict.fromkeys(str(fmt).lower() for fmt in formats))
    unknown = sorted(set(normalised) - set(STRUCTURE_FORMAT_EXTENSIONS))
    if unknown:
        raise ValueError(f"unsupported structure format(s): {', '.join(unknown)}")
    return normalised


def _write_structures(
    structure: Structure,
    *,
    material_id: str,
    structure_dir: Path,
    formats: Sequence[str],
) -> dict[str, str]:
    paths: dict[str, str] = {}
    stem = _safe_file_stem(material_id)
    for fmt in formats:
        path = structure_dir / f"{stem}{STRUCTURE_FORMAT_EXTENSIONS[fmt]}"
        if fmt == "json":
            dumpfn(structure, str(path))
        elif fmt == "cif":
            structure.to(filename=str(path), fmt="cif")
        else:
            structure.to(filename=str(path), fmt="poscar")
        paths[fmt] = str(path)
    return paths


def _result_template(tasks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, task in tasks.iterrows():
        rows.append(
            {
                "schema_version": GAP_SCHEMA_VERSION,
                "task_id": task["task_id"],
                "material_id": task["material_id"],
                "formula": task["formula"],
                "method": task["method"],
                "band_gap": "",
                "is_direct": "",
                "transition": "",
                "status": "pending",
                "error": "",
                "structure_sha256": task["structure_sha256"],
                "settings_sha256": "",
                "backend": "",
                "backend_version": "",
                "completed_at": "",
            }
        )
    return pd.DataFrame(rows, columns=GAP_RESULT_COLUMNS)


def _method_metadata_template(method: str) -> dict[str, Any]:
    return {
        "schema_version": GAP_SCHEMA_VERSION,
        "method": method,
        "calculator": "",
        "calculator_version": "",
        "functional": "",
        "soc": None,
        "pseudopotential_family": "",
        "geometry_relaxed": None,
        "kpoint_policy": "",
        "settings": {},
        "notes": "",
    }


def export_gap_candidates(
    groups_path: str | Path,
    dataset_path: str | Path,
    output: str | Path,
    *,
    method: str = "external",
    structure_dir: str | Path | None = None,
    structure_formats: Sequence[str] = ("json",),
    results_template: str | Path | None = None,
    method_metadata_template: str | Path | None = None,
    structure_col: str = "structure",
    max_natoms: int | None = None,
) -> pd.DataFrame:
    """Export unique group members as versioned external calculation tasks."""
    method = str(method).strip()
    if not method:
        raise ValueError("method must be a non-empty identifier")
    formats = _normalise_structure_formats(structure_formats)
    groups = load_group_df(groups_path)
    dataset = pd.read_pickle(dataset_path)
    seen: set[str] = set()
    records: list[dict[str, Any]] = []

    structure_root = Path(structure_dir) if structure_dir is not None else None
    if structure_root is not None:
        structure_root.mkdir(parents=True, exist_ok=True)

    for group_index, group in enumerate(groups):
        for member_index, material_id in enumerate(group.mp_ids):
            material_id = str(material_id)
            if material_id in seen:
                continue
            seen.add(material_id)
            if material_id not in dataset.index:
                continue
            row = dataset.loc[material_id]
            structure = _calculation_structure(row, structure_col)
            natoms = len(structure)
            if max_natoms is not None and natoms > max_natoms:
                continue

            structure_hash = _structure_sha256(structure)
            paths = (
                _write_structures(
                    structure,
                    material_id=material_id,
                    structure_dir=structure_root,
                    formats=formats,
                )
                if structure_root is not None
                else {}
            )
            primary_path = paths.get("json") or next(iter(paths.values()), "")
            composition = row.get("composition", group.compositions[member_index])
            formula = _formula(row.get("formula", group.compositions[member_index]))
            records.append(
                {
                    "schema_version": GAP_SCHEMA_VERSION,
                    "task_id": make_gap_task_id(material_id, method, structure_hash),
                    "method": method,
                    "source_group_index": group_index,
                    "source_member_index": member_index,
                    "material_id": material_id,
                    "formula": formula,
                    "composition": _formula(composition),
                    "initial_band_gap": row.get("band_gap", ""),
                    "e_hull": row.get("e_hull", row.get("energy_above_hull", "")),
                    "natoms": natoms,
                    "structure_sha256": structure_hash,
                    "structure_path": primary_path,
                    "structure_json_path": paths.get("json", ""),
                    "structure_cif_path": paths.get("cif", ""),
                    "structure_poscar_path": paths.get("poscar", ""),
                }
            )

    columns = [
        "schema_version",
        "task_id",
        "method",
        "source_group_index",
        "source_member_index",
        "material_id",
        "formula",
        "composition",
        "initial_band_gap",
        "e_hull",
        "natoms",
        "structure_sha256",
        "structure_path",
        "structure_json_path",
        "structure_cif_path",
        "structure_poscar_path",
    ]
    frame = pd.DataFrame.from_records(records, columns=columns)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)

    if results_template is not None:
        results_template = Path(results_template)
        results_template.parent.mkdir(parents=True, exist_ok=True)
        _result_template(frame).to_csv(results_template, index=False)
    if method_metadata_template is not None:
        method_metadata_template = Path(method_metadata_template)
        method_metadata_template.parent.mkdir(parents=True, exist_ok=True)
        method_metadata_template.write_text(
            json.dumps(_method_metadata_template(method), indent=2, sort_keys=True) + "\n"
        )
    return frame


def _read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".json":
        return pd.read_json(path)
    return pd.read_csv(path)


def _text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _schema_version(value: Any) -> int | None:
    text = _text(value)
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if not math.isfinite(number) or not number.is_integer():
        return None
    return int(number)


def _normalise_directness(value: Any) -> tuple[Any, bool]:
    if value is None or pd.isna(value):
        return pd.NA, True
    if isinstance(value, bool):
        return value, True
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value), True
    text = str(value).strip().lower()
    if text in {"true", "t", "1", "yes", "y", "direct"}:
        return True, True
    if text in {"false", "f", "0", "no", "n", "indirect"}:
        return False, True
    if text in {"", "unknown", "na", "n/a", "none", "null"}:
        return pd.NA, True
    return pd.NA, False


def _same_formula(left: str, right: str) -> bool:
    try:
        return Composition(left).reduced_composition == Composition(right).reduced_composition
    except Exception:
        return left == right


def _load_method_metadata(path: str | Path | None) -> tuple[dict[str, Any] | None, str]:
    if path is None:
        return None, ""
    path = Path(path)
    try:
        metadata = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"cannot read method metadata JSON {path}: {exc}") from exc
    if not isinstance(metadata, dict):
        raise ValueError("method metadata must be a JSON object")
    version = metadata.get("schema_version", GAP_SCHEMA_VERSION)
    if version != GAP_SCHEMA_VERSION:
        raise ValueError(f"unsupported method-metadata schema_version: {version}")
    method = _text(metadata.get("method", metadata.get("method_id")))
    if not method:
        raise ValueError("method metadata must define a non-empty 'method'")
    canonical = {
        key: value for key, value in metadata.items() if key not in {"settings_sha256", "notes"}
    }
    return metadata, _canonical_sha256(canonical)


def _load_gap_tasks(path: str | Path | pd.DataFrame) -> pd.DataFrame:
    tasks = path.copy() if isinstance(path, pd.DataFrame) else _read_table(path).copy()
    missing = sorted(GAP_TASK_REQUIRED_COLUMNS - set(tasks.columns))
    if missing:
        raise ValueError(f"missing required gap-task columns: {', '.join(missing)}")
    identity_columns = ("task_id", "material_id", "formula", "method", "structure_sha256")
    for column in identity_columns:
        tasks[column] = tasks[column].map(_text)

    task_errors: list[str] = []
    for row_number, (_, task) in enumerate(tasks.iterrows(), start=1):
        errors: list[str] = []
        if _schema_version(task["schema_version"]) != GAP_SCHEMA_VERSION:
            errors.append("unsupported_schema_version")
        for field in ("task_id", "material_id", "formula", "method", "structure_sha256"):
            if not task[field]:
                errors.append(f"missing_{field}")
        if task["task_id"] and not _TASK_ID_RE.fullmatch(task["task_id"]):
            errors.append("invalid_task_id")
        if task["structure_sha256"] and not _HASH_RE.fullmatch(task["structure_sha256"]):
            errors.append("invalid_structure_sha256")
        if not errors:
            expected_id = make_gap_task_id(
                task["material_id"], task["method"], task["structure_sha256"]
            )
            if task["task_id"] != expected_id:
                errors.append("task_identity_mismatch")
        if errors:
            task_errors.append(f"row {row_number} ({';'.join(errors)})")
    if task_errors:
        raise ValueError("invalid gap-task rows: " + ", ".join(task_errors))

    duplicated_tasks = tasks["task_id"].duplicated(keep=False)
    if duplicated_tasks.any():
        duplicate_ids = sorted(tasks.loc[duplicated_tasks, "task_id"].unique())
        raise ValueError("duplicate task_id values in gap tasks: " + ", ".join(duplicate_ids))
    return tasks


def _normalise_result_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    aliases = {
        "band_gap_eV": "band_gap",
        "method_id": "method",
        "direct": "is_direct",
    }
    for source, target in aliases.items():
        if target not in frame.columns and source in frame.columns:
            frame[target] = frame[source]
    missing = sorted(GAP_RESULT_REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"missing required gap-result columns: {', '.join(missing)}")
    for column in GAP_RESULT_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    return frame


def _write_validation_outputs(
    *,
    accepted: pd.DataFrame,
    rejected: pd.DataFrame,
    report: dict[str, Any],
    output_path: str | Path | None,
    rejected_path: str | Path | None,
    report_path: str | Path | None,
) -> None:
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        accepted.to_csv(path, index=False)
    if rejected_path is not None:
        path = Path(rejected_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        rejected.to_csv(path, index=False)
    if report_path is not None:
        path = Path(report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def validate_gap_results(
    path: str | Path | pd.DataFrame,
    *,
    tasks_path: str | Path | pd.DataFrame | None = None,
    method_metadata_path: str | Path | None = None,
    output_path: str | Path | None = None,
    rejected_path: str | Path | None = None,
    report_path: str | Path | None = None,
) -> pd.DataFrame:
    """Validate external results, optionally against exported tasks and method metadata.

    The legacy seven-column result table remains accepted when ``tasks_path`` is
    omitted. Supplying tasks enables strict task identity and structure checks.
    Rejected rows are excluded from the returned normalized frame and summarized
    in ``frame.attrs['validation_report']``.
    """
    raw = _normalise_result_columns(
        path.copy() if isinstance(path, pd.DataFrame) else _read_table(path)
    )
    metadata, metadata_hash = _load_method_metadata(method_metadata_path)
    metadata_method = (
        _text(metadata.get("method", metadata.get("method_id"))) if metadata is not None else ""
    )

    tasks: pd.DataFrame | None = None
    task_lookup: dict[str, pd.Series] = {}
    expected_task_ids: set[str] = set()
    if tasks_path is not None:
        tasks = _load_gap_tasks(tasks_path)
        task_lookup = {str(row["task_id"]): row for _, row in tasks.iterrows()}
        expected_task_ids = set(task_lookup)

    duplicate_keys = []
    for _, row in raw.iterrows():
        task_id = _text(row.get("task_id"))
        duplicate_keys.append(
            task_id or f"{_text(row.get('material_id'))}|{_text(row.get('method'))}"
        )
    duplicate_mask = pd.Series(duplicate_keys).duplicated(keep=False).tolist()

    accepted_records: list[dict[str, Any]] = []
    rejected_records: list[dict[str, Any]] = []
    received_task_ids: set[str] = set()
    accepted_task_ids: set[str] = set()
    error_counts: Counter[str] = Counter()

    for row_number, (_, source_row) in enumerate(raw.iterrows(), start=1):
        record = source_row.to_dict()
        errors: list[str] = []
        for column in (
            "task_id",
            "material_id",
            "formula",
            "method",
            "transition",
            "status",
            "error",
            "structure_sha256",
            "settings_sha256",
            "backend",
            "backend_version",
            "completed_at",
        ):
            record[column] = _text(record.get(column))

        version_text = _text(record.get("schema_version"))
        if not version_text:
            record["schema_version"] = GAP_SCHEMA_VERSION
        else:
            parsed_version = _schema_version(version_text)
            record["schema_version"] = (
                parsed_version if parsed_version is not None else version_text
            )
            if record["schema_version"] != GAP_SCHEMA_VERSION:
                errors.append("unsupported_schema_version")

        status = record["status"].lower()
        if status in GAP_SUCCESS_STATUSES:
            status = "success"
        record["status"] = status
        if not status or status not in GAP_KNOWN_STATUSES:
            errors.append("invalid_status")

        for field in ("material_id", "formula", "method"):
            if not record[field]:
                errors.append(f"missing_{field}")

        gap = pd.to_numeric(pd.Series([record.get("band_gap")]), errors="coerce").iloc[0]
        record["band_gap"] = gap
        if status == "success" and (pd.isna(gap) or not math.isfinite(float(gap)) or gap < 0):
            errors.append("invalid_band_gap")
        elif not pd.isna(gap) and (not math.isfinite(float(gap)) or gap < 0):
            errors.append("invalid_band_gap")

        directness, directness_valid = _normalise_directness(record.get("is_direct"))
        record["is_direct"] = directness
        if not directness_valid:
            errors.append("invalid_is_direct")

        if duplicate_mask[row_number - 1]:
            errors.append("duplicate_result")

        task_id = record["task_id"]
        if task_id and not _TASK_ID_RE.fullmatch(task_id):
            errors.append("invalid_task_id")
        if tasks is not None:
            if not task_id:
                errors.append("missing_task_id")
            elif task_id not in task_lookup:
                errors.append("unknown_task_id")
            else:
                received_task_ids.add(task_id)
                task = task_lookup[task_id]
                if record["material_id"] != task["material_id"]:
                    errors.append("material_id_mismatch")
                if record["method"] != task["method"]:
                    errors.append("method_mismatch")
                if not _same_formula(record["formula"], task["formula"]):
                    errors.append("formula_mismatch")
                expected_structure_hash = task["structure_sha256"]
                if record["structure_sha256"]:
                    if record["structure_sha256"] != expected_structure_hash:
                        errors.append("structure_sha256_mismatch")
                else:
                    errors.append("missing_structure_sha256")
                task_settings_hash = _text(task.get("settings_sha256"))
                if (
                    task_settings_hash
                    and record["settings_sha256"]
                    and record["settings_sha256"] != task_settings_hash
                ):
                    errors.append("settings_sha256_mismatch")

        for field in ("structure_sha256", "settings_sha256"):
            if record[field] and not _HASH_RE.fullmatch(record[field]):
                errors.append(f"invalid_{field}")

        if metadata is not None:
            if record["method"] != metadata_method:
                errors.append("method_metadata_mismatch")
            if record["settings_sha256"] and record["settings_sha256"] != metadata_hash:
                errors.append("settings_sha256_mismatch")
            else:
                record["settings_sha256"] = metadata_hash

        errors = list(dict.fromkeys(errors))
        if errors:
            for error in errors:
                error_counts[error] += 1
            record["validation_errors"] = ";".join(errors)
            record["source_row"] = row_number
            rejected_records.append(record)
        else:
            accepted_records.append(record)
            if task_id:
                accepted_task_ids.add(task_id)

    ordered_columns = GAP_RESULT_COLUMNS + [
        column for column in raw.columns if column not in GAP_RESULT_COLUMNS
    ]
    accepted = pd.DataFrame(accepted_records)
    if accepted.empty:
        accepted = pd.DataFrame(columns=ordered_columns)
    else:
        accepted = accepted[[column for column in ordered_columns if column in accepted.columns]]
    rejected_columns = list(dict.fromkeys(ordered_columns + ["validation_errors", "source_row"]))
    rejected = pd.DataFrame(rejected_records)
    if rejected.empty:
        rejected = pd.DataFrame(columns=rejected_columns)
    else:
        rejected = rejected[[column for column in rejected_columns if column in rejected.columns]]

    report = {
        "schema_version": GAP_SCHEMA_VERSION,
        "results_file": str(path) if isinstance(path, (str, Path)) else None,
        "tasks_file": str(tasks_path) if isinstance(tasks_path, (str, Path)) else None,
        "method_metadata_file": (
            str(method_metadata_path) if method_metadata_path is not None else None
        ),
        "method_metadata_sha256": metadata_hash or None,
        "input_count": int(len(raw)),
        "accepted_count": int(len(accepted)),
        "rejected_count": int(len(rejected)),
        "error_counts": dict(sorted(error_counts.items())),
        "accepted_status_counts": {
            str(key): int(value) for key, value in accepted["status"].value_counts().items()
        },
        "methods": sorted(str(value) for value in accepted["method"].dropna().unique()),
        "expected_task_count": len(expected_task_ids) if tasks is not None else None,
        "missing_task_ids": (
            sorted(expected_task_ids - received_task_ids) if tasks is not None else []
        ),
        "unaccepted_task_ids": (
            sorted(expected_task_ids - accepted_task_ids) if tasks is not None else []
        ),
    }
    accepted.attrs["validation_report"] = report
    _write_validation_outputs(
        accepted=accepted,
        rejected=rejected,
        report=report,
        output_path=output_path,
        rejected_path=rejected_path,
        report_path=report_path,
    )
    return accepted
