"""Feed external band-gap results back into final pair generation."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd
from monty.serialization import dumpfn

from ..config import PairThresholds
from ..data.io import load_group_df, write_pairs_csv
from .gap_export import validate_gap_results
from .pairing import attach_gaps_and_compress, enumerate_pairs, gaps_valid, pairs_to_dataframe

SUCCESS_STATUSES = frozenset({"success", "completed", "ok"})


def _bool_from_value(value: Any) -> bool | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "t", "1", "yes", "y", "direct"}:
        return True
    if text in {"false", "f", "0", "no", "n", "indirect"}:
        return False
    return None


def load_gap_results(
    gap_paths: Sequence[str | Path],
    *,
    method: str | None = None,
    allow_mixed_methods: bool = False,
) -> tuple[pd.DataFrame, dict[str, list], dict]:
    """Load external gap-result tables and build a material-id gap map.

    The original PBE/database gaps stored on ``StructureGroup.band_gaps`` are
    intentionally not modified. This helper only builds the high-level gap map
    needed by final pair enumeration.
    """
    frames = [validate_gap_results(path) for path in gap_paths]
    if not frames:
        raise ValueError("at least one gap-result table is required")
    rejected = [
        frame.attrs.get("validation_report", {})
        for frame in frames
        if frame.attrs.get("validation_report", {}).get("rejected_count", 0)
    ]
    if rejected:
        errors: dict[str, int] = {}
        for report in rejected:
            for name, count in report.get("error_counts", {}).items():
                errors[name] = errors.get(name, 0) + int(count)
        if "duplicate_result" in errors:
            raise ValueError("duplicate successful gap results are not allowed")
        raise ValueError(f"gap result validation rejected rows: {errors}")

    raw = pd.concat(frames, ignore_index=True)
    methods = sorted(raw["method"].dropna().astype(str).unique())
    if method is not None and allow_mixed_methods:
        raise ValueError("method and allow_mixed_methods are mutually exclusive")
    if method is None and not allow_mixed_methods:
        if len(methods) > 1:
            raise ValueError(
                "multiple gap methods present; pass --method to select one: " + ", ".join(methods)
            )
        method = methods[0] if methods else ""

    selected = (
        raw.copy() if allow_mixed_methods else raw.loc[raw["method"].astype(str) == method].copy()
    )
    success_mask = selected["status"].str.lower().isin(SUCCESS_STATUSES)
    successful = selected.loc[success_mask].copy()
    duplicate_rows = int(successful.duplicated(subset=["material_id"], keep=False).sum())
    if duplicate_rows:
        raise ValueError(f"duplicate successful gap results are not allowed for method {method!r}")

    gap_map = {
        str(row["material_id"]): [float(row["band_gap"]), _bool_from_value(row["is_direct"])]
        for _, row in successful.iterrows()
    }
    report = {
        "gap_files": [str(path) for path in gap_paths],
        "methods": methods,
        "selected_method": "mixed_sources" if allow_mixed_methods else method,
        "allow_mixed_methods": allow_mixed_methods,
        "gap_rows": int(len(raw)),
        "selected_gap_rows": int(len(selected)),
        "successful_gap_rows": int(len(successful)),
        "duplicate_success_rows": duplicate_rows,
        "failed_or_skipped_gap_rows": int((~success_mask).sum()),
    }
    return successful, gap_map, report


def generate_pairs_from_gap_results(
    *,
    groups_path: str | Path,
    gap_paths: Sequence[str | Path],
    output: str | Path,
    summary: str | Path | None = None,
    method: str | None = None,
    thresholds: PairThresholds | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Generate final alloying pairs from matched groups and external gaps."""
    thresholds = thresholds or PairThresholds()
    groups = load_group_df(groups_path)
    _, gap_map, report = load_gap_results(gap_paths, method=method)

    group_material_ids = sorted({str(mid) for group in groups for mid in group.mp_ids})
    missing = [mid for mid in group_material_ids if mid not in gap_map]
    all_pairs = []
    groups_with_pairs = 0
    groups_with_two_or_more_gaps = 0

    for group_index, group in enumerate(groups):
        compressed = attach_gaps_and_compress(group, gap_map)
        if compressed is None:
            continue
        groups_with_two_or_more_gaps += 1
        aligned_group, gaps = compressed
        if not gaps_valid(gaps, thresholds):
            continue
        pairs = enumerate_pairs(aligned_group, gaps, thresholds)
        if pairs:
            groups_with_pairs += 1
        for pair in pairs:
            pair["source_group_index"] = group_index
            pair["gap_method"] = report["selected_method"]
        all_pairs.extend(pairs)

    pairs_df = pairs_to_dataframe(all_pairs)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    write_pairs_csv(pairs_df, output)

    report.update(
        {
            "group_count": int(len(groups)),
            "materials_in_groups": int(len(group_material_ids)),
            "covered_materials": int(len(group_material_ids) - len(missing)),
            "coverage_fraction": (
                (len(group_material_ids) - len(missing)) / len(group_material_ids)
                if group_material_ids
                else 0.0
            ),
            "missing_materials": missing,
            "groups_with_two_or_more_gaps": groups_with_two_or_more_gaps,
            "groups_with_pairs": groups_with_pairs,
            "pair_count": int(len(pairs_df)),
        }
    )
    if summary is not None:
        Path(summary).parent.mkdir(parents=True, exist_ok=True)
        dumpfn(report, str(summary))
    return pairs_df, report


def _pair_keys(pairs: pd.DataFrame) -> set[str]:
    if pairs.empty:
        return set()
    keys = set()
    for _, row in pairs.iterrows():
        ids = sorted([str(row["mp_id_a"]), str(row["mp_id_b"])])
        keys.add("|".join(ids))
    return keys


def _safe_method_filename(method: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in method)


def compare_gap_methods(
    *,
    groups_path: str | Path,
    gap_paths: Sequence[str | Path],
    output_dir: str | Path,
    summary: str | Path,
    thresholds: PairThresholds | None = None,
) -> dict:
    """Generate method-specific pairs and a cross-method comparison report."""
    frames = [validate_gap_results(path) for path in gap_paths]
    if not frames:
        raise ValueError("at least one gap-result table is required")
    raw = pd.concat(frames, ignore_index=True)
    methods = sorted(raw["method"].dropna().astype(str).unique())
    if not methods:
        raise ValueError("gap-result tables contain no method labels")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    method_pair_keys: dict[str, set[str]] = {}
    method_reports: dict[str, dict] = {}
    method_gap_maps: dict[str, dict[str, list]] = {}

    for method in methods:
        pairs_path = output_dir / f"pairs_{_safe_method_filename(method)}.csv"
        pairs, report = generate_pairs_from_gap_results(
            groups_path=groups_path,
            gap_paths=gap_paths,
            output=pairs_path,
            method=method,
            thresholds=thresholds,
        )
        method_pair_keys[method] = _pair_keys(pairs)
        method_reports[method] = report
        _, gap_map, _ = load_gap_results(gap_paths, method=method)
        method_gap_maps[method] = gap_map

    common = set.intersection(*method_pair_keys.values()) if method_pair_keys else set()
    union = set.union(*method_pair_keys.values()) if method_pair_keys else set()
    baseline = methods[0]
    gap_shifts: dict[str, dict] = {}
    directness_changes: dict[str, dict] = {}
    for pair_key in sorted(union):
        ids = pair_key.split("|")
        directness_changes[pair_key] = {
            method: [
                method_gap_maps[method][ids[0]][1],
                method_gap_maps[method][ids[1]][1],
            ]
            for method in methods
            if ids[0] in method_gap_maps[method] and ids[1] in method_gap_maps[method]
        }
        if ids[0] not in method_gap_maps[baseline] or ids[1] not in method_gap_maps[baseline]:
            continue
        baseline_gaps = method_gap_maps[baseline]
        gap_shifts[pair_key] = {}
        for method in methods[1:]:
            gaps = method_gap_maps[method]
            if ids[0] not in gaps or ids[1] not in gaps:
                continue
            gap_shifts[pair_key][f"{method}_minus_{baseline}"] = {
                "gap_a": round(float(gaps[ids[0]][0]) - float(baseline_gaps[ids[0]][0]), 12),
                "gap_b": round(float(gaps[ids[1]][0]) - float(baseline_gaps[ids[1]][0]), 12),
            }
    comparison = {
        "methods": methods,
        "pair_counts": {method: len(keys) for method, keys in method_pair_keys.items()},
        "coverage": {
            method: {
                "covered_materials": report["covered_materials"],
                "materials_in_groups": report["materials_in_groups"],
                "coverage_fraction": report["coverage_fraction"],
                "missing_materials": report["missing_materials"],
            }
            for method, report in method_reports.items()
        },
        "common_pairs": sorted(common),
        "all_pairs": sorted(union),
        "gap_shifts": gap_shifts,
        "directness_changes": directness_changes,
        "method_only_pairs": {
            method: sorted(
                keys
                - set.union(*(other for name, other in method_pair_keys.items() if name != method))
                if len(method_pair_keys) > 1
                else keys
            )
            for method, keys in method_pair_keys.items()
        },
    }
    Path(summary).parent.mkdir(parents=True, exist_ok=True)
    dumpfn(comparison, str(summary))
    return comparison
