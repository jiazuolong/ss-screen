"""Stage 11 recommendation aggregation, classification, and audit tests."""

from __future__ import annotations

import json

import pandas as pd

from ssscreen.config import RecommendationSettings
from ssscreen.stability.recommendation import generate_recommendations


def test_explicit_mixed_gap_sources_are_found_without_claiming_method_equivalence():
    from ssscreen.stability.recommendation import _Assessment, _evaluate_gap_evidence

    pair = pd.Series(
        dict(
            mp_id_a="a",
            mp_id_b="b",
            gap_a=0.09,
            gap_b=0.26,
            gap_method="mixed_sources",
            gap_method_a="external-a",
            gap_method_b="external-b",
        )
    )
    gaps = pd.DataFrame(
        [
            dict(
                material_id="a",
                method="external-a",
                band_gap=0.09,
                is_direct=True,
                status="success",
            ),
            dict(
                material_id="b",
                method="external-b",
                band_gap=0.26,
                is_direct=False,
                status="success",
            ),
            dict(
                material_id="a",
                method="old-method",
                band_gap=0.57,
                is_direct=False,
                status="success",
            ),
        ]
    )
    assessment = _Assessment()
    result = _evaluate_gap_evidence(
        pair, gaps, method_override=None, settings=RecommendationSettings(), assessment=assessment
    )
    assert result["complete"] and result["gap_evidence_status"] == "complete"
    assert result["gap_a_eV"] == 0.09
    assert not assessment.missing
    assert "gap:mixed_sources" in assessment.uncertain

    pair["gap_method_b"] = "absent-method"
    result = _evaluate_gap_evidence(
        pair,
        gaps,
        method_override=None,
        settings=RecommendationSettings(),
        assessment=_Assessment(),
    )
    assert not result["complete"]
    assert result["gap_evidence_status"] == "missing_source"

    pair["gap_method_b"] = "external-b"
    pair["gap_b"] = 0.3
    result = _evaluate_gap_evidence(
        pair,
        gaps,
        method_override=None,
        settings=RecommendationSettings(),
        assessment=_Assessment(),
    )
    assert not result["complete"]
    assert result["gap_evidence_status"] == "incompatible"


def _write_csv(path, records, columns=None):
    frame = pd.DataFrame.from_records(records, columns=columns)
    frame.to_csv(path, index=False)
    return path


def _complete_inputs(tmp_path):
    pairs = _write_csv(
        tmp_path / "pairs.csv",
        [
            {
                "comp_a": "CaSe",
                "comp_b": "CaS",
                "gap_a": 0.35,
                "gap_b": 0.05,
                "mp_id_a": "mp-a",
                "mp_id_b": "mp-b",
                "gap_direct_a": True,
                "gap_direct_b": False,
                "source_group_index": 0,
                "gap_method": "hse-v1",
            },
            {
                "comp_a": "CaTe",
                "comp_b": "CaS",
                "gap_a": 0.75,
                "gap_b": 0.05,
                "mp_id_a": "mp-c",
                "mp_id_b": "mp-b",
                "gap_direct_a": True,
                "gap_direct_b": False,
                "source_group_index": 0,
                "gap_method": "hse-v1",
            },
        ],
    )
    gaps = _write_csv(
        tmp_path / "gaps.csv",
        [
            {
                "material_id": "mp-a",
                "method": "hse-v1",
                "band_gap": 0.35,
                "is_direct": True,
                "status": "success",
            },
            {
                "material_id": "mp-b",
                "method": "hse-v1",
                "band_gap": 0.05,
                "is_direct": False,
                "status": "success",
            },
            {
                "material_id": "mp-c",
                "method": "hse-v1",
                "band_gap": 0.75,
                "is_direct": True,
                "status": "success",
            },
        ],
    )
    mixing = _write_csv(
        tmp_path / "mixing.csv",
        [
            {
                "pair_index": 0,
                "sqs_structure_id": "sqs-0",
                "target_fraction_b": 0.5,
                "actual_fraction_b": 0.5,
                "fraction_basis": "actual",
                "mixing_enthalpy_meV_per_atom": 10.0,
                "mixing_signal": "endothermic",
                "model_sha256": "model-a",
                "status": "success",
                "usable_for_screening": True,
                "warnings": "",
            },
            {
                "pair_index": 1,
                "sqs_structure_id": "sqs-1",
                "target_fraction_b": 0.5,
                "actual_fraction_b": 0.5,
                "fraction_basis": "actual",
                "mixing_enthalpy_meV_per_atom": 80.0,
                "mixing_signal": "endothermic",
                "model_sha256": "model-a",
                "status": "success",
                "usable_for_screening": True,
                "warnings": "",
            },
        ],
    )
    phonons = _write_csv(
        tmp_path / "phonons.csv",
        [
            {
                "pair_index": 0,
                "structure_id": "sqs-0",
                "structure_role": "sqs",
                "target_fraction_b": 0.5,
                "actual_fraction_b": 0.5,
                "minimum_mesh_frequency_THz": -1e-8,
                "nac_applied": False,
                "model_sha256": "model-a",
                "status": "success",
                "dynamical_status": "stable",
                "warnings": "NAC not applied",
            },
            {
                "pair_index": 1,
                "structure_id": "sqs-1",
                "structure_role": "sqs",
                "target_fraction_b": 0.5,
                "actual_fraction_b": 0.5,
                "minimum_mesh_frequency_THz": -2.7,
                "nac_applied": False,
                "model_sha256": "model-a",
                "status": "success",
                "dynamical_status": "unstable",
                "warnings": "NAC not applied",
            },
        ],
    )
    phases = _write_csv(
        tmp_path / "phases.csv",
        [
            {
                "pair_index": 0,
                "structure_id": "sqs-0",
                "energy_above_hull_eV_per_atom": 0.01,
                "hull_signal": "metastable_within_cutoff",
                "competing_set_complete": True,
                "mp_source_backend": "offline",
                "mp_source_scope": "offline_summary_snapshot",
                "model_sha256": "model-a",
                "status": "success",
                "usable_for_screening": True,
                "warnings": "snapshot scoped",
            },
            {
                "pair_index": 1,
                "structure_id": "sqs-1",
                "energy_above_hull_eV_per_atom": 0.08,
                "hull_signal": "metastable_within_cutoff",
                "competing_set_complete": True,
                "mp_source_backend": "offline",
                "mp_source_scope": "offline_summary_snapshot",
                "model_sha256": "model-a",
                "status": "success",
                "usable_for_screening": True,
                "warnings": "snapshot scoped",
            },
        ],
    )
    return pairs, gaps, mixing, phonons, phases


def _run(tmp_path, inputs, **kwargs):
    pairs, gaps, mixing, phonons, phases = inputs
    output = tmp_path / "recommendations.csv"
    report = tmp_path / "recommendations.md"
    summary = tmp_path / "recommendations.json"
    frame, payload = generate_recommendations(
        pairs_path=pairs,
        gap_results_path=gaps,
        mixing_enthalpy_path=mixing,
        phonons_path=phonons,
        phase_stability_path=phases,
        output_path=output,
        report_path=report,
        summary_path=summary,
        **kwargs,
    )
    return frame, payload, output, report, summary


def test_complete_evidence_ranks_promising_before_explicit_negative_signal(tmp_path):
    frame, summary, output, report, summary_path = _run(tmp_path, _complete_inputs(tmp_path))

    assert list(frame["classification"]) == ["promising", "low-priority"]
    assert list(frame["evidence_level"]) == ["L5", "L5"]
    assert list(frame["rank"]) == [1, 2]
    assert frame.iloc[0]["structure_id"] == "sqs-0"
    assert "phonon:nac_not_applied" in json.loads(frame.iloc[0]["risks"])
    assert json.loads(frame.iloc[0]["missing_data"]) == ["defects:not_requested"]
    assert "mixing:above_low_priority_threshold" in json.loads(frame.iloc[1]["risks"])
    assert "phonon:unstable" in json.loads(frame.iloc[1]["risks"])
    assert summary["classification_counts"] == {"low-priority": 1, "promising": 1}
    assert output.is_file() and summary_path.is_file()
    report_text = report.read_text()
    assert "Decision-support output only" in report_text
    assert "does not establish thermodynamic stability" in report_text


def test_missing_phonon_and_phase_evidence_is_uncertain_and_preserved(tmp_path):
    pairs, gaps, mixing, _phonons, _phases = _complete_inputs(tmp_path)
    pairs = _write_csv(tmp_path / "one-pair.csv", pd.read_csv(pairs).iloc[:1].to_dict("records"))
    mixing = _write_csv(
        tmp_path / "one-mixing.csv", pd.read_csv(mixing).iloc[:1].to_dict("records")
    )
    phonons = _write_csv(
        tmp_path / "empty-phonons.csv",
        [],
        columns=["pair_index", "structure_id", "status", "dynamical_status"],
    )
    phases = _write_csv(
        tmp_path / "empty-phases.csv",
        [],
        columns=[
            "pair_index",
            "structure_id",
            "energy_above_hull_eV_per_atom",
            "hull_signal",
            "status",
            "usable_for_screening",
        ],
    )

    frame, _summary, *_ = _run(tmp_path, (pairs, gaps, mixing, phonons, phases))

    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["classification"] == "uncertain"
    assert row["evidence_level"] == "L4"
    assert set(json.loads(row["missing_data"])) >= {
        "phonon:missing_source",
        "phase:missing_source",
    }


def test_incompatible_mlp_model_hashes_downgrade_to_uncertain(tmp_path):
    pairs, gaps, mixing, phonons, phases = _complete_inputs(tmp_path)
    pairs = _write_csv(tmp_path / "one-pair.csv", pd.read_csv(pairs).iloc[:1].to_dict("records"))
    mixing = _write_csv(
        tmp_path / "one-mixing.csv", pd.read_csv(mixing).iloc[:1].to_dict("records")
    )
    phonon_frame = pd.read_csv(phonons).iloc[:1].copy()
    phonon_frame.loc[:, "model_sha256"] = "model-b"
    phonons = _write_csv(tmp_path / "one-phonon.csv", phonon_frame.to_dict("records"))
    phases = _write_csv(tmp_path / "one-phase.csv", pd.read_csv(phases).iloc[:1].to_dict("records"))

    frame, _summary, *_ = _run(tmp_path, (pairs, gaps, mixing, phonons, phases))

    row = frame.iloc[0]
    assert row["classification"] == "uncertain"
    assert row["evidence_level"] == "L5"
    assert row["model_compatibility_status"] == "incompatible"
    assert "mlp:model_sha256_mismatch" in json.loads(row["risks"])


def test_require_defects_makes_not_requested_evidence_uncertain(tmp_path):
    pairs, gaps, mixing, phonons, phases = _complete_inputs(tmp_path)
    pairs = _write_csv(tmp_path / "one-pair.csv", pd.read_csv(pairs).iloc[:1].to_dict("records"))
    mixing = _write_csv(
        tmp_path / "one-mixing.csv", pd.read_csv(mixing).iloc[:1].to_dict("records")
    )
    phonons = _write_csv(
        tmp_path / "one-phonon.csv", pd.read_csv(phonons).iloc[:1].to_dict("records")
    )
    phases = _write_csv(tmp_path / "one-phase.csv", pd.read_csv(phases).iloc[:1].to_dict("records"))

    frame, _summary, *_ = _run(
        tmp_path,
        (pairs, gaps, mixing, phonons, phases),
        require_defects=True,
    )

    assert frame.iloc[0]["classification"] == "uncertain"
    assert frame.iloc[0]["evidence_level"] == "L5"
    assert "defects:not_requested" in json.loads(frame.iloc[0]["missing_data"])


def test_invalid_threshold_order_is_rejected(tmp_path):
    inputs = _complete_inputs(tmp_path)

    try:
        _run(
            tmp_path,
            inputs,
            settings=RecommendationSettings(
                promising_max_mixing_enthalpy_mev_per_atom=60.0,
                low_priority_mixing_enthalpy_mev_per_atom=50.0,
            ),
        )
    except ValueError as exc:
        assert "promising mixing threshold" in str(exc)
    else:
        raise AssertionError("invalid recommendation settings were accepted")
