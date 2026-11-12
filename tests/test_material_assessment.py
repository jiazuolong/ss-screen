"""Stage 13 threshold boundaries and conservative aggregation of valid evidence."""

from copy import deepcopy

import pytest

from ssscreen.detector import assess_candidate, assess_rows, export_rows, read_csv
from ssscreen.geometry_pipeline import (
    DEFAULT_CONFIG,
    _endpoint_gap_summary,
    _property_summary,
)
from ssscreen.material_assessment import (
    PHOTON_ENERGY_EV_UM,
    assess_endpoint_gap_range,
    summarize_material_evidence,
)


def evidence(count=2):
    candidate = {
        "candidate_id": "test",
        "reference_set_id": "ref",
        "actual_fraction_b": "0.5",
        "expected_structure_ids": ";".join(f"s{i}" for i in range(count)),
    }
    structures = [
        dict(
            candidate,
            structure_id=f"s{i}",
            sha256=f"sha-{i}",
            status="success",
            qc_status="pass",
        )
        for i in range(count)
    ]
    properties = [
        dict(
            candidate,
            structure_id=f"s{i}",
            structure_sha256=f"sha-{i}",
            status="success",
            qc_status="pass",
            band_gap_eV="0.6",
            minimum_mesh_frequency_THz="0.1",
            mixing_enthalpy_meV_per_atom="25",
            energy_above_hull_eV_per_atom="0.025",
        )
        for i in range(count)
    ]
    config = deepcopy(DEFAULT_CONFIG)
    config["gap_target_eV"] = [0.5, 0.7]
    return candidate, properties, config, structures


@pytest.mark.parametrize(
    "field,value,status_key,expected",
    [
        ("minimum_mesh_frequency_THz", -0.1, "phonon_status", "通过"),
        ("minimum_mesh_frequency_THz", -0.10001, "phonon_status", "显著虚频"),
        ("mixing_enthalpy_meV_per_atom", 25, "mixing_status", "优先"),
        ("mixing_enthalpy_meV_per_atom", 25.001, "mixing_status", "备选"),
        ("mixing_enthalpy_meV_per_atom", 50, "mixing_status", "备选"),
        ("mixing_enthalpy_meV_per_atom", 50.001, "mixing_status", "高风险"),
        ("energy_above_hull_eV_per_atom", 0.025, "hull_status", "优先"),
        ("energy_above_hull_eV_per_atom", 0.025001, "hull_status", "备选"),
        ("energy_above_hull_eV_per_atom", 0.1, "hull_status", "备选"),
        ("energy_above_hull_eV_per_atom", 0.100001, "hull_status", "高风险"),
    ],
)
def test_threshold_inclusive_boundaries(field, value, status_key, expected):
    candidate, properties, config, structures = evidence()
    properties[1][field] = str(value)
    result = _property_summary(candidate, properties, config, structures)
    assert result[status_key] == expected
    if field == "energy_above_hull_eV_per_atom":
        assert result["energy_above_hull_meV_atom"] == pytest.approx(value * 1000)


@pytest.mark.parametrize(
    "a,b,wavelength,status",
    [
        (0, 0.7877, 2, "优先"),
        (0.7877, 0, 2, "优先"),
        (0, 0.7877, 1, "次优"),
        (PHOTON_ENERGY_EV_UM / 2, 0.8, 2, "优先"),
        (0, PHOTON_ENERGY_EV_UM / 2, 2, "优先"),
        (None, 0.7877, 2, "待补充"),
        (-0.1, 0.8, 2, "待补充"),
        (float("nan"), 0.8, 2, "待补充"),
        (0, 0.8, None, "待补充"),
    ],
)
def test_endpoint_range_only_closed_bounds_and_missingness(a, b, wavelength, status):
    result = assess_endpoint_gap_range(a, b, wavelength)
    assert result["gap_target_status"] == status
    assert "alloy_gap_eV" not in result


def test_cli_endpoint_evidence_identity_conflict_and_zero():
    candidate, _, config, _ = evidence(1)
    candidate.update(stage12_pair_index="0", comp_a="CaSe", comp_b="CaTe")
    config["detector_context"]["target_wavelength_um"] = 2
    rows = [
        dict(
            pair_index="0",
            actual_fraction_b="0.5",
            comp_a="CaSe",
            comp_b="CaTe",
            gap_a_eV="0.7877",
            gap_b_eV="0",
        )
    ]
    assert _endpoint_gap_summary(candidate, rows, config)["gap_target_status"] == "优先"
    assert (
        _endpoint_gap_summary(candidate, [dict(rows[0], pair_index="1")], config)[
            "gap_target_status"
        ]
        == "待补充"
    )
    assert (
        _endpoint_gap_summary(
            candidate, rows + [dict(rows[0], gap_a_eV="0.1")], config
        )["gap_target_status"]
        == "待核验"
    )
    candidate.update(gap_a_eV=0.7877, gap_b_eV=0)
    assert _endpoint_gap_summary(candidate, [], config)["gap_target_status"] == "优先"
    frontend = assess_rows(rows + [dict(rows[0], gap_a_eV="0.1")], 2)
    assert frontend[0]["gap_target_status"] == "待核验"
    assert frontend[0]["band_match"] == "端元带隙来源冲突"


@pytest.mark.parametrize("fault", ["property_qc", "structure_qc", "sha", "missing"])
def test_invalid_or_missing_configuration_cannot_pass(fault):
    candidate, properties, config, structures = evidence()
    if fault == "property_qc":
        properties[1]["qc_status"] = "insufficient_sampling"
    elif fault == "structure_qc":
        structures[1]["qc_status"] = "fail"
    elif fault == "sha":
        properties[1]["structure_sha256"] = "different-structure"
    else:
        properties.pop()
    result = _property_summary(candidate, properties, config, structures)
    assert result["gap_valid_configuration_count"] == 1
    assert result["gap_status"] != "有效"
    assert (
        result["phonon_status"]
        == result["mixing_status"]
        == result["hull_status"]
        == "待补充"
    )


@pytest.mark.parametrize("long_form", [False, True])
def test_incomplete_competing_set_cannot_pass(long_form):
    candidate, properties, config, structures = evidence(1)
    properties[0]["competing_set_complete"] = "false"
    if long_form:
        properties[0].update(property="energy_above_hull_eV_per_atom", value="0.001")
    result = _property_summary(candidate, properties, config, structures)
    assert result["hull_status"] == "待补充"
    assert result["energy_above_hull_meV_atom"] is None


def test_six_dimensions_risk_and_missingness_are_independent(tmp_path):
    result = _property_summary(*evidence())
    result.update(
        lattice_status="优先", substrate_status="优先", gap_target_status="优先"
    )
    assert summarize_material_evidence(result)["candidate_grade"] == "优先进一步验证"
    result["mixing_status"] = "备选"
    assert summarize_material_evidence(result)["candidate_grade"] == "备选/需复核"
    result["gap_target_status"] = "待补充"
    assert summarize_material_evidence(result)["candidate_grade"] == "待补充"
    result.update(
        candidate_id="test", actual_fraction_b="0.5", phonon_status="显著虚频"
    )
    result["substrate_status"] = "待补充"
    row = assess_candidate(
        {
            "candidate_id": "test",
            "actual_fraction_b": "0.5",
            "gap_a_eV": "0.8",
            "gap_b_eV": "0",
        },
        2.0,
        result,
    )
    assert row["candidate_grade"] == "优先"  # Endpoint range only.
    assert row["material_grade"] == "降低优先级"
    assert row["evidence_completeness"] == "部分缺失"
    assert "显著虚频" in row["material_reason"]
    output = tmp_path / "assessment.csv"
    export_rows(output, [row])
    saved = read_csv(output)[0]
    assert saved["material_grade"] == "降低优先级"
    assert saved["gap_valid_configuration_count"] == "2"


@pytest.mark.parametrize(
    "risk,status_key,value_key,value,display_key,display_status",
    [
        (
            "phonon:unstable",
            "phonon_status",
            "minimum_mesh_frequency_THz",
            -0.3,
            "phonon_status",
            "显著虚频",
        ),
        (
            "mixing:above_low_priority_threshold",
            "mixing_status",
            "mixing_enthalpy_meV_per_atom",
            60,
            "mixing_status",
            "高风险",
        ),
        (
            "phase:above_low_priority_threshold",
            "phase_status",
            "energy_above_hull_eV_per_atom",
            0.2,
            "hull_status",
            "高风险",
        ),
    ],
)
def test_stage12_negative_evidence_survives_missing_geometry(
    risk, status_key, value_key, value, display_key, display_status, tmp_path
):
    source = {
        "candidate_id": "C",
        "actual_fraction_b": "0.5",
        "gap_a_eV": "0.05",
        "gap_b_eV": "0.2",
        "competing_set_complete": "True",
        "risks": '["' + risk + '"]',
        status_key: "success",
        value_key: value,
    }
    result = assess_candidate(source, 10)
    assert result[display_key] == display_status
    assert result["material_grade"] == "降低优先级"
    assert result["evidence_completeness"] == "部分缺失"
    assert result["lattice_mismatch_pct"] is None
    output = tmp_path / "assessment.csv"
    export_rows(output, [result])
    assert read_csv(output)[0]["material_grade"] == "降低优先级"
    # A stale numeric value or risk string from a failed computation is not evidence.
    source[status_key] = "failed"
    assert assess_candidate(source, 10)["material_grade"] == "待补充"
    if status_key == "phase_status":
        source[status_key] = "success"
        source["competing_set_complete"] = "False"
        assert assess_candidate(source, 10)["material_grade"] == "待补充"


def test_optional_alloy_evidence_cannot_block_endpoint_rule():
    result = _property_summary(*evidence())
    result.pop("gap_valid_configuration_count")
    result.update(
        candidate_id="test",
        actual_fraction_b="0.5",
        lattice_status="优先",
        substrate_status="优先",
    )
    row = assess_candidate(
        {
            "candidate_id": "test",
            "actual_fraction_b": "0.5",
            "gap_a_eV": 0.8,
            "gap_b_eV": 0,
        },
        2,
        result,
    )
    assert row["material_grade"] == "优先进一步验证"
    assert row["evidence_completeness"] == "完整"
    assert row["gap_status"] == "构型数量待核验"


def test_changing_wavelength_reassesses_cached_geometry_grade():
    geometry = dict(
        candidate_id="test",
        actual_fraction_b="0.5",
        gap_target_status="待补充",
        lattice_status="优先",
        phonon_status="通过",
        mixing_status="优先",
        hull_status="优先",
        substrate_status="优先",
    )
    source = dict(
        candidate_id="test", actual_fraction_b="0.5", gap_a_eV="0.7877", gap_b_eV="0"
    )
    covered = assess_candidate(source, 2, geometry)
    assert covered["alloy_gap_eV"] is None
    assert covered["material_grade"] == "优先进一步验证"
    uncovered = assess_candidate(source, 1, geometry)
    assert uncovered["gap_target_status"] == "次优"
    assert uncovered["material_grade"] == "备选/需复核"
    assert uncovered["evidence_completeness"] == "完整"


def test_geometry_cli_forwards_current_target(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from ssscreen import geometry_cli

    config = tmp_path / "config.json"
    config.write_text("{}")
    captured = {}

    def fake_evaluate(*args, **kwargs):
        captured.update(kwargs)
        return {"candidate_count": 0, "matching_solutions": 0}

    monkeypatch.setattr(geometry_cli, "evaluate", fake_evaluate)
    result = CliRunner().invoke(
        geometry_cli.main,
        [
            "--input",
            str(tmp_path),
            "--config",
            str(config),
            "--output",
            str(tmp_path / "out"),
            "--target-wavelength-um",
            "1.55",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["target_wavelength_um"] == 1.55
