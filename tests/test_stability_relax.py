"""Tests for Stage 7 manifest-driven MLP relaxation artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from monty.serialization import dumpfn, loadfn
from pymatgen.core import Lattice, Structure

from ssscreen.stability.mlp import RelaxationOutcome
from ssscreen.stability.relax import build_relaxation_tasks, relax_manifest


def _structure(species: tuple[str, str] = ("Ca", "S"), lattice: float = 5.6) -> Structure:
    return Structure(
        Lattice.cubic(lattice),
        list(species),
        [[0, 0, 0], [0.5, 0.5, 0.5]],
    )


def _write_structure(path: Path, structure: Structure) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dumpfn(structure, path)


def _write_manifest(tmp_path: Path, *, duplicate: bool = False) -> Path:
    sqs_a = tmp_path / "sqs-a.json"
    sqs_b = tmp_path / "sqs-b.json"
    endpoint_a = tmp_path / "endpoint-a.json"
    endpoint_b = tmp_path / "endpoint-b.json"
    _write_structure(sqs_a, _structure(("Ca", "S")))
    _write_structure(sqs_b, _structure(("Ca", "Se")))
    _write_structure(endpoint_a, _structure(("Ca", "S")))
    _write_structure(endpoint_b, _structure(("Ca", "Se"), lattice=5.8))
    records = [
        {
            "status": "written",
            "pair_index": 3,
            "mp_id_a": "mp-cas",
            "mp_id_b": "mp-case",
            "comp_a": "CaS",
            "comp_b": "CaSe",
            "target_fraction_b": 0.5,
            "structure_path": str(sqs_a),
            "endpoint_a_structure_path": str(endpoint_a),
            "endpoint_b_structure_path": str(endpoint_b),
        }
    ]
    if duplicate:
        records.append({**records[0], "pair_index": 4, "structure_path": str(sqs_b)})
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("".join(json.dumps(record) + "\n" for record in records))
    return manifest


class FakeBackend:
    def __init__(self, *, converged: bool = True, fail: bool = False) -> None:
        self.converged = converged
        self.fail = fail
        self.calls = 0

    @property
    def metadata(self):
        return {
            "name": "fake",
            "version": "1",
            "model_name": "fixture",
            "model_sha256": "abc123",
            "device": "cpu",
            "dtype": "float64",
        }

    def relax(self, structure, *, fmax, max_steps, relax_cell):
        self.calls += 1
        if self.fail:
            raise RuntimeError("fixture failure")
        relaxed = structure.copy()
        relaxed.scale_lattice(structure.volume * 1.01)
        return RelaxationOutcome(
            structure=relaxed,
            initial_energy_total_ev=-3.0,
            energy_total_ev=-4.0,
            forces_ev_per_angstrom=[[0.01, 0.0, 0.0], [0.0, -0.02, 0.0]],
            stress_ev_per_angstrom3=[
                [0.001, 0.0, 0.0],
                [0.0, 0.002, 0.0],
                [0.0, 0.0, 0.003],
            ],
            steps=7,
            converged=self.converged,
        )


def test_build_relaxation_tasks_deduplicates_endmembers(tmp_path):
    tasks = build_relaxation_tasks(
        manifest_path=_write_manifest(tmp_path, duplicate=True),
        output_dir=tmp_path / "relax",
        include_endmembers=True,
    )

    assert [task.structure_role for task in tasks].count("sqs") == 2
    assert [task.structure_role for task in tasks].count("endmember") == 2
    assert len({task.structure_id for task in tasks}) == 4


def test_build_relaxation_tasks_preserves_actual_fraction_metadata(tmp_path):
    manifest = _write_manifest(tmp_path)
    record = json.loads(manifest.read_text())
    record.update(
        {
            "actual_fraction_b": 0.25,
            "replaced_sites": 1,
            "available_substitution_sites": 4,
        }
    )
    manifest.write_text(json.dumps(record) + "\n")

    tasks = build_relaxation_tasks(
        manifest_path=manifest,
        output_dir=tmp_path / "relax",
    )

    assert tasks[0].metadata["actual_fraction_b"] == 0.25
    assert tasks[0].metadata["replaced_sites"] == 1
    assert tasks[0].metadata["available_substitution_sites"] == 4


def test_build_relaxation_tasks_rejects_manifest_hash_mismatch(tmp_path):
    manifest = _write_manifest(tmp_path)
    record = json.loads(manifest.read_text())
    record["structure_sha256"] = "0" * 64
    manifest.write_text(json.dumps(record) + "\n")

    with pytest.raises(ValueError, match="SHA-256 differs from manifest"):
        build_relaxation_tasks(
            manifest_path=manifest,
            output_dir=tmp_path / "relax",
        )


def test_relax_manifest_writes_complete_results_and_resumes(tmp_path):
    backend = FakeBackend()
    output_dir = tmp_path / "relax"
    results = output_dir / "results.jsonl"
    kwargs = {
        "manifest_path": _write_manifest(tmp_path),
        "output_dir": output_dir,
        "results_path": results,
        "backend": backend,
        "include_endmembers": True,
    }

    records = relax_manifest(**kwargs)

    assert backend.calls == 3
    assert {record["status"] for record in records} == {"success"}
    sqs_record = next(record for record in records if record["structure_role"] == "sqs")
    assert sqs_record["energy_total_eV"] == -4.0
    assert sqs_record["energy_per_atom_eV"] == -2.0
    assert sqs_record["forces_eV_per_angstrom"] == [
        [0.01, 0.0, 0.0],
        [0.0, -0.02, 0.0],
    ]
    assert sqs_record["max_force_eV_per_angstrom"] == pytest.approx(0.02)
    assert sqs_record["stress_eV_per_angstrom3"][2][2] == pytest.approx(0.003)
    assert sqs_record["stress_GPa"][2][2] == pytest.approx(0.48065298624)
    assert sqs_record["steps"] == 7
    assert sqs_record["quality_control"]["passed"] is True
    assert sqs_record["usable_for_thermodynamics"] is True
    assert loadfn(sqs_record["output_structure"]["path"]).volume == pytest.approx(
        _structure().volume * 1.01
    )
    assert len(results.read_text().splitlines()) == 3

    resumed = relax_manifest(**kwargs)
    assert backend.calls == 3
    assert resumed == records


def test_gui_relaxation_handoff_checks_current_evidence(tmp_path):
    from ssscreen.gui.relax_results import relaxation_status
    from ssscreen.gui.sqs_results import file_sha256

    manifest = _write_manifest(tmp_path)
    pairs = tmp_path / "pairs.csv"
    pd.DataFrame(
        [{"mp_id_a": "mp-cas", "mp_id_b": "mp-case", "comp_a": "CaS", "comp_b": "CaSe"}] * 4
    ).to_csv(pairs, index=False)
    model = tmp_path / "fixture.model"
    model.write_bytes(b"fake model for GUI tests only")

    class Backend(FakeBackend):
        @property
        def metadata(self):
            return {**super().metadata, "model_sha256": file_sha256(model)}

    output, results = tmp_path / "relax", tmp_path / "results.jsonl"
    records = relax_manifest(
        manifest_path=manifest,
        output_dir=output,
        results_path=results,
        backend=Backend(),
        include_endmembers=True,
        fmax=0.03,
        max_steps=77,
    )
    params = {
        "backend": "fake",
        "model_path": str(model),
        "model_name": "fixture",
        "dtype": "float64",
        "fmax": 0.03,
        "max_steps": 77,
        "relax_cell": True,
    }

    def status(parameters=None, external=False):
        return relaxation_status(
            tmp_path,
            str(manifest),
            str(pairs),
            str(results),
            str(output),
            parameters or params,
            external=external,
        )

    assert status()["ready"] and status()["usable_pairs"] == 1
    assert status()["evidence_valid"] and status()["usable_sqs"] == 1
    assert not status({**params, "fmax": 0.04})["ready"]
    for changed in (
        model,
        Path(records[0]["input_structure"]["path"]),
        Path(records[0]["output_structure"]["path"]),
    ):
        original = changed.read_bytes()
        changed.write_bytes(original + b"\n")
        assert not status()["ready"]
        changed.write_bytes(original)
    original_results = results.read_text()
    results.write_text(
        "\n".join(json.dumps(row) for row in records if row["structure_role"] == "sqs")
    )
    assert not status()["ready"]  # No endpoint energies.
    assert status()["evidence_valid"] and status()["usable_sqs"] == 1  # Phonons can use SQS only.
    results.write_text(original_results)
    assert status({**params, "model_path": "remote.model"}, external=True)["ready"]
    records = [json.loads(line) for line in original_results.splitlines()]
    records[-1]["backend"]["model_sha256"] = "different-model"
    results.write_text("\n".join(json.dumps(row) for row in records))
    assert not status({**params, "model_path": "remote.model"}, external=True)["ready"]
    results.write_text(original_results)
    records = [json.loads(line) for line in original_results.splitlines()]
    records[0]["status"] = "not_converged"
    records[0]["usable_for_thermodynamics"] = False
    results.write_text("\n".join(json.dumps(row) for row in records))
    assert status()["not_converged"] == 1 and not status()["ready"]
    results.write_text(original_results)
    wrong_pairs = pd.read_csv(pairs)
    wrong_pairs.loc[3, "mp_id_a"] = "another-material"
    wrong_pairs.to_csv(pairs, index=False)
    assert not status()["ready"]


def test_relax_manifest_marks_not_converged_as_unusable(tmp_path):
    records = relax_manifest(
        manifest_path=_write_manifest(tmp_path),
        output_dir=tmp_path / "relax",
        results_path=tmp_path / "results.jsonl",
        backend=FakeBackend(converged=False),
    )

    assert records[0]["status"] == "not_converged"
    assert records[0]["converged"] is False
    assert records[0]["usable_for_thermodynamics"] is False
    assert Path(records[0]["output_structure"]["path"]).is_file()


def test_relax_manifest_records_backend_failure(tmp_path):
    records = relax_manifest(
        manifest_path=_write_manifest(tmp_path),
        output_dir=tmp_path / "relax",
        results_path=tmp_path / "results.jsonl",
        backend=FakeBackend(fail=True),
    )

    assert records[0]["status"] == "failed"
    assert records[0]["error"] == "RuntimeError: fixture failure"
    assert records[0]["usable_for_thermodynamics"] is False


def test_relax_manifest_rejects_resume_with_different_settings(tmp_path):
    manifest = _write_manifest(tmp_path)
    output_dir = tmp_path / "relax"
    results = tmp_path / "results.jsonl"
    relax_manifest(
        manifest_path=manifest,
        output_dir=output_dir,
        results_path=results,
        backend=FakeBackend(),
        fmax=0.03,
    )

    with pytest.raises(ValueError, match="settings differ"):
        relax_manifest(
            manifest_path=manifest,
            output_dir=output_dir,
            results_path=results,
            backend=FakeBackend(),
            fmax=0.05,
        )


def test_old_manifest_can_load_endmembers_from_dataset(tmp_path):
    from ssscreen.gui.relax_results import relaxation_status, requires_endpoint_dataset

    manifest = _write_manifest(tmp_path)
    assert not requires_endpoint_dataset(manifest)
    record = json.loads(manifest.read_text())
    record.pop("endpoint_a_structure_path")
    record.pop("endpoint_b_structure_path")
    manifest.write_text(json.dumps(record) + "\n")
    assert requires_endpoint_dataset(manifest)
    dataset = pd.DataFrame(
        [
            {"material_id": "mp-cas", "structure": _structure(("Ca", "S"))},
            {"material_id": "mp-case", "structure": _structure(("Ca", "Se"))},
        ]
    ).set_index("material_id")
    dataset_path = tmp_path / "dataset.df"
    dataset.to_pickle(dataset_path)

    tasks = build_relaxation_tasks(
        manifest_path=manifest,
        output_dir=tmp_path / "relax",
        include_endmembers=True,
        dataset_path=dataset_path,
    )

    assert len(tasks) == 3
    assert all(task.structure_path.is_file() for task in tasks)
    output = tmp_path / "relax"
    results = output / "results.jsonl"
    relax_manifest(
        manifest_path=manifest,
        output_dir=output,
        results_path=results,
        dataset_path=dataset_path,
        include_endmembers=True,
        backend=FakeBackend(),
        fmax=0.03,
        max_steps=77,
    )
    pairs = tmp_path / "pairs.csv"
    pd.DataFrame([{"mp_id_a": "mp-cas", "mp_id_b": "mp-case"}] * 4).to_csv(pairs, index=False)
    params = {
        "backend": "fake",
        "model_path": "remote.model",
        "dtype": "float64",
        "fmax": 0.03,
        "max_steps": 77,
        "relax_cell": True,
        "dataset_path": dataset_path,
    }

    def status():
        return relaxation_status(
            tmp_path,
            str(manifest),
            str(pairs),
            str(results),
            str(output),
            params,
            external=True,
        )

    assert status()["ready"]
    dataset.loc["mp-cas", "structure"].scale_lattice(300)
    dataset.to_pickle(dataset_path)
    assert not status()["ready"]
