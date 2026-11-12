"""Endpoint interval screening, independent of legacy narrow-gap cutoffs."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path

import click
import pandas as pd

from ..data.io import load_group_df
from ..material_assessment import PHOTON_ENERGY_EV_UM
from .gap_feedback import load_gap_results


def screen_wavelength(
    groups_paths: tuple[Path, ...],
    gap_paths: tuple[Path, ...],
    wavelength_um: float,
    method: str | None,
    output: Path,
    summary: Path,
    *,
    min_gap_exclusive: float | None = None,
    max_gap_exclusive: float | None = None,
    allow_mixed_methods: bool = False,
) -> tuple[pd.DataFrame, dict]:
    """Enumerate unique unordered pairs; retain all group memberships."""
    if not math.isfinite(wavelength_um) or wavelength_um <= 0:
        raise ValueError("wavelength must be finite and positive")
    energy = PHOTON_ENERGY_EV_UM / wavelength_um
    for bound in (min_gap_exclusive, max_gap_exclusive):
        if bound is not None and (not math.isfinite(bound) or bound < 0):
            raise ValueError("gap bounds must be finite and nonnegative")
    if (
        min_gap_exclusive is not None
        and max_gap_exclusive is not None
        and min_gap_exclusive >= max_gap_exclusive
    ):
        raise ValueError("lower gap bound must be below upper bound")
    input_sha256 = {
        "groups": [hashlib.sha256(path.read_bytes()).hexdigest() for path in groups_paths],
        "gaps": [hashlib.sha256(path.read_bytes()).hexdigest() for path in gap_paths],
    }
    successful, gaps, report = load_gap_results(
        gap_paths, method=method, allow_mixed_methods=allow_mixed_methods
    )
    methods = successful.set_index("material_id")["method"].to_dict()
    pairs: dict[tuple[str, str], dict] = {}
    materials: set[str] = set()
    group_count = 0
    for path in groups_paths:
        for index, group in enumerate(load_group_df(path)):
            group_count += 1
            materials.update(map(str, group.mp_ids))
            for i, j in itertools.combinations(range(len(group.mp_ids)), 2):
                a, b = str(group.mp_ids[i]), str(group.mp_ids[j])
                if a == b or group.compositions[i] == group.compositions[j]:
                    continue
                if a not in gaps or b not in gaps:
                    continue
                ga, gb = float(gaps[a][0]), float(gaps[b][0])
                if not all(math.isfinite(g) and g >= 0 for g in (ga, gb)):
                    raise ValueError("invalid successful endpoint gap")
                if not min(ga, gb) <= energy <= max(ga, gb):
                    continue
                if min_gap_exclusive is not None and min(ga, gb) <= min_gap_exclusive:
                    continue
                if max_gap_exclusive is not None and max(ga, gb) >= max_gap_exclusive:
                    continue
                source = {"file": str(path.resolve()), "index": index}
                key = tuple(sorted((a, b)))
                if key in pairs:
                    pairs[key]["source_groups"].append(source)
                    continue
                pairs[key] = {
                    "mp_id_a": a,
                    "mp_id_b": b,
                    "comp_a": group.compositions[i],
                    "comp_b": group.compositions[j],
                    "gap_a": ga,
                    "gap_b": gb,
                    "gap_direct_a": gaps[a][1],
                    "gap_direct_b": gaps[b][1],
                    "gap_method": methods[a] if methods[a] == methods[b] else "mixed_sources",
                    "gap_method_a": methods[a],
                    "gap_method_b": methods[b],
                    "source_group_index": index,
                    "source_groups": [source],
                    "target_wavelength_um": wavelength_um,
                    "target_energy_eV": energy,
                    "gap_rule": "endpoint_range_covers_photon_energy",
                    "min_gap_exclusive_eV": min_gap_exclusive,
                    "max_gap_exclusive_eV": max_gap_exclusive,
                }
    rows = []
    for key in sorted(pairs):
        row = pairs[key]
        row["source_groups"] = json.dumps(row["source_groups"], ensure_ascii=False)
        rows.append(row)
    columns = [
        "mp_id_a",
        "mp_id_b",
        "comp_a",
        "comp_b",
        "gap_a",
        "gap_b",
        "gap_direct_a",
        "gap_direct_b",
        "gap_method",
        "gap_method_a",
        "gap_method_b",
        "source_group_index",
        "source_groups",
        "target_wavelength_um",
        "target_energy_eV",
        "gap_rule",
        "min_gap_exclusive_eV",
        "max_gap_exclusive_eV",
    ]
    frame = pd.DataFrame(rows, columns=columns)
    report.update(
        target_wavelength_um=wavelength_um,
        target_energy_eV=energy,
        group_count=group_count,
        materials_in_groups=len(materials),
        covered_materials=len(materials & gaps.keys()),
        missing_materials=sorted(materials - gaps.keys()),
        pair_count=len(frame),
        legacy_gap_thresholds_applied=False,
        pbe_fallback=False,
        min_gap_exclusive_eV=min_gap_exclusive,
        max_gap_exclusive_eV=max_gap_exclusive,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    summary.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    report.update(
        input_sha256=input_sha256,
        output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
    )
    summary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return frame, report


@click.command("pair-wavelength")
@click.option(
    "--groups",
    "groups_paths",
    multiple=True,
    required=True,
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--gap-results",
    "gap_paths",
    multiple=True,
    required=True,
    type=click.Path(exists=True, path_type=Path),
)
@click.option("--target-wavelength-um", "wavelength_um", type=float, required=True)
@click.option("--method", default=None)
@click.option(
    "--allow-mixed-methods",
    is_flag=True,
    help="Use one result per material across methods; preserve endpoint methods.",
)
@click.option("--min-gap-exclusive", type=float, default=None)
@click.option("--max-gap-exclusive", type=float, default=None)
@click.option("--output", type=click.Path(path_type=Path), required=True)
@click.option("--summary", type=click.Path(path_type=Path), required=True)
def main(
    groups_paths,
    gap_paths,
    wavelength_um,
    method,
    allow_mixed_methods,
    min_gap_exclusive,
    max_gap_exclusive,
    output,
    summary,
):
    """Screen matched groups using a closed endpoint gap interval."""
    try:
        _, report = screen_wavelength(
            groups_paths,
            gap_paths,
            wavelength_um,
            method,
            output,
            summary,
            min_gap_exclusive=min_gap_exclusive,
            max_gap_exclusive=max_gap_exclusive,
            allow_mixed_methods=allow_mixed_methods,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(report, ensure_ascii=False))
