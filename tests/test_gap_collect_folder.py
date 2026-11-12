"""Folder returns must retain material identity and record actual XML provenance."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pandas as pd
import pytest
from click.testing import CliRunner
from pymatgen.core import Lattice, Structure

from ssscreen.cli.app import cli
from ssscreen.config import GAP_PENDING_METHOD
from ssscreen.pair.gap_collect_folder import collect_vasp_gap_folder
from ssscreen.pair.gap_export import _structure_sha256, make_gap_task_id, validate_gap_results


@pytest.fixture
def batch(tmp_path):
    rows = []
    for i, element in enumerate(("S", "Se")):
        structure = Structure(Lattice.cubic(5.4), ["Ca", element], [[0, 0, 0], [0.5, 0.5, 0.5]])
        row = {
            "schema_version": 1,
            "material_id": f"mp-{i}",
            "formula": f"Ca{element}",
            "method": GAP_PENDING_METHOD,
            "structure_sha256": _structure_sha256(structure),
        }
        row["task_id"] = make_gap_task_id(
            row["material_id"], row["method"], row["structure_sha256"]
        )
        rows.append(row)
    tasks = pd.DataFrame(rows)
    payload = tasks.to_csv(index=False).encode()
    source = tmp_path / "inputs.zip"
    with ZipFile(source, "w") as archive:
        archive.writestr("tasks.csv", payload)
        archive.writestr(
            "bundle_manifest.json",
            json.dumps({"files": {"tasks.csv": hashlib.sha256(payload).hexdigest()}}),
        )
    root = tmp_path / "VASP结果"
    task_dir = root / tasks.iloc[0].task_id
    task_dir.mkdir(parents=True)
    (task_dir / "vasprun.xml").write_text("deliberately invalid XML fixture")
    return source, tasks, root


def fake_run(element="S"):
    structure = Structure(Lattice.cubic(5.45), ["Ca", element], [[0, 0, 0], [0.5, 0.5, 0.5]])
    return SimpleNamespace(
        parameters={"GGA": "PE", "METAGGA": "MBJ", "ISPIN": 2, "LHFCALC": False, "ENCUT": 650},
        incar={"METAGGA": "MBJ", "ENCUT": 650},
        kpoints=SimpleNamespace(as_dict=lambda: {"mesh": [4, 4, 4]}),
        potcar_symbols=["PAW Ca", f"PAW {element}"],
        vasp_version="6.5.1",
        initial_structure=structure,
        final_structure=structure,
        converged=True,
        eigenvalue_band_properties=(0.21, 0.3, 0.09, True),
        get_band_structure=lambda: SimpleNamespace(get_band_gap=lambda: {"transition": "G-G"}),
    )


def test_folder_binds_zip_ids_and_xml_conditions_then_validates(batch, tmp_path, monkeypatch):
    source, tasks, root = batch
    before = source.read_bytes()
    monkeypatch.setattr(
        "ssscreen.pair.gap_collect_folder.Vasprun", lambda *args, **kwargs: fake_run()
    )
    output = tmp_path / "returned.csv"
    rows, report = collect_vasp_gap_folder(
        task_sources=(source,), results_dir=root, output_path=output
    )
    assert report["status_counts"] == {"success": 1, "not_converged": 0, "failed": 0, "missing": 1}
    assert report["validation"]["rejected_count"] == 0
    assert report["validation"]["accepted_count"] == 2
    actual = rows.iloc[0]
    assert actual.source_task_id == tasks.iloc[0].task_id
    assert actual.material_id == tasks.iloc[0].material_id
    assert actual.task_id != actual.source_task_id
    assert actual.method.startswith("vasp-mbj-")
    assert actual.band_gap == pytest.approx(0.21)
    assert actual.structure_sha256 != tasks.iloc[0].structure_sha256
    evidence = json.loads(Path(report["provenance_path"]).read_text())
    assert evidence[actual.source_task_id]["method_metadata"]["parameters"]["ENCUT"] == 650
    assert len(evidence[actual.source_task_id]["vasprun_sha256"]) == 64
    bound = pd.read_csv(report["tasks_path"])
    assert bound.iloc[0].source_structure_sha256 == tasks.iloc[0].structure_sha256
    checked = validate_gap_results(output, tasks_path=report["tasks_path"])
    assert checked.attrs["validation_report"]["rejected_count"] == 0
    assert len(checked) == 2
    assert source.read_bytes() == before


def test_folder_validation_rejects_nonfinite_gap_before_publishing(batch, tmp_path, monkeypatch):
    source, _, root = batch
    run = fake_run()
    run.eigenvalue_band_properties = (float("inf"), 0.3, 0.09, True)
    monkeypatch.setattr("ssscreen.pair.gap_collect_folder.Vasprun", lambda *args, **kwargs: run)
    output = tmp_path / "out.csv"
    with pytest.raises(ValueError, match="invalid_band_gap"):
        collect_vasp_gap_folder(task_sources=(source,), results_dir=root, output_path=output)
    assert not output.exists()
    assert not list(tmp_path.glob("out.*"))


def test_folder_collection_directly_feeds_wavelength_pairing(batch, tmp_path, monkeypatch):
    from ssscreen.data.io import dump_group_df
    from ssscreen.pair.envmatch import StructureGroup

    source, tasks, root = batch
    second = root / tasks.iloc[1].task_id
    second.mkdir()
    (second / "vasprun.xml").write_text("parser fixture")

    def parse(path, **kwargs):
        first = path.parent.name == tasks.iloc[0].task_id
        run = fake_run("S" if first else "Se")
        run.eigenvalue_band_properties = (0.08 if first else 0.25, 0.3, 0.09, True)
        return run

    monkeypatch.setattr("ssscreen.pair.gap_collect_folder.Vasprun", parse)
    output = tmp_path / "returned.csv"
    runner = CliRunner()
    collected = runner.invoke(
        cli,
        [
            "gap-collect-vasp",
            "--task-source",
            str(source),
            "--results-dir",
            str(root),
            "--output",
            str(output),
        ],
    )
    assert collected.exit_code == 0, collected.output
    groups = tmp_path / "groups.json"
    dump_group_df(
        [
            StructureGroup(
                mp_ids=tasks.material_id.tolist(),
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
    paired = runner.invoke(
        cli,
        [
            "pair-wavelength",
            "--groups",
            str(groups),
            "--gap-results",
            str(output),
            "--target-wavelength-um",
            "10",
            "--output",
            str(tmp_path / "pairs.csv"),
            "--summary",
            str(tmp_path / "summary.json"),
        ],
    )
    assert paired.exit_code == 0, paired.output
    assert len(pd.read_csv(tmp_path / "pairs.csv")) == 1


@pytest.mark.parametrize("problem", ["unknown", "nested", "empty"])
def test_bad_folder_layout_never_publishes(batch, tmp_path, problem):
    source, tasks, _ = batch
    root = tmp_path / "bad"
    root.mkdir()
    if problem != "empty":
        directory = root / ("gap-unknown" if problem == "unknown" else tasks.iloc[0].task_id)
        if problem == "nested":
            directory /= "mbj"
        directory.mkdir(parents=True)
        (directory / "vasprun.xml").write_text("test")
    output = tmp_path / "returned.csv"
    with pytest.raises(ValueError):
        collect_vasp_gap_folder(task_sources=(source,), results_dir=root, output_path=output)
    assert not output.exists()


def test_xml_from_wrong_material_is_failed_not_reassigned(batch, tmp_path, monkeypatch):
    source, tasks, root = batch
    monkeypatch.setattr(
        "ssscreen.pair.gap_collect_folder.Vasprun", lambda *args, **kwargs: fake_run("O")
    )
    rows, report = collect_vasp_gap_folder(
        task_sources=(source,), results_dir=root, output_path=tmp_path / "out.csv"
    )
    assert rows.iloc[0].status == "failed"
    assert pd.isna(rows.iloc[0].band_gap)
    assert rows.iloc[0].material_id == tasks.iloc[0].material_id
    assert "组成" in rows.iloc[0].error
    assert report["status_counts"]["failed"] == 1


def test_real_cli_collects_malformed_and_missing_without_task_input(batch, tmp_path):
    source, _, root = batch
    output = tmp_path / "returned.csv"
    result = CliRunner().invoke(
        cli,
        [
            "gap-collect-vasp",
            "--task-source",
            str(source),
            "--results-dir",
            str(root),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    rows = pd.read_csv(output)
    assert rows.status.tolist() == ["failed", "missing"]
    assert rows.band_gap.isna().all()
    assert (
        validate_gap_results(output, tasks_path=tmp_path / "returned.tasks.csv").attrs[
            "validation_report"
        ]["rejected_count"]
        == 0
    )
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        collect_vasp_gap_folder(task_sources=(source,), results_dir=root, output_path=output)
    assert output.read_bytes() == before


def test_prepared_batch_is_discovered_only_when_ids_match(batch, tmp_path):
    source, tasks, _ = batch
    prepared = source.parent / "prepared"
    prepared.mkdir()
    tasks["method"] = "actual-method"
    tasks["task_id"] = [
        make_gap_task_id(row.material_id, row.method, row.structure_sha256)
        for row in tasks.itertuples()
    ]
    tasks.to_csv(prepared / "tasks.csv", index=False)
    root = tmp_path / "prepared-returns"
    (root / tasks.iloc[0].task_id).mkdir(parents=True)
    _, report = collect_vasp_gap_folder(
        task_sources=(source,), results_dir=root, output_path=tmp_path / "out.csv"
    )
    assert Path(report["selected_source"]) == prepared / "tasks.csv"
    assert report["status_counts"]["missing"] == 2


def test_modified_zip_task_table_is_rejected(batch, tmp_path):
    source, tasks, root = batch
    with ZipFile(source, "w") as archive:
        archive.writestr("tasks.csv", tasks.to_csv(index=False))
        archive.writestr("bundle_manifest.json", json.dumps({"files": {"tasks.csv": "0" * 64}}))
    with pytest.raises(ValueError, match="校验失败"):
        collect_vasp_gap_folder(
            task_sources=(source,), results_dir=root, output_path=tmp_path / "out.csv"
        )
