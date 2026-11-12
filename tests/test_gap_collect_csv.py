"""Prepared CSV import preserves actual identities and rejects invalid evidence."""

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest
from click.testing import CliRunner

from ssscreen.cli.app import cli
from ssscreen.pair.gap_collect_csv import collect_gap_csv
from ssscreen.pair.gap_export import make_gap_task_id, validate_gap_results


@pytest.fixture
def batch(tmp_path):
    tasks = pd.DataFrame(
        [
            {
                "schema_version": 1,
                "material_id": f"mp-{i}",
                "formula": formula,
                "method": "mbj-test-v1",
                "structure_sha256": str(i + 1) * 64,
                "settings_sha256": str(i + 3) * 64,
            }
            for i, formula in enumerate(("CaS", "CaSe"))
        ]
    )
    tasks["task_id"] = [
        make_gap_task_id(row.material_id, row.method, row.structure_sha256)
        for _, row in tasks.iterrows()
    ]
    source = tmp_path / "registered.csv"
    tasks.to_csv(source, index=False)
    returned = tasks.copy()
    returned["band_gap"] = [0.12, 0.31]
    returned["is_direct"] = [True, False]
    returned["transition"] = ["G-G", "G-X"]
    returned["status"] = ["success", "not_converged"]
    csv = tmp_path / "results.csv"
    returned.to_csv(csv, index=False)
    return source, tasks, csv, returned


def test_csv_import_preserves_tasks_statuses_and_input_bytes(batch, tmp_path):
    source, tasks, csv, returned = batch
    before = csv.read_bytes()
    output = tmp_path / "collected.csv"
    rows, report = collect_gap_csv(task_sources=(source,), results_csv=csv, output_path=output)
    assert report["mode"] == "project-csv"
    assert report["status_counts"] == {
        "success": 1,
        "not_converged": 1,
        "failed": 0,
        "missing": 0,
    }
    assert rows.task_id.tolist() == returned.task_id.tolist()
    assert rows.iloc[0].band_gap == pytest.approx(0.12)
    assert pd.isna(rows.iloc[1].band_gap)
    assert rows.iloc[1].settings_sha256 == tasks.iloc[1].settings_sha256
    assert report["input_sha256"] == hashlib.sha256(before).hexdigest()
    assert csv.read_bytes() == before
    checked = validate_gap_results(output, tasks_path=report["tasks_path"])
    assert checked.attrs["validation_report"]["rejected_count"] == 0
    provenance = json.loads(Path(report["provenance_path"]).read_text())
    assert "not a new XML parse" in provenance["scope"]
    with pytest.raises(FileExistsError):
        collect_gap_csv(task_sources=(source,), results_csv=csv, output_path=output)
    assert len(pd.read_csv(output)) == 2


def test_zip_source_and_partial_csv_keep_missing_tasks(batch, tmp_path):
    source, tasks, csv, returned = batch
    zip_path = tmp_path / "export.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("tasks.csv", source.read_bytes())
        archive.writestr(
            "bundle_manifest.json",
            json.dumps({"files": {"tasks.csv": hashlib.sha256(source.read_bytes()).hexdigest()}}),
        )
    returned.iloc[:1].to_csv(csv, index=False)
    rows, report = collect_gap_csv(
        task_sources=(zip_path,), results_csv=csv, output_path=tmp_path / "out.csv"
    )
    assert len(rows) == 2 and report["missing_count"] == 1
    absent = rows.loc[rows.task_id == tasks.iloc[1].task_id].iloc[0]
    assert absent.status == "missing" and pd.isna(absent.band_gap)
    assert report["missing_task_ids"] == [tasks.iloc[1].task_id]


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("material_id", "mp-wrong", "material_id_mismatch"),
        ("method", "other", "method_mismatch"),
        ("formula", "NaCl", "formula_mismatch"),
        ("structure_sha256", "a" * 64, "structure_sha256_mismatch"),
        ("settings_sha256", "a" * 64, "settings_sha256_mismatch"),
        ("band_gap", -0.3, "invalid_band_gap"),
        ("task_id", "gap-" + "a" * 24, "无法完整对应"),
    ],
)
def test_invalid_csv_never_publishes(batch, tmp_path, field, value, error):
    source, _, csv, returned = batch
    returned.loc[0, field] = value
    returned.to_csv(csv, index=False)
    output = tmp_path / "out.csv"
    with pytest.raises(ValueError, match=error):
        collect_gap_csv(task_sources=(source,), results_csv=csv, output_path=output)
    assert not output.exists()
    assert not list(tmp_path.glob("out.*.json"))


@pytest.mark.parametrize("kind", ["duplicate", "empty", "missing-id"])
def test_csv_format_errors(batch, tmp_path, kind):
    source, _, csv, returned = batch
    if kind == "duplicate":
        returned = pd.concat([returned, returned.iloc[:1]], ignore_index=True)
    elif kind == "empty":
        returned = returned.iloc[:0]
    else:
        returned = returned.drop(columns="task_id")
    returned.to_csv(csv, index=False)
    with pytest.raises(ValueError):
        collect_gap_csv(task_sources=(source,), results_csv=csv, output_path=tmp_path / "out.csv")


def test_cli_csv_and_mutually_exclusive_modes(batch, tmp_path):
    source, _, csv, _ = batch
    args = [
        "gap-collect-vasp",
        "--task-source",
        str(source),
        "--output",
        str(tmp_path / "out.csv"),
    ]
    runner = CliRunner()
    assert runner.invoke(cli, args).exit_code != 0
    assert (
        runner.invoke(
            cli, args + ["--results-csv", str(csv), "--results-dir", str(tmp_path)]
        ).exit_code
        != 0
    )
    result = runner.invoke(cli, args + ["--results-csv", str(csv)])
    assert result.exit_code == 0, result.output
    assert "Imported CSV" in result.output
    assert len(pd.read_csv(tmp_path / "out.csv")) == 2


def test_other_calculation_statuses_remain_visible(batch, tmp_path):
    source, _, csv, returned = batch
    returned["status"] = ["skipped", "pending"]
    returned.to_csv(csv, index=False)
    rows, report = collect_gap_csv(
        task_sources=(source,), results_csv=csv, output_path=tmp_path / "out.csv"
    )
    assert report["status_counts"]["skipped"] == report["status_counts"]["pending"] == 1
    assert report["status_counts"]["success"] == 0
    assert rows.band_gap.isna().all()


def test_historical_library_matches_current_export_and_retains_actual_method(tmp_path):
    from pymatgen.core import Lattice, Structure

    from ssscreen.pair.gap_export import _canonical_sha256

    original = Structure(Lattice.cubic(4), ["Ca", "S"], [[0, 0, 0], [0.5, 0.5, 0.5]]).as_dict()
    shifted = Structure(Lattice.cubic(4), ["Ca", "S"], [[0.25] * 3, [0.75] * 3]).as_dict()
    sha = _canonical_sha256(original)

    def identity(material, method, digest):
        return dict(
            schema_version=1,
            material_id=material,
            method=method,
            formula="CaS",
            structure_sha256=digest,
            task_id=make_gap_task_id(material, method, digest),
        )

    ids = ["mp-1", "mp-2", "mp-3", "mp-4"]
    pending = [
        dict(identity(m, "external-method-pending-v1", sha), structure_json_path=f"{m}.json")
        for m in ids
    ]
    payload = pd.DataFrame(pending).to_csv(index=False).encode()
    archive = tmp_path / "export.zip"
    with ZipFile(archive, "w") as z:
        z.writestr("tasks.csv", payload)
        z.writestr(
            "bundle_manifest.json",
            json.dumps({"files": {"tasks.csv": hashlib.sha256(payload).hexdigest()}}),
        )
        for m in ids:
            z.writestr(f"{m}.json", json.dumps(original))

    def result(material, method, structure):
        return dict(
            identity(material, method, _canonical_sha256(structure)),
            structure_json=json.dumps(structure),
            band_gap=0.23,
            status="success",
            is_direct=True,
            transition="",
        )

    rows = [
        result("mp-1", "m1", original),
        result("mp-2", "m1", shifted),
        result("mp-3", "m1", original),
        result("mp-3", "m2", original),
        result("mp-5", "m1", original),
    ]
    csv = tmp_path / "library.csv"
    pd.DataFrame(rows).to_csv(csv, index=False)

    def match(label, method):
        return collect_gap_csv(
            task_sources=(archive,),
            results_csv=csv,
            library_method=method,
            output_path=tmp_path / f"{label}.csv",
        )

    results, report = match("auto", "")
    assert [r["match"] for r in report["matches"]] == [
        "exact",
        "equivalent",
        "ambiguous",
        "missing",
    ]
    assert results.loc[results.status == "success", "task_id"].tolist() == [
        r["task_id"] for r in rows[:2]
    ]
    assert match("filtered", "m1")[1]["status_counts"]["success"] == 3
    rows[1]["structure_json"] = json.dumps(original)
    pd.DataFrame(rows).to_csv(csv, index=False)
    with pytest.raises(ValueError, match="哈希"):
        match("bad", "m1")
    assert not (tmp_path / "bad.csv").exists()
