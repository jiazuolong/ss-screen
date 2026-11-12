"""Tests for local POSCAR/CIF dataset normalization."""

from __future__ import annotations

import json

import pandas as pd
import pytest
from pymatgen.core import Lattice, Structure

from ssscreen.data.structures import load_structure_dataset


def _write_poscar(path, formula: str) -> None:
    comp = formula.replace("Se", "Q").replace("Te", "R")
    species = (
        comp.replace("Ca", "Ca ").replace("S", "S ").replace("Q", "Se ").replace("R", "Te ").split()
    )
    structure = Structure(Lattice.cubic(5.6), species, [[0, 0, 0], [0.5, 0.5, 0.5]])
    path.parent.mkdir(parents=True, exist_ok=True)
    structure.to(filename=str(path), fmt="poscar")


def test_load_structure_dataset_recurses_poscar_folders(tmp_path):
    root = tmp_path / "inputs"
    _write_poscar(root / "CaS" / "POSCAR", "CaS")
    _write_poscar(root / "CaSe" / "POSCAR", "CaSe")
    output = tmp_path / "local.df"
    provenance = tmp_path / "local.provenance.json"

    df = load_structure_dataset(
        input_dirs=[root],
        output=output,
        band_gap_default=0.2,
        e_hull_default=0.01,
        source="fixture-poscar",
        provenance_path=provenance,
    )

    assert output.exists()
    assert provenance.exists()
    assert list(df.index) == ["CaS", "CaSe"]
    assert set(df["formula"]) == {"CaS", "CaSe"}
    assert df["band_gap"].tolist() == [0.2, 0.2]
    assert df["e_hull"].tolist() == [0.01, 0.01]
    assert df["source"].tolist() == ["fixture-poscar", "fixture-poscar"]


def test_load_structure_dataset_uses_metadata(tmp_path):
    root = tmp_path / "inputs"
    _write_poscar(root / "CaS" / "POSCAR", "CaS")
    metadata = tmp_path / "metadata.csv"
    pd.DataFrame(
        [
            {
                "material_id": "CaS",
                "band_gap": 0.05,
                "e_hull": 0.0,
                "source": "mp-like",
            }
        ]
    ).to_csv(metadata, index=False)

    df = load_structure_dataset(
        input_dirs=[root], output=tmp_path / "local.df", metadata_path=metadata
    )

    assert df.loc["CaS", "band_gap"] == 0.05
    assert df.loc["CaS", "e_hull"] == 0.0
    assert df.loc["CaS", "source"] == "mp-like"


def test_load_structure_dataset_rejects_missing_inputs(tmp_path):
    with pytest.raises(ValueError, match="no supported structure files"):
        load_structure_dataset(input_dirs=[tmp_path], output=tmp_path / "local.df")


@pytest.mark.parametrize("fmt,suffix", [("cif", ".cif"), ("json", ".json"), ("poscar", ".vasp")])
def test_single_structure_formats_and_provenance(tmp_path, fmt, suffix):
    path = tmp_path / f"CaS{suffix}"
    structure = Structure(Lattice.cubic(5.6), ["Ca", "S"], [[0, 0, 0], [0.5, 0.5, 0.5]])
    structure.to(filename=str(path), fmt=fmt)
    provenance = tmp_path / "provenance.json"
    frame = load_structure_dataset(
        inputs=[path, path], output=tmp_path / "local.df", provenance_path=provenance
    )
    assert list(frame.index) == ["CaS"]
    assert frame.loc["CaS", "structure"].composition == structure.composition
    record = json.loads(provenance.read_text())["files"][0]
    assert record["defaulted_fields"] == ["band_gap", "e_hull"]
    assert len(record["sha256"]) == 64


def test_duplicate_material_ids_do_not_overwrite_output(tmp_path):
    for folder in ("one", "two"):
        _write_poscar(tmp_path / folder / "CaS" / "POSCAR", "CaS")
    output = tmp_path / "local.df"
    with pytest.raises(ValueError, match="duplicate material_id"):
        load_structure_dataset(input_dirs=[tmp_path], output=output)
    assert not output.exists()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1])
def test_nonphysical_default_values_are_rejected(tmp_path, value):
    path = tmp_path / "CaS" / "POSCAR"
    _write_poscar(path, "CaS")
    with pytest.raises(ValueError, match="finite number"):
        load_structure_dataset(inputs=[path], output=tmp_path / "local.df", band_gap_default=value)


def test_metadata_tsv_preserves_explicit_zero_and_marks_missing_hull(tmp_path):
    path = tmp_path / "CaS" / "POSCAR"
    _write_poscar(path, "CaS")
    metadata = tmp_path / "metadata.tsv"
    metadata.write_text("material_id\tband_gap\nCaS\t0.0\n")
    frame = load_structure_dataset(
        inputs=[path], output=tmp_path / "local.df", metadata_path=metadata, band_gap_default=0.5
    )
    assert frame.loc["CaS", "band_gap"] == 0.0
    assert frame.loc["CaS", "source_metadata"]["defaulted_fields"] == ["e_hull"]


def test_cli_imports_real_poscar(tmp_path):
    from click.testing import CliRunner

    from ssscreen.cli.app import cli

    path = tmp_path / "CaS" / "POSCAR"
    _write_poscar(path, "CaS")
    output = tmp_path / "local.df"
    result = CliRunner().invoke(
        cli, ["dataset", "structures", "--input", str(path), "--output", str(output)]
    )
    assert result.exit_code == 0, result.output
    assert list(pd.read_pickle(output).index) == ["CaS"]
