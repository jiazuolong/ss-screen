import csv
import json

import pytest

from ssscreen.stability.result_library import historical_rows, match_library, sha256


def table(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.parametrize("kind", ["phonon", "phase"])
def test_library_remaps_verified_structures_and_preserves_missing(tmp_path, kind):
    geometry = tmp_path / "structure"
    geometry.write_text("original geometry")
    file = {"path": str(geometry), "sha256": sha256(geometry)}
    record = dict(
        structure_id="old",
        structure_role="sqs",
        pair_index=7,
        mp_id_a="a",
        mp_id_b="b",
        actual_fraction_b=0.5,
        input_structure=file,
        output_structure=file,
        backend=dict(name="mace", version="1", model_sha256="1" * 64, dtype="float64"),
        settings=dict(
            optimizer="FIRE",
            cell_mode="full",
            fmax_ev_per_angstrom=0.01,
            max_steps=500,
            quality_control=dict(
                min_volume_ratio=0.5, max_volume_ratio=2, min_distance_angstrom=0.5
            ),
        ),
        energy_per_atom_eV=-3,
        status="success",
        usable_for_thermodynamics=True,
    )
    relax = tmp_path / "relax.jsonl"
    relax.write_text(json.dumps(record))
    db = tmp_path / "db"
    db.write_text("source database")
    row = dict(
        structure_id="old",
        pair_index=7,
        status="success",
        dynamical_status="stable",
        energy_above_hull_eV_per_atom=0.01,
        hull_signal="near",
        usable_for_screening=True,
        energy_per_atom_eV=-3,
        mp_database_sha256=sha256(db),
    )
    source = tmp_path / "summary.csv"
    table(source, [row])
    history = list(historical_rows(kind, source, relax, "batch"))
    library = tmp_path / "library.csv"
    table(library, history)
    pairs = tmp_path / "pairs.csv"
    table(pairs, [dict(mp_id_a="a", mp_id_b="b")])
    record.update(pair_index=0, structure_id="new")
    relax.write_text(json.dumps(record))
    output = tmp_path / "filtered.csv"

    def match():
        return match_library(kind, library, relax, pairs, output, db)

    rows, _ = match()
    assert (rows[0]["structure_id"], rows[0]["pair_index"], rows[0]["library_structure_id"]) == (
        "new",
        0,
        "old",
    )
    record["backend"]["dtype"] = "float32"
    relax.write_text(json.dumps(record))
    rows, backup = match()
    assert (
        backup.is_file()
        and rows[0]["status"] == "missing"
        and "energy_above_hull_eV_per_atom" not in rows[0]
    )
    geometry.write_text("changed structure")
    before = output.read_bytes()
    with pytest.raises(ValueError, match="结构文件已改变"):
        match()
    assert output.read_bytes() == before
