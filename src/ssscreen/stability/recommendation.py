"""Auditable Stage 11 recommendations from Stage 5 and Stage 8--10 evidence."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import RecommendationSettings

RECOMMENDATION_SCHEMA_VERSION = 1
CLASSIFICATION_ORDER = {"promising": 0, "uncertain": 1, "low-priority": 2}
EVIDENCE_LEVEL_LABELS = {
    "L2": "structure-matched pair",
    "L3": "high-fidelity endpoint gaps",
    "L4": "SQS/MLP mixing evidence",
    "L5": "phonon and competing-phase evidence",
    "L6": "defect evidence",
}
REQUIRED_PAIR_COLUMNS = ("comp_a", "comp_b", "mp_id_a", "mp_id_b")
REQUIRED_GAP_COLUMNS = ("material_id", "method", "band_gap", "is_direct", "status")
REQUIRED_MIXING_COLUMNS = (
    "pair_index",
    "sqs_structure_id",
    "mixing_enthalpy_meV_per_atom",
    "status",
    "usable_for_screening",
)
REQUIRED_PHONON_COLUMNS = (
    "pair_index",
    "structure_id",
    "status",
    "dynamical_status",
)
REQUIRED_PHASE_COLUMNS = (
    "pair_index",
    "structure_id",
    "energy_above_hull_eV_per_atom",
    "hull_signal",
    "status",
    "usable_for_screening",
)
REQUIRED_DEFECT_COLUMNS = ("pair_index", "status", "defect_signal")
OUTPUT_COLUMNS = [
    "schema_version",
    "recommendation_id",
    "rank",
    "classification",
    "evidence_level",
    "evidence_level_label",
    "pair_index",
    "source_group_index",
    "structure_id",
    "target_fraction_b",
    "actual_fraction_b",
    "fraction_basis",
    "mp_id_a",
    "mp_id_b",
    "comp_a",
    "comp_b",
    "gap_method",
    "gap_a_eV",
    "gap_b_eV",
    "gap_direct_a",
    "gap_direct_b",
    "gap_evidence_status",
    "mixing_status",
    "mixing_enthalpy_meV_per_atom",
    "mixing_signal",
    "phonon_status",
    "dynamical_status",
    "minimum_mesh_frequency_THz",
    "phonon_nac_applied",
    "phase_status",
    "hull_signal",
    "energy_above_hull_eV_per_atom",
    "competing_set_complete",
    "mp_source_backend",
    "mp_source_scope",
    "defect_status",
    "defect_signal",
    "defect_record_count",
    "model_sha256",
    "model_compatibility_status",
    "positive_evidence_count",
    "risk_count",
    "missing_data_count",
    "positive_evidence",
    "risks",
    "missing_data",
    "source_warnings",
    "recommended_next_steps",
    "rationale",
]


@dataclass
class _Assessment:
    positive: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    uncertain: list[str] = field(default_factory=list)
    hard_negative: list[str] = field(default_factory=list)
    source_warnings: list[str] = field(default_factory=list)
    model_sha256_values: set[str] = field(default_factory=set)

    def add_positive(self, code: str) -> None:
        _append_unique(self.positive, code)

    def add_risk(self, code: str, *, uncertain: bool = False, hard: bool = False) -> None:
        _append_unique(self.risks, code)
        if uncertain:
            _append_unique(self.uncertain, code)
        if hard:
            _append_unique(self.hard_negative, code)

    def add_missing(self, code: str, *, required: bool = True) -> None:
        _append_unique(self.missing, code)
        if required:
            _append_unique(self.uncertain, code)

    def add_warning(self, stage: str, value: object) -> None:
        text = _clean_text(value)
        if text:
            _append_unique(self.source_warnings, f"{stage}: {text}")

    def add_model(self, value: object) -> None:
        text = _clean_text(value)
        if text:
            self.model_sha256_values.add(text)


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _atomic_write_dataframe(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.stem}.", suffix=path.suffix or ".csv", dir=path.parent
    )
    os.close(descriptor)
    try:
        frame.to_csv(temporary, index=False)
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text or None


def _finite_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _as_bool(value: object) -> bool | None:
    if value is None:
        return None
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "t", "yes", "y", "1"}:
        return True
    if text in {"false", "f", "no", "n", "0"}:
        return False
    return None


def _json_list(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=True)


def _load_csv(path: Path, *, label: str, required: tuple[str, ...]) -> pd.DataFrame:
    frame = pd.read_csv(path)
    unnamed = [column for column in frame.columns if str(column).startswith("Unnamed:")]
    if unnamed:
        frame = frame.drop(columns=unnamed)
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {', '.join(missing)}")
    return frame


def _prepare_pair_index(frame: pd.DataFrame, *, label: str, pair_count: int) -> pd.DataFrame:
    prepared = frame.copy()
    prepared["__pair_index"] = pd.Series(pd.NA, index=prepared.index, dtype="Int64")
    present = prepared["pair_index"].notna()
    if not present.any():
        return prepared
    numeric = pd.to_numeric(prepared.loc[present, "pair_index"], errors="coerce")
    if numeric.isna().any() or any(float(value) != int(value) for value in numeric):
        raise ValueError(f"{label} contains a non-integer pair_index")
    indices = numeric.astype(int)
    invalid = sorted({int(value) for value in indices if value < 0 or value >= pair_count})
    if invalid:
        raise ValueError(f"{label} contains out-of-range pair_index values: {invalid}")
    prepared.loc[present, "__pair_index"] = indices.to_numpy()
    return prepared


def _validate_settings(settings: RecommendationSettings) -> None:
    values = {
        "promising mixing threshold": settings.promising_max_mixing_enthalpy_mev_per_atom,
        "low-priority mixing threshold": settings.low_priority_mixing_enthalpy_mev_per_atom,
        "promising hull threshold": settings.promising_max_hull_ev_per_atom,
        "low-priority hull threshold": settings.low_priority_hull_ev_per_atom,
        "gap consistency tolerance": settings.gap_consistency_tolerance_ev,
    }
    invalid = [name for name, value in values.items() if value < 0 or not math.isfinite(value)]
    if invalid:
        raise ValueError(f"recommendation settings must be finite and non-negative: {invalid}")
    if (
        settings.promising_max_mixing_enthalpy_mev_per_atom
        > settings.low_priority_mixing_enthalpy_mev_per_atom
    ):
        raise ValueError("promising mixing threshold cannot exceed the low-priority threshold")
    if settings.promising_max_hull_ev_per_atom > settings.low_priority_hull_ev_per_atom:
        raise ValueError("promising hull threshold cannot exceed the low-priority threshold")


def _rows_for_pair_and_structure(
    frame: pd.DataFrame,
    *,
    pair_index: int,
    structure_column: str,
    structure_id: str | None,
) -> pd.DataFrame:
    rows = frame.loc[frame["__pair_index"] == pair_index]
    if structure_column not in rows.columns:
        return rows if structure_id is None else rows.iloc[0:0]
    normalized = rows[structure_column].map(_clean_text)
    if structure_id is None:
        return rows.loc[normalized.isna()]
    return rows.loc[normalized == structure_id]


def _single_row(
    rows: pd.DataFrame,
    *,
    stage: str,
    assessment: _Assessment,
) -> tuple[pd.Series | None, str]:
    if rows.empty:
        assessment.add_missing(f"{stage}:missing_source")
        return None, "missing_source"
    if len(rows) != 1:
        assessment.add_risk(f"{stage}:ambiguous_records", uncertain=True)
        return None, "incompatible"
    return rows.iloc[0], "available"


def _recommendation_id(pair_index: int, structure_id: str | None, pair: pd.Series) -> str:
    payload = {
        "pair_index": pair_index,
        "structure_id": structure_id,
        "mp_id_a": _clean_text(pair.get("mp_id_a")),
        "mp_id_b": _clean_text(pair.get("mp_id_b")),
        "gap_method": _clean_text(pair.get("gap_method")),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return f"recommendation-{digest[:20]}"


def _evaluate_gap_evidence(
    pair: pd.Series,
    gaps: pd.DataFrame,
    *,
    method_override: str | None,
    settings: RecommendationSettings,
    assessment: _Assessment,
) -> dict[str, Any]:
    pair_method = _clean_text(pair.get("gap_method"))
    method = _clean_text(method_override) or pair_method
    if method_override and pair_method and method_override != pair_method:
        assessment.add_risk("gap:pair_method_conflict", uncertain=True)
        return {
            "gap_method": method_override,
            "gap_evidence_status": "incompatible",
            "gap_a_eV": _finite_float(pair.get("gap_a")),
            "gap_b_eV": _finite_float(pair.get("gap_b")),
            "gap_direct_a": _as_bool(pair.get("gap_direct_a")),
            "gap_direct_b": _as_bool(pair.get("gap_direct_b")),
            "complete": False,
        }

    endpoint_ids = [_clean_text(pair.get("mp_id_a")), _clean_text(pair.get("mp_id_b"))]
    if method is None:
        endpoint_rows = gaps.loc[gaps["material_id"].astype(str).isin(endpoint_ids)]
        methods = sorted(
            {text for value in endpoint_rows["method"] if (text := _clean_text(value))}
        )
        if len(methods) == 1:
            method = methods[0]
        else:
            code = "gap:missing_method" if not methods else "gap:ambiguous_method"
            (
                assessment.add_missing(code)
                if not methods
                else assessment.add_risk(code, uncertain=True)
            )
            return {
                "gap_method": None,
                "gap_evidence_status": "missing_source" if not methods else "incompatible",
                "gap_a_eV": _finite_float(pair.get("gap_a")),
                "gap_b_eV": _finite_float(pair.get("gap_b")),
                "gap_direct_a": _as_bool(pair.get("gap_direct_a")),
                "gap_direct_b": _as_bool(pair.get("gap_direct_b")),
                "complete": False,
            }

    mixed_sources = method == "mixed_sources"
    if mixed_sources:
        # Pair generation explicitly records the authorized source for each endmember.
        # Source coverage does not establish equivalence of the two methods.
        assessment.add_risk("gap:mixed_sources", uncertain=True)
    result: dict[str, Any] = {"gap_method": method, "complete": True}
    result_status = "complete"
    direct_values: list[bool | None] = []
    for endpoint, material_id in zip(("a", "b"), endpoint_ids, strict=True):
        endpoint_method = (
            _clean_text(pair.get(f"gap_method_{endpoint}")) if mixed_sources else method
        )
        selected = gaps.loc[gaps["method"].astype(str) == endpoint_method]
        rows = selected.loc[selected["material_id"].astype(str) == str(material_id)]
        if rows.empty:
            assessment.add_missing(f"gap:{endpoint}:missing_source")
            result["complete"] = False
            result_status = "missing_source"
            result[f"gap_{endpoint}_eV"] = _finite_float(pair.get(f"gap_{endpoint}"))
            direct = _as_bool(pair.get(f"gap_direct_{endpoint}"))
            result[f"gap_direct_{endpoint}"] = direct
            direct_values.append(direct)
            continue
        if len(rows) != 1:
            assessment.add_risk(f"gap:{endpoint}:ambiguous_records", uncertain=True)
            result["complete"] = False
            result_status = "incompatible"
            result[f"gap_{endpoint}_eV"] = _finite_float(pair.get(f"gap_{endpoint}"))
            direct = _as_bool(pair.get(f"gap_direct_{endpoint}"))
            result[f"gap_direct_{endpoint}"] = direct
            direct_values.append(direct)
            continue

        row = rows.iloc[0]
        source_status = (_clean_text(row.get("status")) or "missing").lower()
        gap = _finite_float(row.get("band_gap"))
        direct = _as_bool(row.get("is_direct"))
        result[f"gap_{endpoint}_eV"] = gap
        result[f"gap_direct_{endpoint}"] = direct
        direct_values.append(direct)
        if source_status != "success" or gap is None or gap < 0:
            assessment.add_missing(f"gap:{endpoint}:{source_status}")
            result["complete"] = False
            result_status = "failed"
            continue

        pair_gap = _finite_float(pair.get(f"gap_{endpoint}"))
        if pair_gap is not None and abs(pair_gap - gap) > settings.gap_consistency_tolerance_ev:
            assessment.add_risk(f"gap:{endpoint}:value_mismatch", uncertain=True)
            result["complete"] = False
            result_status = "incompatible"
        pair_direct = _as_bool(pair.get(f"gap_direct_{endpoint}"))
        if pair_direct is not None and direct is not None and pair_direct != direct:
            assessment.add_risk(f"gap:{endpoint}:directness_mismatch", uncertain=True)
            result["complete"] = False
            result_status = "incompatible"

    result["gap_evidence_status"] = result_status
    if result["complete"]:
        assessment.add_positive(f"gap:endpoints_verified:{method}")
    if direct_values == [False, False]:
        assessment.add_risk("gap:both_endmembers_indirect")
    return result


def _evaluate_mixing(
    rows: pd.DataFrame,
    *,
    settings: RecommendationSettings,
    assessment: _Assessment,
) -> dict[str, Any]:
    row, availability = _single_row(rows, stage="mixing", assessment=assessment)
    result = {
        "mixing_status": availability,
        "mixing_enthalpy_meV_per_atom": None,
        "mixing_signal": None,
        "complete": False,
        "target_fraction_b": None,
        "actual_fraction_b": None,
        "fraction_basis": None,
    }
    if row is None:
        return result
    assessment.add_model(row.get("model_sha256"))
    assessment.add_warning("mixing", row.get("warnings"))
    status = (_clean_text(row.get("status")) or "missing").lower()
    usable = _as_bool(row.get("usable_for_screening"))
    value = _finite_float(row.get("mixing_enthalpy_meV_per_atom"))
    result.update(
        {
            "mixing_status": status,
            "mixing_enthalpy_meV_per_atom": value,
            "mixing_signal": _clean_text(row.get("mixing_signal")),
            "target_fraction_b": _finite_float(row.get("target_fraction_b")),
            "actual_fraction_b": _finite_float(row.get("actual_fraction_b")),
            "fraction_basis": _clean_text(row.get("fraction_basis")),
        }
    )
    if status != "success" or usable is not True or value is None:
        assessment.add_missing(f"mixing:{status}")
        return result
    result["complete"] = True
    if value > settings.low_priority_mixing_enthalpy_mev_per_atom:
        assessment.add_risk("mixing:above_low_priority_threshold", hard=True)
    elif value > settings.promising_max_mixing_enthalpy_mev_per_atom:
        assessment.add_risk("mixing:borderline", uncertain=True)
    else:
        assessment.add_positive("mixing:within_promising_threshold")
    return result


def _evaluate_phonon(rows: pd.DataFrame, *, assessment: _Assessment) -> dict[str, Any]:
    row, availability = _single_row(rows, stage="phonon", assessment=assessment)
    result = {
        "phonon_status": availability,
        "dynamical_status": None,
        "minimum_mesh_frequency_THz": None,
        "phonon_nac_applied": None,
        "complete": False,
    }
    if row is None:
        return result
    assessment.add_model(row.get("model_sha256"))
    assessment.add_warning("phonon", row.get("warnings"))
    status = (_clean_text(row.get("status")) or "missing").lower()
    dynamical = (_clean_text(row.get("dynamical_status")) or "missing").lower()
    nac_applied = _as_bool(row.get("nac_applied"))
    result.update(
        {
            "phonon_status": status,
            "dynamical_status": dynamical,
            "minimum_mesh_frequency_THz": _finite_float(row.get("minimum_mesh_frequency_THz")),
            "phonon_nac_applied": nac_applied,
        }
    )
    if status != "success":
        assessment.add_missing(f"phonon:{status}")
        return result
    if dynamical == "unstable":
        result["complete"] = True
        assessment.add_risk("phonon:unstable", hard=True)
    elif dynamical == "stable":
        result["complete"] = True
        assessment.add_positive("phonon:no_significant_imaginary_modes")
    else:
        assessment.add_risk(f"phonon:{dynamical}", uncertain=True)
    if nac_applied is False:
        assessment.add_risk("phonon:nac_not_applied")
    return result


def _evaluate_phase(
    rows: pd.DataFrame,
    *,
    settings: RecommendationSettings,
    assessment: _Assessment,
) -> dict[str, Any]:
    row, availability = _single_row(rows, stage="phase", assessment=assessment)
    result = {
        "phase_status": availability,
        "hull_signal": None,
        "energy_above_hull_eV_per_atom": None,
        "competing_set_complete": None,
        "mp_source_backend": None,
        "mp_source_scope": None,
        "complete": False,
    }
    if row is None:
        return result
    assessment.add_model(row.get("model_sha256"))
    assessment.add_warning("phase", row.get("warnings"))
    status = (_clean_text(row.get("status")) or "missing").lower()
    signal = (_clean_text(row.get("hull_signal")) or "missing").lower()
    usable = _as_bool(row.get("usable_for_screening"))
    complete = _as_bool(row.get("competing_set_complete"))
    value = _finite_float(row.get("energy_above_hull_eV_per_atom"))
    backend = _clean_text(row.get("mp_source_backend"))
    scope = _clean_text(row.get("mp_source_scope"))
    result.update(
        {
            "phase_status": status,
            "hull_signal": signal,
            "energy_above_hull_eV_per_atom": value,
            "competing_set_complete": complete,
            "mp_source_backend": backend,
            "mp_source_scope": scope,
        }
    )
    if status != "success" or usable is not True or complete is not True or value is None:
        code = "phase:incomplete_competing_set" if complete is False else f"phase:{status}"
        assessment.add_missing(code)
        return result
    result["complete"] = True
    if signal == "unstable" or value > settings.low_priority_hull_ev_per_atom:
        assessment.add_risk("phase:above_low_priority_threshold", hard=True)
    elif value > settings.promising_max_hull_ev_per_atom:
        assessment.add_risk("phase:borderline", uncertain=True)
    else:
        assessment.add_positive("phase:within_promising_threshold")
    if backend == "offline" or scope == "offline_summary_snapshot":
        assessment.add_risk("phase:offline_snapshot_scope")
    return result


def _evaluate_defects(
    defects: pd.DataFrame | None,
    *,
    pair_index: int,
    structure_id: str | None,
    require_defects: bool,
    assessment: _Assessment,
) -> dict[str, Any]:
    result = {"defect_status": "not_requested", "defect_signal": None, "record_count": 0}
    if defects is None:
        assessment.add_missing("defects:not_requested", required=require_defects)
        return result

    pair_rows = defects.loc[defects["__pair_index"] == pair_index]
    if "structure_id" in pair_rows.columns:
        normalized = pair_rows["structure_id"].map(_clean_text)
        exact = (
            pair_rows.loc[normalized == structure_id]
            if structure_id
            else pair_rows.loc[normalized.isna()]
        )
        rows = exact if not exact.empty else pair_rows.loc[normalized.isna()]
    else:
        rows = pair_rows
    if rows.empty:
        assessment.add_missing("defects:missing_source", required=require_defects)
        result["defect_status"] = "missing_source"
        return result

    result["record_count"] = int(len(rows))
    statuses = {(_clean_text(value) or "missing").lower() for value in rows["status"]}
    signals = {(_clean_text(value) or "missing").lower() for value in rows["defect_signal"]}
    if statuses != {"success"}:
        assessment.add_missing("defects:failed_or_incomplete", required=require_defects)
        result["defect_status"] = "failed"
        result["defect_signal"] = ";".join(sorted(signals))
        return result

    allowed = {"favorable", "neutral", "low_risk", "risky", "uncertain"}
    unknown = signals - allowed
    if unknown:
        assessment.add_risk("defects:unknown_signal", uncertain=True)
        result["defect_status"] = "incompatible"
    else:
        result["defect_status"] = "complete"
    result["defect_signal"] = ";".join(sorted(signals))
    if "risky" in signals:
        assessment.add_risk("defects:risky", hard=True)
    elif "uncertain" in signals:
        assessment.add_risk("defects:uncertain", uncertain=True)
    elif not unknown:
        assessment.add_positive("defects:no_high-risk_signal")
    return result


def _candidate_structure_ids(
    pair_index: int,
    mixing: pd.DataFrame,
    phonons: pd.DataFrame,
    phases: pd.DataFrame,
    defects: pd.DataFrame | None,
) -> list[str | None]:
    values: set[str] = set()
    for frame, column in (
        (mixing, "sqs_structure_id"),
        (phonons, "structure_id"),
        (phases, "structure_id"),
    ):
        rows = frame.loc[frame["__pair_index"] == pair_index]
        values.update(text for value in rows[column] if (text := _clean_text(value)))
    if defects is not None and "structure_id" in defects.columns:
        rows = defects.loc[defects["__pair_index"] == pair_index]
        values.update(text for value in rows["structure_id"] if (text := _clean_text(value)))
    return sorted(values) if values else [None]


def _recommended_steps(
    classification: str,
    assessment: _Assessment,
    *,
    require_defects: bool,
) -> list[str]:
    steps: list[str] = []
    incomplete = [*assessment.missing]
    incompatible = [
        code
        for code in assessment.uncertain
        if any(token in code for token in ("mismatch", "ambiguous", "conflict", "unknown"))
    ]
    if any(code.startswith("gap:") for code in [*incomplete, *incompatible]):
        _append_unique(steps, "complete_or_revalidate_high_fidelity_endpoint_gaps")
    if any(code.startswith("mixing:") for code in [*incomplete, *incompatible]):
        _append_unique(steps, "run_compatible_sqs_relaxation_and_mixing_enthalpy")
    if any(code.startswith("phonon:") for code in [*incomplete, *incompatible]):
        _append_unique(steps, "run_converged_phonon_screening")
    if any(code.startswith("phase:") for code in [*incomplete, *incompatible]):
        _append_unique(steps, "complete_same_mlip_competing_phase_hull")
    if (
        any(code.startswith("defects:") for code in [*incomplete, *incompatible])
        and require_defects
    ):
        _append_unique(steps, "complete_consistent_defect_screening")
    if "mlp:model_sha256_mismatch" in assessment.uncertain:
        _append_unique(steps, "recompute_stability_evidence_with_one_mlp_model")
    if "phonon:unstable" in assessment.hard_negative:
        _append_unique(steps, "verify_imaginary_modes_with_larger_supercells_or_dft")
    if "mixing:above_low_priority_threshold" in assessment.hard_negative:
        _append_unique(steps, "verify_high_mixing_penalty_before_further_investment")
    if "mixing:borderline" in assessment.uncertain:
        _append_unique(steps, "test_additional_sqs_compositions_and_energy_convergence")
    if "phase:above_low_priority_threshold" in assessment.hard_negative:
        _append_unique(steps, "verify_competing_phases_and_hull_with_consistent_dft")
    if "phase:borderline" in assessment.uncertain:
        _append_unique(steps, "verify_borderline_hull_distance_with_consistent_dft")
    if classification == "promising":
        _append_unique(steps, "perform_consistent_high_fidelity_dft_validation")
        _append_unique(steps, "test_multiple_sqs_compositions_and_supercell_convergence")
        if not require_defects:
            _append_unique(steps, "consider_defect_screening_for_priority_candidates")
    elif classification == "low-priority":
        _append_unique(steps, "deprioritize_unless_the_negative_signal_is_resolved")
    else:
        _append_unique(steps, "resolve_missing_or_conflicting_evidence_before_ranking")
    return steps


def _rationale(classification: str, assessment: _Assessment) -> str:
    if classification == "low-priority":
        return "Low priority because explicit negative signals were found: " + ", ".join(
            assessment.hard_negative
        )
    if classification == "uncertain":
        reasons = [*assessment.uncertain]
        return "Uncertain because evidence is missing, borderline, or incompatible: " + ", ".join(
            reasons
        )
    return (
        "Promising for further study because the required Stage 3--10 evidence is complete "
        "and no configured low-priority signal was found."
    )


def _evidence_level(
    *,
    gap_complete: bool,
    mixing_complete: bool,
    phonon_complete: bool,
    phase_complete: bool,
    defect_complete: bool,
) -> str:
    level = "L2"
    if gap_complete:
        level = "L3"
        if mixing_complete:
            level = "L4"
            if phonon_complete and phase_complete:
                level = "L5"
                if defect_complete:
                    level = "L6"
    return level


def _sort_number(value: object) -> float:
    number = _finite_float(value)
    return number if number is not None else math.inf


def _render_markdown_report(
    frame: pd.DataFrame,
    summary: dict[str, Any],
) -> str:
    def display(value: object, digits: int = 4) -> str:
        number = _finite_float(value)
        if number is not None:
            return f"{number:.{digits}f}"
        text = _clean_text(value)
        return text.replace("|", "\\|") if text else "not available"

    lines = [
        "# SS-Screen Stage 11 Recommendation Report",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        "> Decision-support output only. `promising` means worthy of further consistent",
        "> DFT or experimental study; it does not establish thermodynamic stability,",
        "> synthesizability, or device performance.",
        "",
        "## Summary",
        "",
        f"- Input pairs: {summary['input_pair_count']}",
        f"- Recommendation rows: {summary['recommendation_count']}",
        f"- Classification counts: `{json.dumps(summary['classification_counts'], sort_keys=True)}`",
        f"- Evidence levels: `{json.dumps(summary['evidence_level_counts'], sort_keys=True)}`",
        f"- Defects required: `{str(summary['require_defects']).lower()}`",
        "",
        "## Configured triage thresholds",
        "",
        f"- Promising mixing enthalpy maximum: {summary['settings']['promising_max_mixing_enthalpy_meV_per_atom']} meV/atom",
        f"- Low-priority mixing enthalpy threshold: {summary['settings']['low_priority_mixing_enthalpy_meV_per_atom']} meV/atom",
        f"- Promising same-MLIP hull maximum: {summary['settings']['promising_max_hull_eV_per_atom']} eV/atom",
        f"- Low-priority hull threshold: {summary['settings']['low_priority_hull_eV_per_atom']} eV/atom",
        "",
        "These are configurable triage thresholds, not universal physical constants.",
        "",
        "## Ranked candidates",
        "",
        "| Rank | Class | Evidence | Pair | Structure | x(B) | Mixing (meV/atom) | Hull (eV/atom) | Phonon |",
        "|---:|---|---|---|---|---:|---:|---:|---|",
    ]
    for row in frame.to_dict(orient="records"):
        pair = f"{row['comp_a']} / {row['comp_b']}"
        fraction = row.get("actual_fraction_b")
        if _finite_float(fraction) is None:
            fraction = row.get("target_fraction_b")
        lines.append(
            "| "
            f"{row['rank']} | {row['classification']} | {row['evidence_level']} | "
            f"{display(pair)} | {display(row.get('structure_id'))} | {display(fraction, 3)} | "
            f"{display(row.get('mixing_enthalpy_meV_per_atom'), 3)} | "
            f"{display(row.get('energy_above_hull_eV_per_atom'), 5)} | "
            f"{display(row.get('dynamical_status'))} |"
        )
    if frame.empty:
        lines.append("| - | - | - | No candidates | - | - | - | - | - |")

    lines.extend(["", "## Candidate audits", ""])
    for row in frame.to_dict(orient="records"):
        lines.extend(
            [
                f"### {row['rank']}. {row['recommendation_id']}",
                "",
                f"- Classification: `{row['classification']}`",
                f"- Evidence level: `{row['evidence_level']}` — {row['evidence_level_label']}",
                f"- Pair: `{row['mp_id_a']}` ({row['comp_a']}) / `{row['mp_id_b']}` ({row['comp_b']})",
                f"- Structure: `{row['structure_id'] or 'not available'}`",
                f"- Rationale: {row['rationale']}",
                f"- Positive evidence: `{row['positive_evidence']}`",
                f"- Risks: `{row['risks']}`",
                f"- Missing data: `{row['missing_data']}`",
                f"- Source warnings: `{row['source_warnings']}`",
                f"- Recommended next steps: `{row['recommended_next_steps']}`",
                "",
            ]
        )

    lines.extend(
        [
            "## Ranking policy",
            "",
            "Rows are ordered by classification, then higher evidence level, fewer risks and missing",
            "items, lower mixing enthalpy, lower same-MLIP hull distance, pair index, and structure ID.",
            "No opaque aggregate scientific score is used.",
            "",
            "## Scientific scope",
            "",
            summary["scientific_scope"],
            "",
        ]
    )
    return "\n".join(lines)


def generate_recommendations(
    *,
    pairs_path: str | Path,
    gap_results_path: str | Path,
    mixing_enthalpy_path: str | Path,
    phonons_path: str | Path,
    phase_stability_path: str | Path,
    output_path: str | Path,
    report_path: str | Path,
    defects_path: str | Path | None = None,
    summary_path: str | Path | None = None,
    gap_method: str | None = None,
    require_defects: bool = False,
    settings: RecommendationSettings | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Join Stage 5 and Stage 8--10 artifacts into auditable recommendations."""
    settings = settings or RecommendationSettings()
    _validate_settings(settings)
    pairs_path = Path(pairs_path)
    gaps_path = Path(gap_results_path)
    mixing_path = Path(mixing_enthalpy_path)
    phonons_path = Path(phonons_path)
    phase_path = Path(phase_stability_path)
    output_path = Path(output_path)
    report_path = Path(report_path)
    defects_file = Path(defects_path) if defects_path is not None else None

    pairs = _load_csv(pairs_path, label="pairs", required=REQUIRED_PAIR_COLUMNS).reset_index(
        drop=True
    )
    gaps = _load_csv(gaps_path, label="gap results", required=REQUIRED_GAP_COLUMNS)
    mixing = _load_csv(mixing_path, label="mixing enthalpy", required=REQUIRED_MIXING_COLUMNS)
    phonons = _load_csv(phonons_path, label="phonon summary", required=REQUIRED_PHONON_COLUMNS)
    phases = _load_csv(phase_path, label="phase stability", required=REQUIRED_PHASE_COLUMNS)
    defects = (
        _load_csv(defects_file, label="defect results", required=REQUIRED_DEFECT_COLUMNS)
        if defects_file is not None
        else None
    )

    pair_count = len(pairs)
    mixing = _prepare_pair_index(mixing, label="mixing enthalpy", pair_count=pair_count)
    phonons = _prepare_pair_index(phonons, label="phonon summary", pair_count=pair_count)
    phases = _prepare_pair_index(phases, label="phase stability", pair_count=pair_count)
    if "structure_role" in phonons.columns:
        phonons = phonons.loc[phonons["structure_role"].fillna("sqs") == "sqs"].copy()
    if defects is not None:
        defects = _prepare_pair_index(defects, label="defect results", pair_count=pair_count)

    rows: list[dict[str, Any]] = []
    for pair_index, pair in pairs.iterrows():
        structure_ids = _candidate_structure_ids(pair_index, mixing, phonons, phases, defects)
        for structure_id in structure_ids:
            assessment = _Assessment()
            mixing_rows = _rows_for_pair_and_structure(
                mixing,
                pair_index=pair_index,
                structure_column="sqs_structure_id",
                structure_id=structure_id,
            )
            phonon_rows = _rows_for_pair_and_structure(
                phonons,
                pair_index=pair_index,
                structure_column="structure_id",
                structure_id=structure_id,
            )
            phase_rows = _rows_for_pair_and_structure(
                phases,
                pair_index=pair_index,
                structure_column="structure_id",
                structure_id=structure_id,
            )
            gap = _evaluate_gap_evidence(
                pair,
                gaps,
                method_override=gap_method,
                settings=settings,
                assessment=assessment,
            )
            mixing_result = _evaluate_mixing(
                mixing_rows,
                settings=settings,
                assessment=assessment,
            )
            phonon_result = _evaluate_phonon(
                phonon_rows,
                assessment=assessment,
            )
            phase_result = _evaluate_phase(
                phase_rows,
                settings=settings,
                assessment=assessment,
            )
            defect_result = _evaluate_defects(
                defects,
                pair_index=pair_index,
                structure_id=structure_id,
                require_defects=require_defects,
                assessment=assessment,
            )

            model_values = sorted(assessment.model_sha256_values)
            if len(model_values) > 1:
                model_status = "incompatible"
                assessment.add_risk("mlp:model_sha256_mismatch", uncertain=True)
            elif len(model_values) == 1:
                model_status = "compatible"
            else:
                model_status = "missing_source"

            if assessment.hard_negative:
                classification = "low-priority"
            elif assessment.uncertain:
                classification = "uncertain"
            else:
                classification = "promising"

            defect_complete = defect_result["defect_status"] == "complete"
            evidence_level = _evidence_level(
                gap_complete=bool(gap["complete"]),
                mixing_complete=bool(mixing_result["complete"]),
                phonon_complete=bool(phonon_result["complete"]),
                phase_complete=bool(phase_result["complete"]),
                defect_complete=defect_complete,
            )
            next_steps = _recommended_steps(
                classification, assessment, require_defects=require_defects
            )
            target_fraction = mixing_result["target_fraction_b"]
            actual_fraction = mixing_result["actual_fraction_b"]
            if len(phonon_rows) == 1:
                phonon_row = phonon_rows.iloc[0]
                if target_fraction is None:
                    target_fraction = _finite_float(phonon_row.get("target_fraction_b"))
                if actual_fraction is None:
                    actual_fraction = _finite_float(phonon_row.get("actual_fraction_b"))

            row = {
                "schema_version": RECOMMENDATION_SCHEMA_VERSION,
                "recommendation_id": _recommendation_id(pair_index, structure_id, pair),
                "rank": None,
                "classification": classification,
                "evidence_level": evidence_level,
                "evidence_level_label": EVIDENCE_LEVEL_LABELS[evidence_level],
                "pair_index": pair_index,
                "source_group_index": pair.get("source_group_index"),
                "structure_id": structure_id,
                "target_fraction_b": target_fraction,
                "actual_fraction_b": actual_fraction,
                "fraction_basis": mixing_result["fraction_basis"],
                "mp_id_a": pair.get("mp_id_a"),
                "mp_id_b": pair.get("mp_id_b"),
                "comp_a": pair.get("comp_a"),
                "comp_b": pair.get("comp_b"),
                **{key: value for key, value in gap.items() if key != "complete"},
                **{
                    key: value
                    for key, value in mixing_result.items()
                    if key
                    not in {"complete", "target_fraction_b", "actual_fraction_b", "fraction_basis"}
                },
                **{key: value for key, value in phonon_result.items() if key != "complete"},
                **{key: value for key, value in phase_result.items() if key != "complete"},
                "defect_status": defect_result["defect_status"],
                "defect_signal": defect_result["defect_signal"],
                "defect_record_count": defect_result["record_count"],
                "model_sha256": model_values[0] if len(model_values) == 1 else None,
                "model_compatibility_status": model_status,
                "positive_evidence_count": len(assessment.positive),
                "risk_count": len(assessment.risks),
                "missing_data_count": len(assessment.missing),
                "positive_evidence": _json_list(assessment.positive),
                "risks": _json_list(assessment.risks),
                "missing_data": _json_list(assessment.missing),
                "source_warnings": _json_list(assessment.source_warnings),
                "recommended_next_steps": _json_list(next_steps),
                "rationale": _rationale(classification, assessment),
            }
            rows.append(row)

    rows.sort(
        key=lambda row: (
            CLASSIFICATION_ORDER[str(row["classification"])],
            -int(str(row["evidence_level"])[1:]),
            int(row["risk_count"]),
            int(row["missing_data_count"]),
            _sort_number(row.get("mixing_enthalpy_meV_per_atom")),
            _sort_number(row.get("energy_above_hull_eV_per_atom")),
            int(row["pair_index"]),
            str(row.get("structure_id") or ""),
        )
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    frame = pd.DataFrame.from_records(rows, columns=OUTPUT_COLUMNS)

    classification_counts = Counter(str(value) for value in frame["classification"])
    evidence_counts = Counter(str(value) for value in frame["evidence_level"])
    generated_at = datetime.now(UTC).isoformat()
    summary = {
        "schema_version": RECOMMENDATION_SCHEMA_VERSION,
        "generated_at": generated_at,
        "pairs_path": str(pairs_path),
        "gap_results_path": str(gaps_path),
        "mixing_enthalpy_path": str(mixing_path),
        "phonons_path": str(phonons_path),
        "phase_stability_path": str(phase_path),
        "defects_path": str(defects_file) if defects_file is not None else None,
        "output_path": str(output_path),
        "report_path": str(report_path),
        "input_pair_count": pair_count,
        "recommendation_count": len(frame),
        "classification_counts": dict(sorted(classification_counts.items())),
        "evidence_level_counts": dict(sorted(evidence_counts.items())),
        "require_defects": require_defects,
        "gap_method_override": gap_method,
        "settings": {
            "promising_max_mixing_enthalpy_meV_per_atom": settings.promising_max_mixing_enthalpy_mev_per_atom,
            "low_priority_mixing_enthalpy_meV_per_atom": settings.low_priority_mixing_enthalpy_mev_per_atom,
            "promising_max_hull_eV_per_atom": settings.promising_max_hull_ev_per_atom,
            "low_priority_hull_eV_per_atom": settings.low_priority_hull_ev_per_atom,
            "gap_consistency_tolerance_eV": settings.gap_consistency_tolerance_ev,
        },
        "ranking_policy": (
            "classification, descending evidence level, risk count, missing-data count, "
            "mixing enthalpy, hull distance, pair index, structure ID; no opaque score"
        ),
        "scientific_scope": (
            "Recommendation tiers are decision support for further consistent DFT or experimental "
            "study. They do not prove finite-temperature stability, synthesizability, or device "
            "performance. Missing core evidence is uncertain, never an implicit pass."
        ),
    }
    _atomic_write_dataframe(frame, output_path)
    _atomic_write_text(report_path, _render_markdown_report(frame, summary))
    if summary_path is not None:
        _atomic_write_text(Path(summary_path), json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return frame, summary
