"""Manifest evidence integrity, offline output, and conservative error handling."""

from pathlib import Path
import json
import csv

import numpy as np
import pytest
from ssscreen.geometry_pipeline import _config, _effective_supercell_matrix, evaluate
from ssscreen.detector import assess_rows, index_geometry, read_csv

FIXTURES = Path(__file__).parent / "data" / "stage13_geometry"


def test_substrate_search_uses_distinct_planes_and_signed_film_strain(tmp_path):
    from pymatgen.core import Lattice, Structure
    from ssscreen.geometry_pipeline import substrate_matches

    film = Structure(Lattice.cubic(4), ["Na"], [[0, 0, 0]])
    substrate = Structure(Lattice.cubic(4.04), ["Na"], [[0, 0, 0]])
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"schema_version": 2, "substrate": {"max_area_A2": 30}}))
    config = _config(path)["substrate"]
    matches = substrate_matches(film, substrate, config, "test-film", "test-substrate")
    families = {(1, 0, 0), (1, 1, 0), (1, 1, 1)}
    assert matches
    assert {tuple(m["film_miller"]) for m in matches} == families
    assert {tuple(m["substrate_miller"]) for m in matches} == families
    assert all(m["principal_strains"] == pytest.approx([0.01, 0.01]) for m in matches)
    assert all(m["strain_convention"] == "fixed_substrate_deformed_film" for m in matches)
    compressed = substrate_matches(substrate, film, config, "test-film-reverse", "test-substrate")
    assert compressed
    assert all(m["principal_strains"] == pytest.approx([4 / 4.04 - 1] * 2) for m in compressed)


def test_effective_supercell_matrix_reconstructs_reduced_zsl_basis():
    base = np.array([[4.0, 0.0, 0.0], [0.0, 4.0, 0.0]])
    # The returned ZSL basis can differ from its original area-multiple matrix
    # after the Zur reduction swaps vectors or adds/subtracts one row.
    reduced = np.array([[2, 2], [0, 2]]) @ base
    transform = _effective_supercell_matrix(base, reduced)
    assert np.array_equal(transform, [[2, 2], [0, 2]])
    assert np.allclose(transform @ base, reduced)


def test_offline_pipeline_never_invents_geometry(tmp_path):
    from monty.serialization import dumpfn
    from pymatgen.core import Lattice, Structure
    from ssscreen.geometry_bundle import digest

    # Self-contained synthetic evidence; do not restore removed historical files.
    fixture = tmp_path / "synthetic_input"
    fixture.mkdir()

    def write_table(name, rows):
        with (fixture / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    ends = []
    for role, element in [("A", "Na"), ("B", "K")]:
        path = fixture / f"{role}.json"
        dumpfn(Structure(Lattice.cubic(4), [element, "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]]), path)
        ends.append(
            dict(
                pair_id="pair",
                role=role,
                reference_set_id="synthetic",
                structure_file=str(path),
                sha256=digest(path),
                status="success",
                qc_status="pass",
                method="synthetic-method",
            )
        )
    path = fixture / "alloy.json"
    dumpfn(
        Structure(
            Lattice.cubic(5),
            ["Na", "K", "Cl", "Cl"],
            [[0, 0, 0], [0.5, 0, 0], [0, 0.5, 0], [0.5, 0.5, 0.5]],
        ),
        path,
    )
    write_table(
        "candidates.csv",
        [
            dict(
                candidate_id="candidate",
                pair_id="pair",
                actual_fraction_b=0.5,
                reference_set_id="synthetic",
                expected_structure_ids="syn-101;syn-202",
                replaceable_a="Na",
                replaceable_b="K",
                gap_a_eV=0,
                gap_b_eV=0.8,
            )
        ],
    )
    write_table("endmembers.csv", ends)
    write_table(
        "alloy_structures.csv",
        [
            dict(
                candidate_id="candidate",
                structure_id=f"syn-{seed}",
                seed=seed,
                actual_fraction_b=0.5,
                reference_set_id="synthetic",
                structure_file=str(path),
                sha256=digest(path),
                status="success",
                qc_status="pass",
            )
            for seed in (101, 202)
        ],
    )
    write_table(
        "properties.csv",
        [
            dict(
                candidate_id="candidate",
                structure_id=f"syn-{seed}",
                structure_sha256=digest(path),
                reference_set_id="synthetic",
                status="success",
                qc_status="pass",
                band_gap_eV=0.4,
                minimum_mesh_frequency_THz=0.1,
                mixing_enthalpy_meV_per_atom=18,
                energy_above_hull_eV_per_atom=0.012,
            )
            for seed in (101, 202)
        ],
    )
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"schema_version": 2}))
    out = tmp_path / "output"
    summary = evaluate(fixture, config, out)
    assert summary["candidate_count"] == 1
    main = read_csv(out / "candidate_evaluation.csv")[0]
    assert main["selected_structure_id"] == "syn-101"
    assert main["available_configurations"] == "2"
    assert main["phonon_min_THz"] == "0.1"
    assert main["mixing_enthalpy_meV_atom"] == "18.0"
    assert main["energy_above_hull_meV_atom"] == "12.0"
    assert main["gap_status"] == "有效"
    assert "seed202" not in (main.get("selected_structure_id") or "")
    assert "晶格常数匹配（新增）" in (out / "report.md").read_text()
    for filename in (
        "lattice_matches.csv",
        "substrate_top_matches.csv",
        "structure_matches.csv",
        "match_details.jsonl.gz",
        "summary.json",
    ):
        assert (out / filename).is_file()
    if main["substrate_principal_strain_pct"]:
        assert main["match_id"]
    else:
        assert main["candidate_grade"] != "优先进一步验证"
    ends[0]["method"] = ""
    write_table("endmembers.csv", ends)
    evaluate(fixture, config, tmp_path / "missing_method")
    assert (
        read_csv(tmp_path / "missing_method/candidate_evaluation.csv")[0]["lattice_status"]
        == "待核验"
    )
    (fixture / "substrates.json").write_text(json.dumps([{"substrate_id": "duplicate"}] * 2))
    with pytest.raises(ValueError, match="duplicate substrate_id"):
        evaluate(fixture, config, tmp_path / "duplicate_substrates")


def test_explicit_stage12_pair_and_x_join():
    result = [
        {
            "candidate_id": "XYZ",
            "stage12_pair_index": "4",
            "actual_fraction_b": "0.5",
            "gap_eV": "0.4",
            "gap_status": "有效",
            "gap_valid_configuration_count": "2",
            "candidate_grade": "待补充",
        }
    ]
    stage12 = [
        {
            "recommendation_id": "per-structure-1",
            "pair_index": "4",
            "actual_fraction_b": "0.5",
            "structure_id": "s101",
        },
        {
            "recommendation_id": "per-structure-2",
            "pair_index": "4",
            "actual_fraction_b": "0.5",
            "structure_id": "s202",
        },
    ]
    assessed = assess_rows(stage12, 2.0, index_geometry(result))
    assert len(assessed) == 1
    assert assessed[0]["candidate_id"] == "XYZ"
    assert assessed[0]["alloy_gap_eV"] == 0.4
    assert assessed[0]["band_match"] == "端元带隙缺失"


def test_config_rejects_unsupported_substitution(tmp_path):
    config = {"schema_version": 2, "substrate": {"allow_automatic_seed_fallback": True}}
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="fallback"):
        _config(path)


def test_missing_gap_target_has_pending_grade(tmp_path):
    config = {"schema_version": 2}
    path = tmp_path / "unset.json"
    path.write_text(json.dumps(config))
    assert _config(path)["gap_target_eV"] is None
