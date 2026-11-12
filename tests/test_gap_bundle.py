"""The exported ZIP must work after relocation and preserve strict task identities."""

import hashlib
import json
import subprocess
import sys
import zipfile

import pandas as pd
import pytest
from click.testing import CliRunner
from pymatgen.core import Lattice, Structure

from ssscreen.cli.app import cli
from ssscreen.data.io import dump_group_df
from ssscreen.pair.envmatch import StructureGroup
from ssscreen.pair.gap_bundle import export_gap_bundle
from ssscreen.pair.gap_export import validate_gap_results


@pytest.fixture
def inputs(tmp_path):
    structure = Structure(Lattice.cubic(5.4), ["Ca", "S"], [[0, 0, 0], [0.5, 0.5, 0.5]])
    bigger = structure.copy()
    bigger.make_supercell((2, 1, 1))
    dataset = pd.DataFrame(
        [
            {"material_id": "mp-1", "formula": "CaS", "structure": structure},
            {"material_id": "mp-2", "formula": "CaS", "structure": bigger},
        ]
    ).set_index("material_id")
    dataset_path, groups_path = tmp_path / "dataset.df", tmp_path / "groups.json"
    dataset.to_pickle(dataset_path)
    group = StructureGroup(
        entry_idx=[0, 1],
        A_elements=[["Ca"], ["Ca"]],
        compositions=["CaS", "CaS"],
        group_size=2,
        X_element=["S", "Se"],
        mp_ids=["mp-1", "mp-2"],
        group_repr="fixture",
        band_gaps=[0.0, 0.3],
    )
    dump_group_df([group, group], groups_path)
    return groups_path, dataset_path


def test_zip_relocates_and_prepares_strict_real_method_contract(inputs, tmp_path):
    groups, dataset = inputs
    original = {path: path.read_bytes() for path in inputs}
    output = tmp_path / "交接.zip"
    report = export_gap_bundle(groups, dataset, output, max_natoms=2)
    assert report["task_count"] == 1
    assert report["candidate_material_count"] == 2
    assert report["skipped_count"] == 1
    assert all(path.read_bytes() == data for path, data in original.items())
    destination = tmp_path / "another machine"
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert not any(name.endswith(".df") for name in archive.namelist())
        archive.extractall(destination)
    for name, expected in report["files"].items():
        assert hashlib.sha256((destination / name).read_bytes()).hexdigest() == expected
    tasks = pd.read_csv(destination / "tasks.csv")
    for key in ("structure_json_path", "structure_cif_path", "structure_poscar_path"):
        path = destination / tasks.iloc[0][key]
        assert path.is_file() and str(tmp_path) not in tasks.iloc[0][key]
        assert len(Structure.from_file(path)) == 2
    assert pd.read_csv(destination / "results_template.csv").iloc[0].status == "pending"
    assert pd.read_csv(destination / "skipped_materials.csv").iloc[0].material_id == "mp-2"
    metadata_path = destination / "method_metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata.update(method="test-real-method-v1", calculator="external-fixture", functional="test")
    metadata_path.write_text(json.dumps(metadata))
    completed = subprocess.run(
        [sys.executable, str(destination / "prepare_calculation.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    prepared = destination / "prepared"
    actual_tasks = pd.read_csv(prepared / "tasks.csv")
    assert actual_tasks.iloc[0].pending_task_id == tasks.iloc[0].task_id
    assert actual_tasks.iloc[0].task_id != tasks.iloc[0].task_id
    results = pd.read_csv(prepared / "results_template.csv")
    results["status"], results["band_gap"] = "success", 0.2
    results.to_csv(prepared / "returned.csv", index=False)
    checked = validate_gap_results(
        prepared / "returned.csv",
        tasks_path=prepared / "tasks.csv",
        method_metadata_path=prepared / "method_metadata.json",
    )
    assert checked.attrs["validation_report"]["rejected_count"] == 0
    assert (destination / "tasks.csv").read_bytes() != (prepared / "tasks.csv").read_bytes()


def test_existing_zip_and_missing_material_do_not_publish(inputs, tmp_path):
    groups, dataset = inputs
    output = tmp_path / "exists.zip"
    output.write_bytes(b"keep existing")
    with pytest.raises(FileExistsError):
        export_gap_bundle(groups, dataset, output)
    assert output.read_bytes() == b"keep existing"
    frame = pd.read_pickle(dataset).iloc[:1]
    frame.to_pickle(dataset)
    target = tmp_path / "missing.zip"
    with pytest.raises(ValueError, match="缺少 1"):
        export_gap_bundle(groups, dataset, target)
    assert not target.exists()
    assert not list(tmp_path.glob(".gap-bundle-*"))


def test_cli_bundle_uses_real_exporter(inputs, tmp_path):
    groups, dataset = inputs
    output = tmp_path / "bundle.zip"
    argv = [
        "gap-export",
        "--bundle",
        "--groups",
        str(groups),
        "--dataset",
        str(dataset),
        "--output",
        str(output),
    ]
    result = CliRunner().invoke(cli, argv)
    assert result.exit_code == 0, result.output
    with zipfile.ZipFile(output) as archive:
        assert json.loads(archive.read("bundle_manifest.json"))["task_count"] == 2
    result = CliRunner().invoke(cli, argv)
    assert result.exit_code != 0
    assert "已存在" in result.output
