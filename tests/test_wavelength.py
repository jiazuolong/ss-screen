"""Closed boundaries, bypassed legacy gates, and missing evidence."""

import hashlib
import json

import pandas as pd
import pytest
from click.testing import CliRunner

from ssscreen.data.io import dump_group_df
from ssscreen.material_assessment import PHOTON_ENERGY_EV_UM
from ssscreen.pair.envmatch import StructureGroup
from ssscreen.pair.wavelength import main, screen_wavelength


def test_closed_interval_and_deduplication(tmp_path):
    target = PHOTON_ENERGY_EV_UM / 10
    ids = ["a", "b", "c", "d", "e"]
    group = StructureGroup(
        mp_ids=ids,
        compositions=["CaS", "CaSe", "CaTe", "CaO", "CaPo"],
        group_size=5,
        X_element=["S", "Se", "Te", "O", "Po"],
        A_elements=[["Ca"]] * 5,
        entry_idx=list(range(5)),
        band_gaps=[0] * 5,
        group_repr="test",
    )
    groups = tmp_path / "groups.json"
    dump_group_df([group, group], groups)
    gaps = tmp_path / "gaps.csv"
    pd.DataFrame(
        [
            dict(
                material_id=mid,
                formula=formula,
                method="mbj",
                band_gap=gap,
                is_direct=False,
                transition="",
                status=status,
            )
            for mid, formula, gap, status in zip(
                ids,
                group.compositions,
                [0, target, 1.2, 0.01, None],
                ["success"] * 4 + ["failed"],
                strict=True,
            )
        ]
    ).to_csv(gaps, index=False)
    out, summary = tmp_path / "pairs.csv", tmp_path / "summary.json"
    result = CliRunner().invoke(
        main,
        [
            "--groups",
            str(groups),
            "--gap-results",
            str(gaps),
            "--target-wavelength-um",
            "10",
            "--output",
            str(out),
            "--summary",
            str(summary),
        ],
    )
    assert result.exit_code == 0, result.output
    pairs = pd.read_csv(out)
    keys = {frozenset((r.mp_id_a, r.mp_id_b)) for r in pairs.itertuples()}
    assert keys == {
        frozenset(p) for p in [("a", "b"), ("a", "c"), ("b", "c"), ("b", "d"), ("c", "d")]
    }
    assert all(len(json.loads(v)) == 2 for v in pairs.source_groups)
    report = json.loads(summary.read_text())
    assert report["missing_materials"] == ["e"]
    assert report["input_sha256"] == {
        "groups": [hashlib.sha256(groups.read_bytes()).hexdigest()],
        "gaps": [hashlib.sha256(gaps.read_bytes()).hexdigest()],
    }
    assert report["output_sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_invalid_wavelength(value, tmp_path):
    with pytest.raises(ValueError, match="finite and positive"):
        screen_wavelength((), (), value, None, tmp_path / "out", tmp_path / "summary")


@pytest.mark.parametrize(
    "a,b,kept",
    [
        (0, 0.3, False),
        (0.01, 0.4, False),
        (0.01, 0.400001, False),
        (0.01, 0.399999, True),
        (0.1239841984, 0.3, True),
        (0.01, 0.1239841984, True),
        (0.3, 0.01, True),
        (0.2, 0.3, False),
    ],
)
def test_strict_endpoint_bounds(a, b, kept, tmp_path):
    groups, gaps = tmp_path / "groups.json", tmp_path / "gaps.csv"
    dump_group_df(
        [
            StructureGroup(
                mp_ids=["a", "b"],
                compositions=["CaS", "CaSe"],
                group_size=2,
                X_element=["S", "Se"],
                A_elements=[["Ca"], ["Ca"]],
                entry_idx=[0, 1],
                band_gaps=[0, 0],
                group_repr="test",
            )
        ],
        groups,
    )
    pd.DataFrame(
        [
            dict(
                material_id=mid,
                formula=formula,
                method="mbj",
                band_gap=gap,
                is_direct=False,
                transition="",
                status="success",
            )
            for mid, formula, gap in [("a", "CaS", a), ("b", "CaSe", b)]
        ]
    ).to_csv(gaps, index=False)
    out, summary = tmp_path / "pairs.csv", tmp_path / "summary.json"
    result = CliRunner().invoke(
        main,
        [
            "--groups",
            str(groups),
            "--gap-results",
            str(gaps),
            "--target-wavelength-um",
            "10",
            "--min-gap-exclusive",
            "0",
            "--max-gap-exclusive",
            "0.4",
            "--output",
            str(out),
            "--summary",
            str(summary),
        ],
    )
    assert result.exit_code == 0, result.output
    assert len(pd.read_csv(out)) == int(kept)
    assert json.loads(summary.read_text())["max_gap_exclusive_eV"] == 0.4


def test_mixed_source_override_keeps_provenance_and_rejects_duplicates(tmp_path):
    from ssscreen.pair.gap_feedback import load_gap_results

    groups, gaps = tmp_path / "groups.json", tmp_path / "gaps.csv"
    dump_group_df(
        [
            StructureGroup(
                mp_ids=["cd", "zn"],
                compositions=["CdSnSb2", "ZnSnSb2"],
                group_size=2,
                X_element=["Cd", "Zn"],
                A_elements=[["Sn", "Sb"]] * 2,
                entry_idx=[0, 1],
                band_gaps=[0, 0],
                group_repr="test",
            )
        ],
        groups,
    )
    rows = pd.DataFrame(
        [
            dict(
                material_id=mid,
                formula=formula,
                method=method,
                band_gap=gap,
                is_direct=False,
                transition="",
                status="success",
            )
            for mid, formula, method, gap in [
                ("cd", "CdSnSb2", "source_cd", 0.0894),
                ("zn", "ZnSnSb2", "source_zn", 0.2612),
            ]
        ]
    )
    rows.to_csv(gaps, index=False)
    with pytest.raises(ValueError, match="multiple gap methods"):
        load_gap_results([gaps])
    out, summary = tmp_path / "pairs.csv", tmp_path / "summary.json"
    result = CliRunner().invoke(
        main,
        [
            "--groups",
            str(groups),
            "--gap-results",
            str(gaps),
            "--target-wavelength-um",
            "10",
            "--min-gap-exclusive",
            "0",
            "--max-gap-exclusive",
            "0.4",
            "--allow-mixed-methods",
            "--output",
            str(out),
            "--summary",
            str(summary),
        ],
    )
    assert result.exit_code == 0, result.output
    pair = pd.read_csv(out).iloc[0]
    assert pair.gap_method_a == "source_cd"
    assert pair.gap_method_b == "source_zn"
    assert pair.gap_method == "mixed_sources"
    with pytest.raises(ValueError, match="mutually exclusive"):
        load_gap_results([gaps], method="source_cd", allow_mixed_methods=True)
    duplicate = rows.iloc[[0]].copy()
    duplicate["method"] = "old_cd"
    pd.concat([rows, duplicate]).to_csv(gaps, index=False)
    with pytest.raises(ValueError, match="duplicate successful"):
        load_gap_results([gaps], allow_mixed_methods=True)
