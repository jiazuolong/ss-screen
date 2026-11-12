from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from ssscreen.pair.gap_collect_vasp import ParsedVaspGap, collect_vasp_gap_results
from ssscreen.pair.gap_export import GAP_SCHEMA_VERSION


def _write_tasks(path: Path) -> None:
    pd.DataFrame(
        [
            {
                "schema_version": GAP_SCHEMA_VERSION,
                "task_id": "gap-aaaaaaaaaaaaaaaaaaaaaaaa",
                "material_id": "mp-1",
                "formula": "CaS",
                "method": "vasp-hse06-v1",
                "structure_sha256": "a" * 64,
            },
            {
                "schema_version": GAP_SCHEMA_VERSION,
                "task_id": "gap-bbbbbbbbbbbbbbbbbbbbbbbb",
                "material_id": "mp-2",
                "formula": "CaSe",
                "method": "vasp-hse06-v1",
                "structure_sha256": "b" * 64,
            },
            {
                "schema_version": GAP_SCHEMA_VERSION,
                "task_id": "gap-cccccccccccccccccccccccc",
                "material_id": "mp-3",
                "formula": "CaTe",
                "method": "vasp-hse06-v1",
                "structure_sha256": "c" * 64,
            },
        ]
    ).to_csv(path, index=False)


def test_collect_vasp_gap_results_batches_statuses_and_missing(monkeypatch, tmp_path):
    tasks = tmp_path / "tasks.csv"
    results_dir = tmp_path / "vasp-results"
    output = tmp_path / "results.csv"
    report_path = tmp_path / "report.json"
    _write_tasks(tasks)
    for task_id in ("gap-aaaaaaaaaaaaaaaaaaaaaaaa", "gap-bbbbbbbbbbbbbbbbbbbbbbbb"):
        task_dir = results_dir / task_id
        task_dir.mkdir(parents=True)
        (task_dir / "vasprun.xml").write_text("placeholder")

    parsed = iter(
        [
            ParsedVaspGap(
                status="success",
                band_gap=0.42,
                is_direct=True,
                transition="G-G",
                backend_version="6.4.3",
            ),
            ParsedVaspGap(
                status="not_converged",
                error="VASP not converged",
                backend_version="6.4.3",
            ),
        ]
    )
    monkeypatch.setattr("ssscreen.pair.gap_collect_vasp._parse_vasprun", lambda _path: next(parsed))

    results, report = collect_vasp_gap_results(
        tasks_path=tasks,
        results_dir=results_dir,
        output_path=output,
        report_path=report_path,
    )

    assert list(results["status"]) == ["success", "not_converged", "missing"]
    assert results.loc[0, "band_gap"] == pytest.approx(0.42)
    assert bool(results.loc[0, "is_direct"]) is True
    assert pd.isna(results.loc[1, "band_gap"])
    assert set(results["backend"]) == {"VASP"}
    assert set(results["backend_version"]) == {"", "6.4.3"}
    assert report["selected_task_count"] == 3
    assert report["status_counts"] == {
        "success": 1,
        "not_converged": 1,
        "failed": 0,
        "missing": 1,
    }
    assert report["missing_task_ids"] == ["gap-cccccccccccccccccccccccc"]
    assert report["task_results"][2]["error"] == "vasprun.xml[.gz] not found"
    assert pd.read_csv(output).shape[0] == 3
    assert json.loads(report_path.read_text()) == report


def test_collect_vasp_gap_results_filters_one_task(monkeypatch, tmp_path):
    tasks = tmp_path / "tasks.csv"
    results_dir = tmp_path / "vasp-results"
    _write_tasks(tasks)
    selected = "gap-bbbbbbbbbbbbbbbbbbbbbbbb"
    task_dir = results_dir / selected
    task_dir.mkdir(parents=True)
    (task_dir / "vasprun.xml.gz").write_text("placeholder")
    monkeypatch.setattr(
        "ssscreen.pair.gap_collect_vasp._parse_vasprun",
        lambda _path: ParsedVaspGap(status="success", band_gap=0.3, is_direct=False),
    )

    results, report = collect_vasp_gap_results(
        tasks_path=tasks,
        results_dir=results_dir,
        output_path=tmp_path / "results.csv",
        report_path=tmp_path / "report.json",
        task_ids=(selected,),
    )

    assert list(results["task_id"]) == [selected]
    assert report["selected_task_count"] == 1
    assert report["missing_count"] == 0


def test_collect_vasp_gap_results_hashes_metadata_and_reports_unknown_directory(
    monkeypatch, tmp_path
):
    tasks = tmp_path / "tasks.csv"
    results_dir = tmp_path / "vasp-results"
    output = tmp_path / "results.csv"
    metadata = tmp_path / "method.json"
    _write_tasks(tasks)
    selected = "gap-aaaaaaaaaaaaaaaaaaaaaaaa"
    task_dir = results_dir / selected
    task_dir.mkdir(parents=True)
    (task_dir / "vasprun.xml").write_text("placeholder")
    (results_dir / "gap-unknown-directory").mkdir()
    metadata.write_text(
        json.dumps(
            {
                "schema_version": GAP_SCHEMA_VERSION,
                "method": "vasp-hse06-v1",
                "functional": "HSE06",
                "settings": {"ENCUT": 520},
            }
        )
    )
    monkeypatch.setattr(
        "ssscreen.pair.gap_collect_vasp._parse_vasprun",
        lambda _path: ParsedVaspGap(status="success", band_gap=0.4, is_direct=True),
    )

    results, report = collect_vasp_gap_results(
        tasks_path=tasks,
        results_dir=results_dir,
        output_path=output,
        method_metadata_path=metadata,
        task_ids=(selected,),
    )

    assert results.loc[0, "settings_sha256"] == report["settings_sha256"]
    assert len(report["settings_sha256"]) == 64
    assert report["unexpected_task_ids"] == ["gap-unknown-directory"]
    assert (tmp_path / "results.collection-report.json").is_file()


def test_collect_vasp_gap_results_rejects_unknown_task_selection(tmp_path):
    tasks = tmp_path / "tasks.csv"
    results_dir = tmp_path / "vasp-results"
    results_dir.mkdir()
    _write_tasks(tasks)

    with pytest.raises(ValueError, match="unknown task_id selection"):
        collect_vasp_gap_results(
            tasks_path=tasks,
            results_dir=results_dir,
            output_path=tmp_path / "results.csv",
            report_path=tmp_path / "report.json",
            task_ids=("gap-unknown",),
        )


def test_parse_vasprun_extracts_converged_gap(monkeypatch, tmp_path):
    from ssscreen.pair import gap_collect_vasp

    class FakeBandStructure:
        def get_band_gap(self):
            return {"transition": "G-X"}

    class FakeVasprun:
        converged = True
        converged_electronic = True
        converged_ionic = True
        eigenvalue_band_properties = (0.37, 1.2, 0.83, False)
        vasp_version = "6.4.3"

        def get_band_structure(self):
            return FakeBandStructure()

    monkeypatch.setattr(gap_collect_vasp, "Vasprun", lambda *_args, **_kwargs: FakeVasprun())

    result = gap_collect_vasp._parse_vasprun(tmp_path / "vasprun.xml")

    assert result == ParsedVaspGap(
        status="success",
        band_gap=0.37,
        is_direct=False,
        transition="G-X",
        backend_version="6.4.3",
    )


def test_collect_preserves_per_task_settings_without_single_metadata(tmp_path):
    tasks = tmp_path / "tasks.csv"
    _write_tasks(tasks)
    frame = pd.read_csv(tasks)
    frame["settings_sha256"] = ["a" * 64, "b" * 64, ""]
    frame.to_csv(tasks, index=False)
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    results, _ = collect_vasp_gap_results(
        tasks_path=tasks, results_dir=results_dir, output_path=tmp_path / "collected.csv"
    )
    assert list(results["settings_sha256"]) == ["a" * 64, "b" * 64, ""]
    assert list(results["status"]) == ["missing"] * 3
    assert results["band_gap"].isna().all()


def test_collect_rejects_metadata_that_would_replace_task_settings(tmp_path):
    tasks = tmp_path / "tasks.csv"
    _write_tasks(tasks)
    frame = pd.read_csv(tasks)
    frame["settings_sha256"] = "a" * 64
    frame.to_csv(tasks, index=False)
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    metadata = tmp_path / "method_metadata.json"
    metadata.write_text(json.dumps({"method": "vasp-hse06-v1", "settings": {"ENCUT": 520}}))
    output = tmp_path / "collected.csv"
    with pytest.raises(ValueError, match="settings do not match"):
        collect_vasp_gap_results(
            tasks_path=tasks,
            results_dir=results_dir,
            output_path=output,
            method_metadata_path=metadata,
        )
    assert not output.exists()
