"""Composition-template grouping.

First stage of pair screening: bucket materials whose reduced compositions
share a common "fixed" part, leaving one element as the variable ``X`` site.
For a binary ``AxBy`` the templates are ``AxX`` and ``ByX`` (i.e. each element
in turn plays the role of X); for a ternary ``AxByCz`` there are three
templates.

Merges the divergent logic of ``screening-binary.ipynb`` cell 15 and
``screening-tenary.ipynb`` cell 5 into a single function parameterised by the
number of elements.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd
from pymatgen.core import Composition

from ..config import composition_permutations
from .envmatch import StructureGroup


def composition_template(comp: Composition) -> str:
    """Render the *fixed* part of a reduced composition as ``"A{...}B{...}"``.

    Used for display / debugging. The variable-element slot is appended by
    :func:`group_by_composition_template`.
    """
    return comp.reduced_formula


def _template_key(comp: Composition, permutation: list[int]) -> str:
    """Build the ``AxByX{n}`` template key for one permutation.

    ``permutation[-1]`` is the variable element; the leading indices are the
    spectator (fixed) elements. Reproduces cell 15 (binary) and cell 5
    (ternary) exactly.
    """
    elems = list(comp.keys())
    fixed = {elems[k]: comp[elems[k]] for k in permutation[:-1]}
    # Reduced formula of the fixed part (handles integer amounts), e.g.
    # {Ca:3} -> "Ca3", {} -> "" (only happens for elemental, out of scope).
    fixed_str = Composition(fixed).reduced_formula if fixed else ""
    x_amount = int(comp[elems[permutation[-1]]])
    return f"{fixed_str}X{x_amount}"


def group_by_composition_template(
    df: pd.DataFrame,
    nelems: int | None = None,
    *,
    index_col: str = "material_id",
    comp_col: str = "reduced_composition",
    bandgap_col: str = "band_gap",
    min_group_size: int = 2,
) -> dict[str, list[list]]:
    """Group rows of ``df`` by composition template (``AxByX`` etc.).

    Parameters
    ----------
    df
        Dataset with one row per material. Must contain ``comp_col``
        (pymatgen ``Composition``), ``bandgap_col`` (float, eV), and be indexed
        by ``index_col``.
    nelems
        Number of elements in the reduced composition (2 or 3). If ``None``,
        inferred per-row from ``len(comp_col)`` — but a fixed value is strongly
        recommended so the permutation set is consistent.
    min_group_size
        Drop templates with fewer than this many members (default 2: a template
        must have at least two structures to be a candidate for pairing).

    Returns
    -------
    dict mapping template key (``"CaX3"``) to a list of
    ``[material_id, x_element_symbol, band_gap]`` triples, sorted by nothing in
    particular (insertion order).

    Mirrors ``screening-binary.ipynb:15`` and ``screening-tenary.ipynb:5``.
    """
    if nelems is not None:
        permutations = composition_permutations(nelems)

    all_fixed_parts: dict[str, list[list]] = {}
    for index, row in df.iterrows():
        rd = row[comp_col]
        if nelems is None:
            perms = composition_permutations(len(rd))
        else:
            perms = permutations
        elems = list(rd.keys())
        for perm in perms:
            key = _template_key(rd, perm)
            x_elem = str(elems[perm[-1]])
            entry = [str(index), x_elem, float(row[bandgap_col])]
            all_fixed_parts.setdefault(key, []).append(entry)

    if min_group_size > 1:
        all_fixed_parts = {k: v for k, v in all_fixed_parts.items() if len(v) >= min_group_size}
    return all_fixed_parts


def screen_composition_candidates(
    df: pd.DataFrame,
    *,
    nelems: int,
    max_bandgap: float,
    max_e_hull: float,
    excluded_elements: set[str] | frozenset[str],
    min_group_size: int = 2,
    min_x_elements: int = 2,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Select and write composition-template candidates before structure matching."""
    hull_col = "e_hull" if "e_hull" in df.columns else "energy_above_hull"
    selected = df.loc[
        (df["nelems"] == nelems) & (df[hull_col] <= max_e_hull) & (df["band_gap"] < max_bandgap),
        :,
    ].copy()
    selected = selected.loc[
        ~selected["reduced_composition"].apply(
            lambda comp: any(str(el) in excluded_elements for el in comp.elements)
        ),
        :,
    ]

    templates = group_by_composition_template(
        selected,
        nelems=nelems,
        min_group_size=min_group_size,
    )
    templates = {
        template: entries
        for template, entries in templates.items()
        if len({entry[1] for entry in entries}) >= min_x_elements
    }

    records = []
    for template, entries in templates.items():
        for material_id, x_element, band_gap in entries:
            row = selected.loc[material_id]
            composition = row["reduced_composition"]
            records.append(
                {
                    "template": template,
                    "material_id": material_id,
                    "x_element": x_element,
                    "formula": row.get("formula", composition.reduced_formula),
                    "composition": composition.reduced_formula,
                    "band_gap": band_gap,
                    "e_hull": row[hull_col],
                    "source": row.get("source", ""),
                }
            )

    candidates = pd.DataFrame.from_records(
        records,
        columns=[
            "template",
            "material_id",
            "x_element",
            "formula",
            "composition",
            "band_gap",
            "e_hull",
            "source",
        ],
    )
    summary = {
        "input_rows": int(len(df)),
        "selected_rows": int(len(selected)),
        "template_count": int(len(templates)),
        "candidate_rows": int(len(candidates)),
        "nelems": int(nelems),
        "max_bandgap": float(max_bandgap),
        "max_e_hull": float(max_e_hull),
        "min_group_size": int(min_group_size),
        "min_x_elements": int(min_x_elements),
    }
    return candidates, summary


def screen_composition_batches(
    df: pd.DataFrame,
    *,
    element_counts: Iterable[int],
    max_bandgap: float,
    max_e_hull: float,
    excluded_elements: set[str],
    min_group_size: int = 2,
    min_x_elements: int = 2,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run the existing binary/ternary rules and combine their candidates."""
    counts = list(dict.fromkeys(element_counts))
    if not counts or any(count not in (2, 3) for count in counts):
        raise ValueError("Select binary (2), ternary (3), or both.")
    if not df.index.is_unique or df.index.hasnans:
        raise ValueError("Input material IDs must be unique and non-null.")
    if not all(isinstance(value, str) for value in df.index):
        raise ValueError("Input material IDs must be strings in the DataFrame index.")

    tables, reports = [], []
    for count in counts:
        table, report = screen_composition_candidates(
            df,
            nelems=count,
            max_bandgap=max_bandgap,
            max_e_hull=max_e_hull,
            excluded_elements=excluded_elements,
            min_group_size=min_group_size,
            min_x_elements=min_x_elements,
        )
        if len(counts) > 1:
            table["nelems"] = count
        tables.append(table)
        reports.append(report)

    candidates = pd.concat(tables, ignore_index=True)
    summary = dict(reports[0])
    if len(counts) > 1:
        summary["nelems"] = counts
        for key in ("selected_rows", "template_count", "candidate_rows"):
            summary[key] = sum(report[key] for report in reports)
    summary["by_nelems"] = {str(n): report for n, report in zip(counts, reports, strict=True)}
    summary["unique_candidate_materials"] = int(candidates["material_id"].nunique())
    return candidates, summary


def candidate_structures(df: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    """Extract each selected material once, preserving original structures/columns."""
    if "structure" not in df.columns:
        raise ValueError("Candidate structure export requires a 'structure' column.")
    selected = df.loc[candidates["material_id"].drop_duplicates().tolist()].copy()
    if selected["structure"].isna().any():
        raise ValueError("Candidate structure export found missing structures.")
    return selected


def attach_band_gaps(
    groups: Iterable[StructureGroup],
    template_entries: list[list],
) -> None:
    """Fill in each group's ``band_gaps`` from the template's ``[id, x, gap]`` rows.

    ``group.entry_idx`` indexes into ``template_entries``. Mutates the groups
    in place, matching upstream ``get_groups`` in
    ``screening-binary.ipynb:26``.
    """
    for group in groups:
        group.band_gaps = [template_entries[i][2] for i in group.entry_idx]
