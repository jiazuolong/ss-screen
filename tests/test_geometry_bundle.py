"""Reject mislabeled alloy structures and incomplete relaxation provenance."""

import json
from copy import deepcopy

import pandas as pd
import pytest
from monty.serialization import dumpfn
from pymatgen.core import Composition, Lattice, Structure

from ssscreen.geometry_bundle import digest, validate_relaxed


def test_relaxed_identity_requires_real_alloy(tmp_path):
    path = tmp_path / "pure.json"
    dumpfn(Structure(Lattice.cubic(4), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]]), path)
    record = dict(
        status="success",
        converged=True,
        quality_control={"passed": True},
        settings={"cell_mode": "full"},
        backend={"model_sha256": "model"},
        output_structure={"path": str(path), "sha256": digest(path)},
    )
    assert validate_relaxed(record, Composition("NaCl"), tmp_path)[0] == path
    cpu = deepcopy(record)
    cpu["backend"]["device"] = "cpu"
    gpu = deepcopy(record)
    gpu["backend"]["device"] = "cuda"
    assert (
        validate_relaxed(cpu, Composition("NaCl"), tmp_path)[1]
        == validate_relaxed(gpu, Composition("NaCl"), tmp_path)[1]
    )
    gpu["backend"]["model_sha256"] = "different-model"
    assert (
        validate_relaxed(cpu, Composition("NaCl"), tmp_path)[1]
        != validate_relaxed(gpu, Composition("NaCl"), tmp_path)[1]
    )
    with pytest.raises(ValueError, match="composition"):
        validate_relaxed(record, Composition("NaLiCl2"), tmp_path)
    bad = deepcopy(record)
    bad["settings"] = {}
    with pytest.raises(ValueError, match="provenance"):
        validate_relaxed(bad, Composition("NaCl"), tmp_path)
    path.write_text("changed")
    with pytest.raises(ValueError, match="SHA"):
        validate_relaxed(record, Composition("NaCl"), tmp_path)


def test_build_bundle_selects_actual_seed_and_keeps_invalid_geometry_missing(tmp_path):
    from ssscreen.geometry_bundle import build_bundle
    from ssscreen.geometry_pipeline import evaluate

    pairs = tmp_path / "pairs.csv"
    pd.DataFrame(
        [dict(mp_id_a="a", mp_id_b="b", comp_a="NaCl", comp_b="KCl", gap_a=0, gap_b=1)]
    ).to_csv(pairs, index=False)
    records = []
    for mid, species, coords in [
        ("a", ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]]),
        ("b", ["K", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]]),
        ("alloy", ["Na", "K", "Cl", "Cl"], [[0, 0, 0], [0.5, 0, 0], [0, 0.5, 0], [0.5, 0.5, 0.5]]),
    ]:
        path = tmp_path / f"{mid}.json"
        dumpfn(Structure(Lattice.cubic(5), species, coords), path)
        record = dict(
            status="success",
            converged=True,
            quality_control={"passed": True},
            settings={"cell_mode": "full"},
            backend={"model_sha256": "same-model"},
            output_structure={"path": str(path), "sha256": digest(path)},
            structure_id=mid,
            structure_role="sqs" if mid == "alloy" else "endmember",
            material_id=mid,
            pair_index=0,
            actual_fraction_b=0.5,
            seed=1000104,
            substitution={"from": "Na", "to": "K"},
        )
        records.append(record)
    relaxation = tmp_path / "relax.jsonl"
    relaxation.write_text("\n".join(json.dumps(r) for r in records))
    substrates = tmp_path / "substrates.json"
    substrates.write_text("[]")
    bundle = tmp_path / "input"
    report = build_bundle(pairs, relaxation, substrates, bundle, tmp_path, 10)
    assert report["valid_alloys"] == 1
    assert not report["failures"]
    evaluate(bundle, bundle / "config.json", tmp_path / "output")
    row = pd.read_csv(tmp_path / "output/candidate_evaluation.csv").iloc[0]
    assert row.selected_structure_id == "alloy"
    assert row.selected_seed == 1000104
    assert row.band_match == "端元范围覆盖"
    assert row.substrate_status == "待补充"
    assert row.candidate_grade != "优先进一步验证"
