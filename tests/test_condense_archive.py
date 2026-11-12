"""Tests for Stage 2 condensed-structure archive helpers."""

from __future__ import annotations

import json

import pandas as pd
from monty.serialization import loadfn
from pymatgen.core import Lattice, Structure

from ssscreen.data.condense import (
    build_archive_index,
    condense_dataframe,
    condense_materials,
    condense_paths,
    validate_archive,
)


def _structure() -> Structure:
    return Structure(Lattice.cubic(5.4), ["Ca", "S"], [[0, 0, 0], [0.5, 0.5, 0.5]])


def _condensed(formula: str = "CaS") -> dict:
    return {
        "formula": formula,
        "spg_symbol": "Fm-3m",
        "crystal_system": "cubic",
        "mineral": {"type": "Halite"},
        "dimensionality": 3,
        "sites": [],
        "distances": {},
        "angles": {},
        "nnn_distances": {},
        "components": [],
        "component_makeup": {},
        "vdw_heterostructure_info": None,
    }


def test_condense_materials_writes_json_manifest_and_index(tmp_path):
    calls = []

    def fake_condense(structure, condenser=None):
        calls.append(structure.composition.reduced_formula)
        return _condensed(structure.composition.reduced_formula)

    output_dir = tmp_path / "condensed"
    manifest = tmp_path / "manifest.jsonl"
    index = tmp_path / "index.csv"

    summary = condense_materials(
        [("mp-1", _structure())],
        output_dir,
        manifest_path=manifest,
        index_path=index,
        condense_func=fake_condense,
    )

    assert summary.written == 1
    assert summary.skipped == 0
    assert summary.failed == 0
    assert calls == ["CaS"]

    condensed = loadfn(output_dir / "mp-1.json")
    assert condensed["formula"] == "CaS"

    manifest_record = json.loads(manifest.read_text().strip())
    assert manifest_record["material_id"] == "mp-1"
    assert manifest_record["status"] == "written"
    assert manifest_record["formula"] == "CaS"
    assert manifest_record["output_path"].endswith("mp-1.json")
    assert manifest_record["sha256"]

    index_df = pd.read_csv(index)
    assert list(index_df["material_id"]) == ["mp-1"]
    assert list(index_df["status"]) == ["written"]
    assert list(index_df["formula"]) == ["CaS"]


def test_condense_materials_skips_existing_by_default(tmp_path):
    output_dir = tmp_path / "condensed"
    output_dir.mkdir()
    existing = output_dir / "mp-1.json"
    existing.write_text('{"formula": "old"}')

    def fail_if_called(structure, condenser=None):
        raise AssertionError("existing file should be skipped")

    summary = condense_materials(
        [("mp-1", _structure())],
        output_dir,
        condense_func=fail_if_called,
    )

    assert summary.written == 0
    assert summary.skipped == 1
    assert summary.failed == 0
    assert existing.read_text() == '{"formula": "old"}'


def test_condense_paths_records_input_load_failures(tmp_path, monkeypatch):
    bad_input = tmp_path / "bad.cif"
    bad_input.write_text("not a structure")
    manifest = tmp_path / "manifest.jsonl"
    index = tmp_path / "index.csv"

    monkeypatch.setattr(
        "ssscreen.data.condense._make_condenser",
        lambda: object(),
    )

    summary = condense_paths(
        [bad_input],
        tmp_path / "condensed",
        manifest_path=manifest,
        index_path=index,
    )

    assert summary.written == 0
    assert summary.skipped == 0
    assert summary.failed == 1
    record = json.loads(manifest.read_text().strip())
    assert record["material_id"] == "bad"
    assert record["status"] == "failed"
    assert record["source_path"] == str(bad_input)
    assert record["output_path"].endswith("bad.json")
    assert record["error"]


def test_condense_dataframe_uses_dataframe_index_as_material_id(tmp_path):
    df = pd.DataFrame(
        [{"structure": _structure(), "formula": "CaS"}],
        index=pd.Index(["mp-1"], name="material_id"),
    )
    df_path = tmp_path / "dataset.df"
    df.to_pickle(df_path)

    summary = condense_dataframe(
        df_path,
        tmp_path / "condensed",
        condense_func=lambda structure, condenser=None: _condensed("CaS"),
    )

    assert summary.written == 1
    assert (tmp_path / "condensed" / "mp-1.json").exists()


def test_condense_dataframe_reuses_one_structure_condenser(tmp_path, monkeypatch):
    df = pd.DataFrame(
        [{"structure": _structure()}, {"structure": _structure()}],
        index=pd.Index(["mp-1", "mp-2"], name="material_id"),
    )
    df_path = tmp_path / "dataset.df"
    df.to_pickle(df_path)
    factory_calls = []

    class FakeCondenser:
        def condense_structure(self, structure):
            return _condensed(structure.composition.reduced_formula)

    def fake_factory():
        factory_calls.append(True)
        return FakeCondenser()

    monkeypatch.setattr("ssscreen.data.condense._make_condenser", fake_factory)

    summary = condense_dataframe(df_path, tmp_path / "condensed")

    assert summary.written == 2
    assert factory_calls == [True]


def test_build_archive_index_and_validate_archive(tmp_path):
    output_dir = tmp_path / "condensed"
    output_dir.mkdir()
    from monty.serialization import dumpfn

    dumpfn(_condensed("CaS"), output_dir / "mp-1.json")
    (output_dir / "broken.json").write_text('{"formula": "Broken"}')

    index = build_archive_index(output_dir, tmp_path / "index.csv")

    assert set(index["material_id"]) == {"mp-1", "broken"}
    assert set(index["status"]) == {"present"}

    validation = validate_archive(output_dir, index_path=tmp_path / "validation.csv")

    records = {row.material_id: row for row in validation.itertuples(index=False)}
    assert records["mp-1"].status == "valid"
    assert records["broken"].status == "invalid"
    assert "sites" in records["broken"].error


def test_stop_preserves_success_failures_and_resumes_without_overwriting(tmp_path):
    stop = tmp_path / "request.stop"
    manifest, index = tmp_path / "manifest.jsonl", tmp_path / "index.csv"
    output = tmp_path / "condensed"
    materials = [(f"mp-{i}", _structure()) for i in range(4)]
    calls = []

    def calculate(structure, condenser=None):
        calls.append(True)
        if len(calls) == 2:
            # First success is already durable while the next item runs.
            assert len(manifest.read_text().splitlines()) == 1
            raise ValueError("sample failure")
        if len(calls) == 3:
            stop.touch()
        return _condensed()

    summary = condense_materials(
        materials,
        output,
        condense_func=calculate,
        manifest_path=manifest,
        index_path=index,
        stop_file=stop,
    )
    assert summary.stopped and summary.pending == 1
    assert (summary.written, summary.failed) == (2, 1)
    assert list(pd.read_csv(index).status) == ["written", "failed", "written"]
    assert not (output / "mp-3.json").exists()
    before = {p.name: p.read_bytes() for p in output.glob("*.json")}
    stop.unlink()
    resumed = condense_materials(
        materials,
        output,
        condense_func=lambda *args, **kwargs: _condensed(),
        manifest_path=manifest,
        index_path=index,
        stop_file=stop,
    )
    assert not resumed.stopped and resumed.pending == 0
    assert (resumed.written, resumed.skipped, resumed.failed) == (2, 2, 0)
    assert all((output / name).read_bytes() == data for name, data in before.items())


def test_interrupt_flushes_completed_records_and_empty_stop_writes_readable_index(tmp_path):
    calls = []

    def interrupted(structure, condenser=None):
        calls.append(True)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return _condensed()

    manifest, index = tmp_path / "manifest.jsonl", tmp_path / "index.csv"
    materials = [("mp-1", _structure()), ("mp-2", _structure())]
    summary = condense_materials(
        materials,
        tmp_path / "condensed",
        condense_func=interrupted,
        manifest_path=manifest,
        index_path=index,
    )
    assert summary.stopped and summary.written == 1 and summary.pending == 1
    assert list(pd.read_csv(index).material_id) == ["mp-1"]
    assert len(manifest.read_text().splitlines()) == 1
    stop = tmp_path / "stop"
    stop.touch()
    summary = condense_materials(
        materials,
        tmp_path / "empty",
        condense_func=interrupted,
        manifest_path=manifest,
        index_path=index,
        stop_file=stop,
    )
    assert summary.stopped and summary.pending == 2
    assert len(calls) == 2
    assert pd.read_csv(index).empty
