"""Plot validated existing phase energies without loading a relaxation model.

Run with ``python -m ssscreen.stability.phase_plot --help`` in the project
calculation environment. Per-target hulls include the target, as in competing.py.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

from pymatgen.analysis.phase_diagram import PDEntry, PDPlotter, PhaseDiagram
from pymatgen.core import Composition, Element

from ..config import CompetingPhaseSettings

ENERGY_TOLERANCE = CompetingPhaseSettings.numerical_tolerance_ev_per_atom
PLOT_DPI = 180


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def checked_diagram(rows: list[dict[str, str]], expected: dict[str, str]):
    """Rebuild from eV/atom, preserving reduced-formula normalization."""
    target_id = expected["structure_id"]
    system = expected["chemical_system"]
    if expected["status"] != "success" or expected["competing_set_complete"].lower() != "true":
        raise ValueError(f"{target_id}: competition set is not complete and successful")
    entries, seen, target = [], set(), None
    for row in rows:
        phase_id = row["phase_structure_id"]
        if row["target_structure_id"] != target_id or row["chemical_system"] != system:
            raise ValueError(f"{target_id}: mixed target or chemical system")
        if phase_id in seen:
            raise ValueError(f"{target_id}: duplicate phase {phase_id}")
        seen.add(phase_id)
        comp = Composition(row["phase_composition"])
        if not set(comp.chemical_system.split("-")).issubset(system.split("-")):
            raise ValueError(f"{target_id}: phase contains elements outside its system")
        energy = float(row["phase_energy_per_atom_eV"])
        if not math.isfinite(energy):
            raise ValueError(f"{target_id}: non-finite energy")
        entry = PDEntry(comp, energy * comp.num_atoms, attribute=phase_id)
        entries.append(entry)
        if row["is_target"].lower() == "true":
            if target is not None or phase_id != target_id:
                raise ValueError(f"{target_id}: ambiguous target")
            target = entry
    if target is None:
        raise ValueError(f"{target_id}: target entry is missing")
    if (
        target.composition.fractional_composition
        != Composition(expected["composition"]).fractional_composition
    ):
        raise ValueError(f"{target_id}: target composition differs from summary")
    if not math.isclose(
        target.energy_per_atom,
        float(expected["energy_per_atom_eV"]),
        abs_tol=ENERGY_TOLERANCE,
        rel_tol=0,
    ):
        raise ValueError(f"{target_id}: target energy differs from summary")
    elements = [Element(symbol) for symbol in system.split("-")]
    if not 2 <= len(elements) <= 3:
        raise ValueError(f"{target_id}: this plot supports binary/ternary systems")
    diagram = PhaseDiagram(entries, elements=elements)
    errors = []
    for entry, row in zip(entries, rows, strict=True):
        actual = diagram.get_e_above_hull(entry)
        declared = float(row["phase_e_above_augmented_hull_eV_per_atom"])
        if not math.isfinite(declared) or not math.isclose(
            actual, declared, abs_tol=ENERGY_TOLERANCE, rel_tol=0
        ):
            raise ValueError(f"{target_id}: hull distance differs for {entry.attribute}")
        errors.append(abs(actual - declared))
    actual = diagram.get_e_above_hull(target)
    if not math.isclose(
        actual,
        float(expected["energy_above_hull_eV_per_atom"]),
        abs_tol=ENERGY_TOLERANCE,
        rel_tol=0,
    ):
        raise ValueError(f"{target_id}: target hull distance differs from summary")
    return diagram, target, max(errors, default=0.0)


def draw_diagram(diagram: PhaseDiagram, target: PDEntry, stem: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.lines import Line2D

    lines, stable, unstable = PDPlotter(diagram, backend="matplotlib").pd_plot_data
    figure, axes = plt.subplots(figsize=(8, 7))
    figure.patch.set_facecolor("white")
    for x, y in lines:
        axes.plot(x, y, color="#334155", linewidth=1.2, zorder=1)
    if unstable:
        coords = list(unstable.values())
        axes.scatter(
            [p[0] for p in coords],
            [p[1] for p in coords],
            s=25,
            color="#d39b32",
            alpha=0.65,
            edgecolor="white",
            linewidth=0.4,
            zorder=2,
        )
    for point, entry in stable.items():
        axes.scatter(*point, s=48, color="#23745b", edgecolor="white", linewidth=0.6, zorder=3)
        center = (
            np.array([0.5, math.sqrt(3) / 6]) if len(diagram.elements) == 3 else np.array([0.5, 0])
        )
        direction = np.asarray(point) - center
        offset = direction / max(float(np.linalg.norm(direction)), 0.1) * 12
        axes.annotate(
            entry.composition.reduced_formula,
            point,
            xytext=offset,
            textcoords="offset points",
            fontsize=10,
            ha="left" if offset[0] >= 0 else "right",
            va="bottom" if offset[1] >= 0 else "top",
            color="#143c30",
        )
    coords = next((p for p, entry in stable.items() if entry is target), None)
    if coords is None:
        coords = unstable[target]
    axes.scatter(
        *coords, s=190, marker="*", color="#c72f46", edgecolor="white", linewidth=0.8, zorder=5
    )
    axes.annotate(
        target.composition.reduced_formula,
        coords,
        xytext=(12, -21),
        textcoords="offset points",
        fontsize=11,
        weight="bold",
        color="#a81c31",
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8},
    )
    system = "-".join(str(element) for element in diagram.elements)
    ehull = diagram.get_e_above_hull(target)
    axes.set_title(
        f"{system}  |  {target.composition.reduced_formula}\n"
        f"0 K MACE convex hull   |   target above hull: {ehull * 1000:.2f} meV/atom",
        fontsize=13,
        pad=24,
    )
    if len(diagram.elements) == 3:
        axes.set_aspect("equal")
        axes.set_xlim(-0.14, 1.14)
        axes.set_ylim(-0.13, math.sqrt(3) / 2 + 0.12)
        axes.axis("off")
    else:
        axes.set_xlabel(f"Atomic fraction of {diagram.elements[1]}")
        axes.set_ylabel("Formation energy (eV/atom)")
    handles = [
        Line2D([], [], color="#334155", linewidth=1.2, label="Hull tie-lines"),
        Line2D([], [], linestyle="none", marker="o", color="#23745b", label="Stable phase"),
        Line2D([], [], linestyle="none", marker="o", color="#d39b32", label="Above hull"),
        Line2D(
            [],
            [],
            linestyle="none",
            marker="*",
            color="#c72f46",
            markersize=11,
            label="Target alloy",
        ),
    ]
    figure.legend(
        handles=handles,
        loc="lower center",
        ncol=4,
        frameon=False,
        fontsize=9,
        bbox_to_anchor=(0.5, 0.045),
    )
    figure.text(
        0.5,
        0.015,
        "Candidate-inclusive hull | supplied competing phases | no finite-temperature free energies",
        ha="center",
        fontsize=8,
        color="#64748b",
    )
    figure.subplots_adjust(top=0.85, bottom=0.13, left=0.1, right=0.9)
    figure.savefig(stem.with_suffix(".png"), dpi=PLOT_DPI)
    figure.savefig(stem.with_suffix(".svg"))
    plt.close(figure)


def render_phase_plots(
    entries_path: Path,
    summary_path: Path,
    output_dir: Path,
    *,
    competing_structures: Path | None = None,
    candidate_structures: Path | None = None,
) -> dict:
    source_rows, scope = csv_rows(entries_path), csv_rows(summary_path)
    if not scope or len({row["structure_id"] for row in scope}) != len(scope):
        raise ValueError("Summary must contain unique target structures")
    groups = defaultdict(list)
    for row in source_rows:
        groups[row["target_structure_id"]].append(row)
    checked = []
    for expected in scope:
        rows = groups[expected["structure_id"]]
        checked.append((expected, rows, *checked_diagram(rows, expected)))
    # Validate the complete scope before writing any plots; never overwrite a bundle.
    output_dir.mkdir(parents=True, exist_ok=False)
    selected = [row for _, rows, *_ in checked for row in rows]
    subset = output_dir / "hull_entries.csv"
    with subset.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)
    plots = []
    for expected, rows, diagram, target, error in checked:
        name = hashlib.sha256(expected["structure_id"].encode()).hexdigest()[:20]
        stem = output_dir / name
        draw_diagram(diagram, target, stem)
        plots.append(
            {
                "target_structure_id": expected["structure_id"],
                "pair_index": expected["pair_index"],
                "composition": expected["composition"],
                "chemical_system": expected["chemical_system"],
                "energy_above_hull_eV_per_atom": diagram.get_e_above_hull(target),
                "phase_count": len(rows),
                "max_hull_error_eV_per_atom": error,
                "png": stem.with_suffix(".png").name,
                "svg": stem.with_suffix(".svg").name,
                "png_sha256": sha256(stem.with_suffix(".png")),
                "svg_sha256": sha256(stem.with_suffix(".svg")),
            }
        )
        print(f"Plotted {len(plots)}/{len(checked)}: {expected['chemical_system']}", flush=True)
    index = {
        "schema_version": 1,
        "entries": subset.name,
        "entries_sha256": sha256(subset),
        "source_entries": str(entries_path.resolve()),
        "source_entries_sha256": sha256(entries_path),
        "scope_summary": str(summary_path.resolve()),
        "scope_summary_sha256": sha256(summary_path),
        "competing_structures": (
            str(competing_structures.resolve()) if competing_structures else None
        ),
        "candidate_structures": (
            str(candidate_structures.resolve()) if candidate_structures else None
        ),
        "energy_tolerance_eV_per_atom": ENERGY_TOLERANCE,
        "plots": plots,
    }
    (output_dir / "phase_plot_index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entries", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--competing-structures", type=Path)
    parser.add_argument("--candidate-structures", type=Path)
    args = parser.parse_args()
    render_phase_plots(
        args.entries,
        args.summary,
        args.output_dir,
        competing_structures=args.competing_structures,
        candidate_structures=args.candidate_structures,
    )


if __name__ == "__main__":
    main()
