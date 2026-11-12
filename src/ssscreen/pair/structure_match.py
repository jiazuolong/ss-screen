"""Stage 3 structure matching from composition candidates and condensed archives."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..data.io import CondenseLoader
from .envmatch import StructureGroup, find_unique_envs, group_similar_structures
from .grouping import attach_band_gaps


def _candidate_entries(template_df: pd.DataFrame) -> list[list]:
    return [
        [str(row.material_id), str(row.x_element), float(row.band_gap)]
        for row in template_df.itertuples(index=False)
    ]


def match_structure_candidates(
    candidates: str | Path | pd.DataFrame,
    condensed_dirs: list[str | Path],
    *,
    min_x_elements: int = 2,
) -> tuple[list[StructureGroup], dict]:
    """Run envmatch on pre-screened composition candidates.

    Parameters
    ----------
    candidates
        Stage 1a composition-candidate CSV or an equivalent DataFrame. Required
        columns are ``template``, ``material_id``, ``x_element``, ``composition``
        or ``formula``, and ``band_gap``.
    condensed_dirs
        One or more Stage 2 archive directories containing ``{material_id}.json``.
    min_x_elements
        Minimum number of distinct X elements required for a structure group to
        survive. The default preserves the alloy-screening requirement.
    """
    df = pd.read_csv(candidates) if not isinstance(candidates, pd.DataFrame) else candidates.copy()
    loader = CondenseLoader(condensed_dirs)
    candidate_ids = set(df["material_id"].astype(str))
    # Freeze membership at startup so a concurrently growing Stage 03 archive
    # cannot change the input population halfway through this run.
    snapshot_ids = {
        path.stem for directory in condensed_dirs for path in Path(directory).glob("*.json")
    } & candidate_ids
    loaded_ids: set[str] = set()

    all_groups: list[StructureGroup] = []
    raw_group_count = 0
    missing_material_ids: list[str] = []
    invalid_material_ids: list[str] = []
    invalid_errors: dict[str, str] = {}

    for template, template_df in df.groupby("template", sort=False):
        entries = _candidate_entries(template_df)
        valid_entries = []
        material_ids = []
        condensed = []
        for entry in entries:
            material_id = entry[0]
            if material_id not in snapshot_ids:
                missing_material_ids.append(material_id)
                continue
            try:
                item = loader.get_condensed(material_id)
                if item is None:
                    missing_material_ids.append(material_id)
                    continue
                find_unique_envs([item])
            except Exception as exc:
                invalid_material_ids.append(material_id)
                invalid_errors[material_id] = str(exc)
                continue
            loaded_ids.add(material_id)
            valid_entries.append(entry)
            material_ids.append(material_id)
            condensed.append(item)

        if len(condensed) < 2:
            continue
        try:
            envs = find_unique_envs(condensed)
            groups = group_similar_structures(envs, str(template), material_ids)
        except Exception as exc:
            invalid_material_ids.extend(material_ids)
            invalid_errors.update({material_id: str(exc) for material_id in material_ids})
            continue
        attach_band_gaps(groups, valid_entries)
        raw_group_count += len(groups)
        all_groups.extend(group for group in groups if len(set(group.X_element)) >= min_x_elements)

    report = {
        "candidate_rows": int(len(df)),
        "template_count": int(df["template"].nunique()) if len(df) else 0,
        "missing_descriptions": int(len(missing_material_ids)),
        "missing_material_ids": missing_material_ids,
        "invalid_descriptions": int(len(invalid_material_ids)),
        "invalid_material_ids": invalid_material_ids,
        "invalid_errors": invalid_errors,
        "raw_group_count": int(raw_group_count),
        "group_count": int(len(all_groups)),
        "grouped_members": int(sum(group.group_size for group in all_groups)),
        "min_x_elements": int(min_x_elements),
        "candidate_materials": len(candidate_ids),
        "available_materials": len(loaded_ids),
        "available_material_ids": sorted(loaded_ids),
        "missing_materials": len(set(missing_material_ids)),
        "invalid_materials": len(set(invalid_material_ids)),
        "description_coverage": len(loaded_ids) / len(candidate_ids) if candidate_ids else 0.0,
        "partial_run": bool(missing_material_ids or invalid_material_ids),
        "condensed_dirs": [str(directory) for directory in condensed_dirs],
    }
    return all_groups, report
