"""Tests for staged structure matching from composition candidates."""

from __future__ import annotations

import pandas as pd
from monty.serialization import dumpfn

from ssscreen.pair.structure_match import match_structure_candidates


def _condensed(formula: str, x_element: str) -> dict:
    return {
        "formula": formula,
        "sites": {
            "0": {
                "element": "Ca",
                "poly_formula": f"{x_element}6",
                "geometry": {"type": "octahedral"},
            },
            "1": {
                "element": x_element,
                "poly_formula": "Ca6",
                "geometry": {"type": "octahedral"},
            },
        },
    }


def test_match_structure_candidates_groups_same_environment_with_different_x(tmp_path):
    condensed_dir = tmp_path / "condensed"
    condensed_dir.mkdir()
    dumpfn(_condensed("CaS", "S"), condensed_dir / "mp-1.json")
    dumpfn(_condensed("CaSe", "Se"), condensed_dir / "mp-2.json")

    candidates = pd.DataFrame(
        [
            {
                "template": "CaX1",
                "material_id": "mp-1",
                "x_element": "S",
                "formula": "CaS",
                "composition": "CaS",
                "band_gap": 0.0,
                "e_hull": 0.0,
                "source": "test",
            },
            {
                "template": "CaX1",
                "material_id": "mp-2",
                "x_element": "Se",
                "formula": "CaSe",
                "composition": "CaSe",
                "band_gap": 0.3,
                "e_hull": 0.0,
                "source": "test",
            },
        ]
    )
    candidate_path = tmp_path / "composition_candidates.csv"
    candidates.to_csv(candidate_path, index=False)

    groups, report = match_structure_candidates(candidate_path, [condensed_dir])

    assert report["candidate_rows"] == 2
    assert report["template_count"] == 1
    assert report["missing_descriptions"] == 0
    assert report["raw_group_count"] == 1
    assert report["group_count"] == 1

    group = groups[0]
    assert group.group_size == 2
    assert group.mp_ids == ["mp-1", "mp-2"]
    assert group.X_element == ["S", "Se"]
    assert group.compositions == ["CaS", "CaSe"]
    assert group.band_gaps == [0.0, 0.3]
    assert not report["partial_run"]
    assert report["description_coverage"] == 1.0


def test_match_structure_candidates_reports_missing_descriptions(tmp_path):
    condensed_dir = tmp_path / "condensed"
    condensed_dir.mkdir()
    dumpfn(_condensed("CaS", "S"), condensed_dir / "mp-1.json")

    candidates = pd.DataFrame(
        [
            {
                "template": "CaX1",
                "material_id": "mp-1",
                "x_element": "S",
                "formula": "CaS",
                "composition": "CaS",
                "band_gap": 0.0,
                "e_hull": 0.0,
                "source": "test",
            },
            {
                "template": "CaX1",
                "material_id": "mp-missing",
                "x_element": "Se",
                "formula": "CaSe",
                "composition": "CaSe",
                "band_gap": 0.3,
                "e_hull": 0.0,
                "source": "test",
            },
        ]
    )
    candidate_path = tmp_path / "composition_candidates.csv"
    candidates.to_csv(candidate_path, index=False)

    groups, report = match_structure_candidates(candidate_path, [condensed_dir])

    assert groups == []
    assert report["missing_descriptions"] == 1
    assert report["missing_material_ids"] == ["mp-missing"]
    assert report["partial_run"]
    assert report["candidate_materials"] == 2
    assert report["available_materials"] == 1
    assert report["description_coverage"] == 0.5


def test_match_structure_candidates_reports_invalid_descriptions(tmp_path):
    condensed_dir = tmp_path / "condensed"
    condensed_dir.mkdir()
    dumpfn({"formula": "CaS"}, condensed_dir / "mp-1.json")
    dumpfn(_condensed("CaSe", "Se"), condensed_dir / "mp-2.json")

    candidates = pd.DataFrame(
        [
            {
                "template": "CaX1",
                "material_id": "mp-1",
                "x_element": "S",
                "formula": "CaS",
                "composition": "CaS",
                "band_gap": 0.0,
                "e_hull": 0.0,
                "source": "test",
            },
            {
                "template": "CaX1",
                "material_id": "mp-2",
                "x_element": "Se",
                "formula": "CaSe",
                "composition": "CaSe",
                "band_gap": 0.3,
                "e_hull": 0.0,
                "source": "test",
            },
        ]
    )

    groups, report = match_structure_candidates(candidates, [condensed_dir])

    assert groups == []
    assert report["invalid_descriptions"] == 1
    assert report["invalid_material_ids"] == ["mp-1"]


def test_partial_matching_freezes_membership_and_records_corrupt_json(tmp_path, monkeypatch):
    import ssscreen.pair.structure_match as matching

    dumpfn(_condensed("CaS", "S"), tmp_path / "mp-1.json")
    dumpfn(_condensed("CaSe", "Se"), tmp_path / "mp-2.json")
    (tmp_path / "mp-bad.json").write_text("{broken")
    candidates = pd.DataFrame(
        [
            {"template": "CaX1", "material_id": mid, "x_element": x, "band_gap": 0.3}
            for mid, x in [("mp-1", "S"), ("mp-2", "Se"), ("mp-bad", "O"), ("mp-late", "Te")]
        ]
    )
    original = matching.find_unique_envs

    def add_new_file(items):
        dumpfn(_condensed("CaTe", "Te"), tmp_path / "mp-late.json")
        return original(items)

    monkeypatch.setattr(matching, "find_unique_envs", add_new_file)
    groups, report = match_structure_candidates(candidates, [tmp_path])
    assert len(groups) == 1
    assert groups[0].mp_ids == ["mp-1", "mp-2"]
    assert report["partial_run"]
    assert report["candidate_materials"] == 4
    assert report["available_materials"] == 2
    assert report["missing_material_ids"] == ["mp-late"]
    assert report["invalid_material_ids"] == ["mp-bad"]
