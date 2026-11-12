"""Native imported projects must retain real inputs and command defaults."""

import json
from pathlib import Path

import pytest

from ssscreen.cli.app import cli
from ssscreen.gui.metadata import COMMANDS
from ssscreen.gui.project_file import create_project_file, extract_project_file
from ssscreen.gui.workflow_project import imported_artifact, mp_output_paths, read_project


@pytest.mark.parametrize("absolute", [False, True])
def test_mp_outputs_follow_dataset_directory(tmp_path, absolute):
    database = Path("01数据源/输入/default.db")
    source = str(tmp_path / database) if absolute else str(database)
    output, provenance = mp_output_paths(tmp_path, source)
    assert output == "01数据源/输入/mp.df"
    assert provenance == "01数据源/输入/mp.df.provenance.json"
    assert (tmp_path / output).parent == (tmp_path / database).parent


def test_mp_outputs_outside_project_keep_absolute_paths(tmp_path):
    source = tmp_path / "external data" / "default.db"
    output, provenance = mp_output_paths(tmp_path / "project", str(source))
    assert Path(output) == source.parent / "mp.df"
    assert Path(provenance) == source.parent / "mp.df.provenance.json"


def test_mp_api_without_database_keeps_project_default(tmp_path):
    assert mp_output_paths(tmp_path) == (
        "01_dataset/mp.df",
        "01_dataset/mp.df.provenance.json",
    )


def test_mp_database_alias_uses_actual_source_directory(tmp_path):
    source = tmp_path / "external" / "default.db"
    (tmp_path / ".ssscreen-project.json").write_text(
        json.dumps({"artifacts": {"input/default.db": str(source)}})
    )
    assert mp_output_paths(tmp_path, "input/default.db") == (
        "external/mp.df",
        "external/mp.df.provenance.json",
    )


def test_new_output_takes_precedence_over_imported_artifact(tmp_path: Path):
    original = tmp_path / "original.df"
    original.write_text("original")
    root = tmp_path / "project"
    root.mkdir()
    (root / ".ssscreen-project.json").write_text(
        json.dumps(
            {
                "artifacts": {"01_dataset/mp.df": str(original)},
                "gui_settings": {"forms": {"dataset_source_page": {"mp_backend": "offline"}}},
            }
        )
    )
    assert imported_artifact(root, "01_dataset/mp.df") == original
    local = root / "01_dataset/mp.df"
    local.parent.mkdir()
    local.write_text("new")
    assert imported_artifact(root, "01_dataset/mp.df") == local
    assert original.read_text() == "original"
    assert (
        read_project(root)["gui_settings"]["forms"]["dataset_source_page"]["mp_backend"]
        == "offline"
    )


def test_workflow_commands_are_real_registered_cli_commands():
    paths = {presentation.command_path for presentation in COMMANDS}
    assert ("pair-wavelength",) in paths
    assert ("geometry-evaluate",) in paths
    assert ("gap-collect-vasp",) in paths
    assert ("gap-validate",) not in paths
    assert [p.command_path for p in COMMANDS if p.stage == "06"] == [("pair-wavelength",)]
    assert {"pair", "gap-compare"} <= cli.commands.keys()
    assert "gap-validate" in cli.commands  # Existing CLI workflows remain supported.
    for path in paths:
        command = cli
        for token in path:
            command = command.commands[token]


def test_import_alias_survives_project_container(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    original = tmp_path / "mp.df"
    original.write_text("external")
    project = tmp_path / "run.ssproject"
    create_project_file(
        root, project, project_settings={"artifact_aliases": {"01_dataset/mp.df": str(original)}}
    )
    restored = tmp_path / "restored"
    extract_project_file(project, restored)
    assert imported_artifact(restored, "01_dataset/mp.df") == original


def test_composition_checkboxes_and_archive_follow_round_trip(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from ssscreen.gui.app import MainWindow
    from ssscreen.gui.workflow_project import capture_forms, restore_forms

    app = QApplication.instance() or QApplication([])
    window = MainWindow(
        str(tmp_path), settings=QSettings(str(tmp_path / "gui.ini"), QSettings.IniFormat)
    )
    page, archive = window.composition_screen_page, window.structure_archive_page
    assert page._element_counts() == [2, 3]
    assert page._screen_argv().count("--nelems") == 2
    page.structures_output.setText("02组成模板筛选/candidates.df")
    assert archive.df_path.text() == page.structures_output.text()
    assert archive.df_path.isReadOnly()
    saved = capture_forms(window)
    page.binary_enabled.setChecked(False)
    page.ternary_enabled.setChecked(False)
    assert "请至少勾选" in page.command_preview.toPlainText()
    restore_forms(window, saved)
    assert page._element_counts() == [2, 3]
    assert archive.df_path.text() == page.structures_output.text()
    restore_forms(
        window,
        {
            "composition_screen_page": {"nelems_edit": "3"},
            "structure_archive_page": {"df_path": "legacy/custom.df"},
        },
    )
    assert page._element_counts() == [3]
    assert not archive.df_follow_composition.isChecked()
    page.structures_output.setText("new/candidates.df")
    assert archive.df_path.text() == "legacy/custom.df"
    assert not archive.df_path.isReadOnly()
    archive.df_follow_composition.setChecked(True)
    assert archive.df_path.text() == "new/candidates.df"
    matching = window.structure_match_page
    archive.df_output_dir.setText("03结构描述归档/condensed")
    page.candidates_output.setText("02组成模板筛选/candidates.csv")
    assert matching.follow_stage03.isChecked()
    assert matching.candidates_edit.text() == page.candidates_output.text()
    assert matching._archive_paths() == [str(tmp_path / "03结构描述归档/condensed")]
    restore_forms(
        window,
        {"structure_match_page": {"candidates_edit": "old.csv", "archives": ["old/archive"]}},
    )
    assert not matching.follow_stage03.isChecked()
    archive.df_output_dir.setText("new/archive")
    assert matching.candidates_edit.text() == "old.csv"
    matching.follow_stage03.setChecked(True)
    assert matching._archive_paths() == [str(tmp_path / "new/archive")]
    window.close()
    app.processEvents()


def test_optional_flags_and_remote_paths_round_trip():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from ssscreen.gui.app import CommandPage
    from ssscreen.gui.metadata import CommandPresentation

    app = QApplication.instance() or QApplication([])
    page = CommandPage(
        CommandPresentation("06", "波长配对", ("pair-wavelength",)), cli.commands["pair-wavelength"]
    )
    assert "--allow-mixed-methods" not in page.argv()
    page.restore_argv(
        [
            "pair-wavelength",
            "--groups",
            "/remote/groups.json",
            "--gap-results",
            "/remote/gaps.csv",
            "--target-wavelength-um",
            "10",
            "--min-gap-exclusive",
            "0",
            "--max-gap-exclusive",
            "0.4",
            "--allow-mixed-methods",
            "--output",
            "pairs.csv",
            "--summary",
            "summary.json",
        ]
    )
    argv = page.argv()
    assert "--allow-mixed-methods" in argv
    assert "/remote/groups.json" in argv
    assert not page.missing_required()
    assert not any("Sentinel" in value for value in argv)
    page.close()
    sqs = CommandPage(
        CommandPresentation("07", "SQS", ("stability", "sqs-generate")),
        cli.commands["stability"].commands["sqs-generate"],
    )
    original = sqs.argv()
    original[original.index("--supercell") + 1] = "2,2,2"
    for _ in range(2):
        sqs.restore_argv(original)
        restored = sqs.argv()
        assert restored[restored.index("--supercell") + 1] == "2,2,2"
        original = restored
    sqs.close()
    app.processEvents()


def test_collected_gap_handoff_round_trip_and_output_integrity(tmp_path):
    pytest.importorskip("PySide6")
    import pandas as pd
    from PySide6.QtCore import QProcess, QSettings
    from PySide6.QtWidgets import QApplication

    from ssscreen.gui.app import MainWindow
    from ssscreen.gui.workflow_project import apply_command_values
    from ssscreen.pair.gap_collect_csv import collect_gap_csv
    from ssscreen.pair.gap_export import make_gap_task_id

    task = {
        "schema_version": 1,
        "material_id": "mp-1",
        "formula": "CaS",
        "method": "test-mbj",
        "structure_sha256": "a" * 64,
    }
    task["task_id"] = make_gap_task_id(
        task["material_id"], task["method"], task["structure_sha256"]
    )
    source, returned = tmp_path / "tasks.csv", tmp_path / "input.csv"
    pd.DataFrame([task]).to_csv(source, index=False)
    pd.DataFrame([{**task, "band_gap": 0.1, "is_direct": True, "status": "success"}]).to_csv(
        returned, index=False
    )
    output = tmp_path / "collected/results_returned.csv"
    collect_gap_csv(task_sources=(source,), results_csv=returned, output_path=output)
    settings = {
        "commands": {
            "gap-validate": ["gap-validate", "--gaps", str(returned), "--tasks", str(source)],
            "gap-collect-vasp": [
                "gap-collect-vasp",
                "--results-csv",
                str(returned),
                "--output",
                str(output),
            ],
        },
        "command_values": {"pair-wavelength": {"wavelength_um": 8}},
    }
    (tmp_path / ".ssscreen-project.json").write_text(json.dumps({"gui_settings": settings}))
    app = QApplication.instance() or QApplication([])
    window = MainWindow(
        str(tmp_path), settings=QSettings(str(tmp_path / "gui.ini"), QSettings.IniFormat)
    )
    window._show_command_page(("pair-wavelength",))
    pair = window._pages[("pair-wavelength",)]
    # Opening 06 directly restores 05 first; stale saved/manual paths are ignored.
    assert pair.groups_edit.isReadOnly() and pair.gaps_edit.isReadOnly()
    assert str(output) in pair.argv()
    apply_command_values(pair, {"gap_paths": ["stale.csv"], "method": "old-method"})
    assert "stale.csv" not in pair.argv() and "--method" not in pair.argv()
    apply_command_values(pair, {"wavelength_um": 10})  # Preserve unsaved user edits.
    window._show_command_page(("gap-validate",))
    page = window._pages[("gap-collect-vasp",)]
    assert ("gap-validate",) not in window._pages
    assert page.pair_button.isEnabled()
    page.pair_button.click()
    assert window.stack.currentWidget() is pair
    assert str(output) in pair.argv()
    assert pair.argv()[pair.argv().index("--target-wavelength-um") + 1] == "10.0"
    assert window.process.state() == QProcess.NotRunning
    snapshot = window._project_settings_snapshot()
    window._apply_project_settings(snapshot)
    assert str(output) in pair.argv()
    output.write_text(output.read_text() + "\n")
    page.refresh_preview()
    assert not page.pair_button.isEnabled()
    assert page.validated_result() is None
    window.close()
    app.processEvents()


def test_wavelength_handoff_requires_current_inputs_conditions_and_output(tmp_path):
    pytest.importorskip("PySide6")
    import hashlib

    from PySide6.QtWidgets import QApplication

    from ssscreen.cli.app import cli
    from ssscreen.gui.metadata import COMMANDS
    from ssscreen.gui.wavelength_page import WavelengthPairPage

    app = QApplication.instance() or QApplication([])
    groups, gaps = tmp_path / "groups.json", tmp_path / "gaps.csv"
    groups.write_text("group fixture")
    gaps.write_text("gap fixture")
    ready = [True]
    presentation = next(p for p in COMMANDS if p.command_path == ("pair-wavelength",))
    page = WavelengthPairPage(
        presentation,
        cli.commands["pair-wavelength"],
        lambda: tmp_path,
        lambda: (str(groups), str(gaps), ready[0]),
    )
    output, summary = tmp_path / "pairs.csv", tmp_path / "summary.json"
    page.apply_values({"wavelength_um": 10, "output": str(output), "summary": str(summary)})
    output.write_text("mp_id_a,mp_id_b\na,b\n")
    payload = output.read_bytes()
    report = {
        "target_wavelength_um": 10,
        "min_gap_exclusive_eV": None,
        "max_gap_exclusive_eV": None,
        "selected_method": "mixed_sources",
        "allow_mixed_methods": True,
        "pair_count": 1,
        "input_sha256": {
            "groups": [hashlib.sha256(groups.read_bytes()).hexdigest()],
            "gaps": [hashlib.sha256(gaps.read_bytes()).hexdigest()],
        },
        "output_sha256": hashlib.sha256(payload).hexdigest(),
    }
    summary.write_text(json.dumps(report))
    page.refresh_preview()
    assert page.sqs_button.isEnabled()
    handoffs = []
    page.sqs_requested.connect(lambda: handoffs.append(True))
    page.sqs_button.click()
    assert handoffs == [True]
    page.wavelength_edit.setText("8")
    assert not page.sqs_button.isEnabled()
    page.wavelength_edit.setText("10")
    assert page.sqs_button.isEnabled()
    saved = page.argv()
    page.restore_argv(saved)
    assert page.validated_result() == str(output)
    for path in (output, groups, gaps):
        original = path.read_bytes()
        path.write_bytes(original + b"changed")
        assert page.validated_result() is None
        page.open_sqs()
        assert handoffs == [True]
        path.write_bytes(original)
    ready[0] = False
    page.refresh_preview()
    assert not page.sqs_button.isEnabled()
    ready[0] = True
    report["pair_count"] = 0
    output.write_text("mp_id_a,mp_id_b\n")
    report["output_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    summary.write_text(json.dumps(report))
    page.refresh_preview()
    assert not page.sqs_button.isEnabled()
    assert "没有符合条件" in page.status_label.text()
    page.close()
    app.processEvents()


def test_sqs_form_follows_inputs_and_restores_generation_parameters(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from ssscreen.gui.sqs_page import SqsPage

    app = QApplication.instance() or QApplication([])
    current = ["06/current.csv", "02/current.df", False]
    page = SqsPage(
        next(p for p in COMMANDS if p.command_path == ("stability", "sqs-generate")),
        cli.commands["stability"].commands["sqs-generate"],
        lambda: tmp_path,
        lambda: tuple(current),
    )
    page.apply_values(
        {
            "pairs_path": "old.csv",
            "dataset_path": "old.df",
            "target_fractions": [0.25, 0.5],
            "supercell": "2,2,2",
            "backend": "icet",
            "cutoffs": [4.0, 3.0],
            "sqs_steps": 10,
            "seed": 123,
        }
    )
    assert page.pairs_edit.isReadOnly() and page.dataset_edit.isReadOnly()
    assert "old.csv" not in page.argv() and "06/current.csv" in page.argv()
    assert page.cutoffs_edit.isEnabled() and page.steps_edit.isEnabled()
    expected = page._parameters()
    assert expected["supercell"] == [2, 2, 2] and expected["seed"] == 123
    assert expected["target_fractions"] == [0.25, 0.5]
    page.restore_argv(page.argv())
    assert page._parameters() == expected
    current[0] = "06/new.csv"
    page.refresh_preview()
    assert page.pairs_edit.text() == "06/new.csv"
    assert not page.relax_button.isEnabled()
    page.backend_combo.setCurrentIndex(0)
    assert not page.steps_edit.isEnabled()
    page.reset()
    assert page._parameters()["seed"] == 7
    page.close()
    app.processEvents()


def test_relax_form_follows_sqs_and_retains_run_controls(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from ssscreen.gui.relax_page import RelaxPage

    app = QApplication.instance() or QApplication([])
    current = ["07/current.jsonl", "02/current.df", "06/current.csv", False]
    page = RelaxPage(
        next(p for p in COMMANDS if p.command_path == ("stability", "relax")),
        cli.commands["stability"].commands["relax"],
        lambda: tmp_path,
        lambda: tuple(current),
    )
    page.apply_values(
        {
            "manifest_path": "old.jsonl",
            "model_path": "remote.model",
            "model_name": "test",
            "fmax": 0.01,
            "max_steps": 500,
            "dtype": "float64",
            "device": "cuda:0",
            "include_endmembers": False,
            "relax_cell": False,
            "retry_failed": True,
            "limit": 3,
        }
    )
    assert "old.jsonl" not in page.argv() and "07/current.jsonl" in page.argv()
    assert page.manifest_edit.isReadOnly() and page.dataset_edit.isReadOnly()
    expected = page._parameters()
    assert expected["device"] == "cuda:0" and expected["retry_failed"]
    assert not expected["include_endmembers"] and not expected["relax_cell"]
    page.restore_argv(page.argv())
    assert page._parameters() == expected
    page.set_external_mode(True)
    assert page.run_button.text() == "导出外部执行命令"
    assert page.advanced_toggle.isChecked()
    current[0] = "07/new.jsonl"
    page.refresh_preview()
    assert page.manifest_edit.text() == "07/new.jsonl"
    assert not page.mixing_button.isEnabled()
    page.reset()
    assert page.endmembers_check.isChecked() and not page.limit_edit.text()
    manifest = tmp_path / current[0]
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps(
            {
                "status": "written",
                "endpoint_a_structure_path": "a.json",
                "endpoint_b_structure_path": "b.json",
            }
        )
    )
    assert "--dataset" not in page.argv()
    manifest.write_text(json.dumps({"status": "written"}))
    assert page.argv()[page.argv().index("--dataset") + 1] == current[1]
    page.endmembers_check.setChecked(False)
    assert "--dataset" not in page.argv()
    page.close()
    app.processEvents()


def test_stability_pages_follow_live_inputs_and_restore_parameters(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QProcess, QSettings
    from PySide6.QtWidgets import QApplication

    from ssscreen.gui.app import MainWindow
    from ssscreen.gui.stability_page import STABILITY_PATHS, StabilityPage

    app = QApplication.instance() or QApplication([])
    window = MainWindow(
        str(tmp_path), settings=QSettings(str(tmp_path / "gui.ini"), QSettings.IniFormat)
    )
    window._show_command_page(STABILITY_PATHS["11"])  # Restore all upstream forms on direct entry.
    relax = window._pages[("stability", "relax")]
    relax.apply_values(
        {
            "model_path": "model.pt",
            "model_name": "test",
            "dtype": "float64",
            "fmax": 0.01,
            "max_steps": 500,
            "results_path": "08/current.jsonl",
        }
    )
    source = window.dataset_source_page
    source.mp_backend.setCurrentIndex(source.mp_backend.findData("offline"))
    source.mp_offline_db.setText("01/current.db")
    for path in STABILITY_PATHS.values():
        window._show_command_page(path)
        page = window._pages[path]
        assert isinstance(page, StabilityPage)
        page.apply_values(
            {
                "relax_results_path": "old.jsonl",
                "candidate_relax_results_path": "old.jsonl",
                "model_path": "old.model",
                "dtype": "float32",
                "offline_db": "old.db",
                "structure_ids": ["old-structure"],
            }
        )
        assert not {"old.jsonl", "old.model", "old.db", "old-structure"} & set(page.argv())
        assert "08/current.jsonl" in page.argv()
        assert all(edit.isReadOnly() for edit in page.source_edits.values())
    phonon, phase = window._pages[STABILITY_PATHS["10"]], window._pages[STABILITY_PATHS["11"]]
    phonon.apply_values(
        {"supercell": "2,2,2", "mesh": "12,14,16", "device": "cuda", "band_points": 81}
    )
    phase.apply_values({"screening_cutoff": 0.2, "allow_incomplete": False, "device": "cuda"})
    relax.results_edit.setText("08/new.jsonl")
    relax.fmax_edit.setText("0.012")
    source.mp_offline_db.setText("01/new.db")
    for path in STABILITY_PATHS.values():
        assert "08/new.jsonl" in window._pages[path].argv()
        assert any(
            edit.text() == "08/new.jsonl" for edit in window._pages[path].source_edits.values()
        )
    assert phase._parameters()["fmax"] == 0.012
    assert Path(phase._parameters()["offline_db"]) == tmp_path / "01/new.db"
    assert phase._parameters()["dtype"] == "float64"
    before = {path: window._pages[path]._parameters() for path in STABILITY_PATHS.values()}
    snapshot = window._project_settings_snapshot()
    window._active_project.settings = snapshot
    window._apply_project_settings(snapshot)
    assert {path: window._pages[path]._parameters() for path in STABILITY_PATHS.values()} == before
    assert phonon._parameters()["supercell"] == (2, 2, 2)
    assert phonon._parameters()["mesh"] == (12, 14, 16)
    phonon.apply_values({"min_supercell_length": 10})
    assert phonon._parameters()["supercell"] is None
    phonon.restore_argv(snapshot["commands"]["stability phonon-run"])
    assert phonon._parameters()["supercell"] == (2, 2, 2)
    source.mp_backend.setCurrentIndex(source.mp_backend.findData("api"))
    assert "--offline-db" not in phase.argv()
    assert phase.editor("api_timeout").isEnabled()
    for path in STABILITY_PATHS.values():
        window._show_command_page(path)
        window._pages[path].next_button.click()
        assert window.process.state() == QProcess.NotRunning
    recommend = window._pages[("recommend",)].argv()
    assert recommend[recommend.index("--phonons") + 1] == phonon.output_paths()["result"]
    window.close()
    app.processEvents()


def test_native_example_cache_requires_matching_upstream(tmp_path):
    pytest.importorskip("PySide6")
    from ssscreen.gui.ten_micron_page import validate_cache
    from ssscreen.ten_micron import CANDIDATES, digest

    (tmp_path / "01_dataset").mkdir()
    (tmp_path / "01_dataset/mp.df.provenance.json").write_text('{"database":{"sha256":"db"}}')
    candidates = tmp_path / CANDIDATES
    candidates.parent.mkdir()
    candidates.write_text("batch")
    archive = tmp_path / "03_condensed/local/mp-1.json"
    archive.parent.mkdir(parents=True)
    archive.write_text("{}")
    profile = {
        "database_sha256": "db",
        "anchors": {CANDIDATES: digest(candidates)},
        "files": {"03_condensed/local/mp-1.json": digest(archive)},
    }
    validate_cache(tmp_path, profile, 3)
    candidates.write_text("other batch")
    with pytest.raises(ValueError, match="不一致"):
        validate_cache(tmp_path, profile, 3)
