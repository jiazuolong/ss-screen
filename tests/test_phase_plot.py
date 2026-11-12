"""Existing energies must produce scoped, normalized and auditable hull plots."""

import csv
import json

import pytest

from ssscreen.stability.phase_plot import checked_diagram, render_phase_plots


def fixture_rows():
    rows = []
    for name, composition, energy, above in [
        ("li", "Li", 0, 0),
        ("na", "Na", 0, 0),
        ("o", "O2", 0, 0),
        ("lio", "LiO", -2, 0),
        ("target", "LiNaO", -1, 1 / 3),
    ]:
        rows.append(
            {
                "target_structure_id": "target",
                "chemical_system": "Li-Na-O",
                "phase_structure_id": name,
                "phase_composition": composition,
                "phase_role": "sqs" if name == "target" else "competing_phase",
                "phase_energy_per_atom_eV": str(energy),
                # Deliberately a different cell size from the reduced formula.
                "phase_energy_total_eV": str(energy * 12),
                "phase_e_above_augmented_hull_eV_per_atom": str(above),
                "is_target": str(name == "target"),
            }
        )
    summary = {
        "structure_id": "target",
        "chemical_system": "Li-Na-O",
        "composition": "Li2Na2O2",
        "energy_per_atom_eV": "-1",
        "energy_above_hull_eV_per_atom": str(1 / 3),
        "pair_index": "2",
        "status": "success",
        "competing_set_complete": "True",
    }
    return rows, summary


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_hull_plot_normalizes_cell_energy_and_rejects_inconsistent_inputs():
    rows, summary = fixture_rows()
    diagram, target, error = checked_diagram(rows, summary)
    assert diagram.get_e_above_hull(target) == pytest.approx(1 / 3)
    assert error < 1e-10
    with pytest.raises(ValueError, match="duplicate"):
        checked_diagram(rows + [rows[0]], summary)
    with pytest.raises(ValueError, match="Missing terminal"):
        checked_diagram(rows[1:], summary)
    for key, value in [
        ("target_structure_id", "another"),
        ("chemical_system", "Ca-O-S"),
        ("phase_energy_per_atom_eV", "nan"),
        ("phase_e_above_augmented_hull_eV_per_atom", "0.5"),
    ]:
        changed = [dict(row) for row in rows]
        changed[-1][key] = value
        with pytest.raises(ValueError):
            checked_diagram(changed, summary)


def test_render_exports_only_requested_targets_and_preserves_inputs(tmp_path):
    rows, summary = fixture_rows()
    entries, scope = tmp_path / "entries.csv", tmp_path / "summary.csv"
    write_csv(entries, rows + [{**row, "target_structure_id": "unrelated"} for row in rows])
    write_csv(scope, [summary])
    original = entries.read_bytes(), scope.read_bytes()
    output = tmp_path / "plots"
    index = render_phase_plots(entries, scope, output)
    assert len(index["plots"]) == 1
    plot = index["plots"][0]
    assert (output / plot["png"]).read_bytes().startswith(b"\x89PNG")
    assert "<svg" in (output / plot["svg"]).read_text()
    with (output / index["entries"]).open() as handle:
        assert {row["target_structure_id"] for row in csv.DictReader(handle)} == {"target"}
    assert json.loads((output / "phase_plot_index.json").read_text()) == index
    assert original == (entries.read_bytes(), scope.read_bytes())
    with pytest.raises(FileExistsError):
        render_phase_plots(entries, scope, output)
