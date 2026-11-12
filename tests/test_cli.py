"""CLI tests for the ``ss-screen`` command surface."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner
from monty.serialization import loadfn
from pymatgen.core import Composition, Lattice, Structure

from ssscreen.cli.app import VERSION_BANNER, cli
from ssscreen.pair.envmatch import StructureGroup

CLI_FIXTURES = Path(__file__).parent / "data" / "cli"


def _screening_df(rows):
    records = []
    for material_id, formula, band_gap, e_hull in rows:
        structure = Structure(
            Lattice.cubic(5.4),
            list(Composition(formula).as_dict().keys()),
            [[0, 0, 0]] * len(Composition(formula)),
        )
        comp = Composition(formula)
        records.append(
            {
                "material_id": material_id,
                "formula": formula,
                "composition": comp,
                "reduced_composition": comp.get_reduced_composition_and_factor()[0],
                "nelems": len(comp),
                "band_gap": band_gap,
                "e_hull": e_hull,
                "structure": structure,
                "source": "fixture",
            }
        )
    return pd.DataFrame.from_records(records).set_index("material_id")


def test_cli_help_lists_current_commands():
    runner = CliRunner()

    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "valence-filter" in result.output
    assert "group" in result.output
    assert "pair" in result.output
    assert "composition-screen" in result.output
    assert "recommend" in result.output


def test_cli_version_matches_release():
    runner = CliRunner()

    result = runner.invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert result.output == f"{VERSION_BANNER}\n\nSS-Screen version 1.0\n"


def test_pair_command_compresses_missing_gap_members_in_lockstep(tmp_path):
    runner = CliRunner()
    output = tmp_path / "pairs.csv"

    result = runner.invoke(
        cli,
        [
            "pair",
            "--groups",
            str(CLI_FIXTURES / "pair_groups.json"),
            "--gaps",
            str(CLI_FIXTURES / "pair_gaps.csv"),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    df = pd.read_csv(output, index_col=0)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["comp_a"] == "CaS"
    assert row["comp_b"] == "CaSe"
    assert row["mp_id_a"] == "mp-low"
    assert row["mp_id_b"] == "mp-mid"
    assert str(row["gap_direct_a"]) == "False"
    assert str(row["gap_direct_b"]) == "True"


def test_condense_help_is_available():
    runner = CliRunner()

    result = runner.invoke(cli, ["condense", "--help"])

    assert result.exit_code == 0
    assert "--input" in result.output
    assert "--df" in result.output
    assert "--output-dir" in result.output


def test_condense_command_invokes_data_layer(monkeypatch, tmp_path):
    from ssscreen.data.condense import CondenseSummary

    runner = CliRunner()
    input_path = tmp_path / "mp-1.json"
    input_path.write_text("{}")
    output_dir = tmp_path / "condensed"
    calls = []

    def fake_condense_paths(
        inputs,
        output_dir_arg,
        overwrite=False,
        manifest_path=None,
        index_path=None,
        continue_on_error=True,
    ):
        calls.append(
            (inputs, output_dir_arg, overwrite, manifest_path, index_path, continue_on_error)
        )
        return CondenseSummary(written=1, skipped=0, failed=0)

    monkeypatch.setattr("ssscreen.data.condense.condense_paths", fake_condense_paths)

    result = runner.invoke(
        cli,
        [
            "condense",
            "--input",
            str(input_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [([input_path], output_dir, False, None, None, True)]
    assert "written=1" in result.output
    assert "skipped=0" in result.output
    assert "failed=0" in result.output


def test_condense_command_invokes_dataframe_archive_mode(monkeypatch, tmp_path):
    from ssscreen.data.condense import CondenseSummary

    runner = CliRunner()
    df_path = tmp_path / "mp.df"
    df_path.write_bytes(b"placeholder")
    output_dir = tmp_path / "condensed"
    manifest = tmp_path / "manifest.jsonl"
    index = tmp_path / "index.csv"
    calls = []

    def fake_condense_dataframe(**kwargs):
        calls.append(kwargs)
        return CondenseSummary(written=2, skipped=1, failed=0)

    monkeypatch.setattr("ssscreen.data.condense.condense_dataframe", fake_condense_dataframe)

    result = runner.invoke(
        cli,
        [
            "condense",
            "--df",
            str(df_path),
            "--structure-column",
            "structure",
            "--limit",
            "3",
            "--output-dir",
            str(output_dir),
            "--manifest",
            str(manifest),
            "--index",
            str(index),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        {
            "df_path": df_path,
            "output_dir": output_dir,
            "structure_col": "structure",
            "material_id_col": None,
            "limit": 3,
            "overwrite": False,
            "manifest_path": manifest,
            "index_path": index,
            "continue_on_error": True,
        }
    ]
    assert "written=2" in result.output
    assert "skipped=1" in result.output


def test_condense_cli_stop_file_exits_without_claiming_completion(monkeypatch, tmp_path):
    from ssscreen.data.condense import CondenseSummary

    source = tmp_path / "source.df"
    source.touch()
    stop = tmp_path / "stop.request"
    calls = []

    def stopped(**kwargs):
        calls.append(kwargs)
        return CondenseSummary(written=1, failed=1, pending=3, stopped=True)

    monkeypatch.setattr("ssscreen.data.condense.condense_dataframe", stopped)
    result = CliRunner().invoke(
        cli,
        [
            "condense",
            "--df",
            str(source),
            "--output-dir",
            str(tmp_path / "condensed"),
            "--stop-file",
            str(stop),
        ],
    )
    assert result.exit_code == 130
    assert calls[0]["stop_file"] == stop
    assert "stopped=True pending=3" in result.output
    assert "preserved" in result.output


def test_condense_index_command_writes_archive_index(monkeypatch, tmp_path):
    runner = CliRunner()
    condensed_dir = tmp_path / "condensed"
    condensed_dir.mkdir()
    output = tmp_path / "index.csv"
    calls = []

    def fake_build_archive_index(condensed_dir_arg, index_path):
        calls.append((condensed_dir_arg, index_path))
        return pd.DataFrame([{"material_id": "mp-1", "status": "present"}])

    monkeypatch.setattr("ssscreen.data.condense.build_archive_index", fake_build_archive_index)

    result = runner.invoke(
        cli,
        [
            "condense-index",
            "--condensed-dir",
            str(condensed_dir),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [(condensed_dir, output)]
    assert "Indexed 1 condensed files" in result.output


def test_condense_validate_command_writes_validation_report(monkeypatch, tmp_path):
    runner = CliRunner()
    condensed_dir = tmp_path / "condensed"
    condensed_dir.mkdir()
    output = tmp_path / "validation.csv"
    calls = []

    def fake_validate_archive(condensed_dir_arg, index_path):
        calls.append((condensed_dir_arg, index_path))
        return pd.DataFrame(
            [
                {"material_id": "mp-1", "status": "valid"},
                {"material_id": "mp-2", "status": "invalid"},
            ]
        )

    monkeypatch.setattr("ssscreen.data.condense.validate_archive", fake_validate_archive)

    result = runner.invoke(
        cli,
        [
            "condense-validate",
            "--condensed-dir",
            str(condensed_dir),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [(condensed_dir, output)]
    assert "valid=1" in result.output
    assert "invalid=1" in result.output


def test_composition_screen_writes_candidate_table_and_summary(tmp_path):
    runner = CliRunner()
    df = _screening_df(
        [
            ("mp-1", "CaS", 0.0, 0.0),
            ("mp-2", "CaSe", 0.3, 0.0),
            ("mp-3", "SrS", 0.4, 0.0),
            ("mp-4", "MgO", 0.1, 0.2),
            ("mp-5", "CaTe", 1.2, 0.0),
        ]
    )
    input_path = tmp_path / "dataset.df"
    output = tmp_path / "composition_candidates.csv"
    summary = tmp_path / "composition_summary.json"
    df.to_pickle(input_path)

    result = runner.invoke(
        cli,
        [
            "composition-screen",
            "--df",
            str(input_path),
            "--nelems",
            "2",
            "--max-bandgap",
            "1.0",
            "--max-e-hull",
            "0.01",
            "--output",
            str(output),
            "--summary",
            str(summary),
        ],
    )

    assert result.exit_code == 0, result.output
    candidates = pd.read_csv(output)
    assert set(candidates["template"]) == {"CaX1", "SX1"}
    assert set(candidates["material_id"]) == {"mp-1", "mp-2", "mp-3"}
    assert set(candidates.columns) >= {
        "template",
        "material_id",
        "x_element",
        "formula",
        "band_gap",
        "e_hull",
        "source",
    }

    report = loadfn(summary)
    assert report["input_rows"] == 5
    assert report["selected_rows"] == 3
    assert report["template_count"] == 2
    assert report["candidate_rows"] == 4


def test_composition_multi_select_exports_original_unique_structures(tmp_path):
    df = _screening_df(
        [
            ("mp-1", "CaS", 0.0, 0.0),
            ("mp-2", "CaSe", 0.3, 0.0),
            ("mp-3", "SrS", 0.4, 0.0),
            ("mp-4", "CaSnO", 0.1, 0.0),
            ("mp-5", "SrSnO", 0.3, 0.0),
            ("mp-6", "BaSnO", 0.2, 0.1),
            ("mp-7", "CaTe", 1.0, 0.0),
        ]
    )
    source, output = tmp_path / "mp.df", tmp_path / "candidates.csv"
    summary, structures = tmp_path / "summary.json", tmp_path / "candidates.df"
    df.to_pickle(source)
    result = CliRunner().invoke(
        cli,
        [
            "composition-screen",
            "--df",
            str(source),
            "--nelems",
            "2",
            "--nelems",
            "3",
            "--nelems",
            "2",
            "--output",
            str(output),
            "--summary",
            str(summary),
            "--structures-output",
            str(structures),
        ],
    )
    assert result.exit_code == 0, result.output
    table, exported, report = pd.read_csv(output), pd.read_pickle(structures), loadfn(summary)
    assert len(table) == 6  # CaS participates in two templates.
    assert set(table["nelems"]) == {2, 3}
    assert set(exported.index) == {"mp-1", "mp-2", "mp-3", "mp-4", "mp-5"}
    assert exported.index.is_unique and exported.index.name == df.index.name
    pd.testing.assert_frame_equal(exported, df.loc[exported.index])
    assert [s.as_dict() for s in exported.structure] == [
        s.as_dict() for s in df.loc[exported.index].structure
    ]
    assert report["input_rows"] == 7
    assert report["nelems"] == [2, 3]
    assert report["unique_candidate_materials"] == 5
    assert report["by_nelems"]["2"]["candidate_rows"] == 4
    assert report["by_nelems"]["3"]["candidate_rows"] == 2


@pytest.mark.parametrize(
    "problem", ["duplicate_ids", "missing_structure", "same_outputs", "overwrite_input"]
)
def test_composition_export_rejects_ambiguous_or_destructive_inputs(tmp_path, problem):
    df = _screening_df([("mp-1", "CaS", 0.0, 0.0), ("mp-2", "CaSe", 0.3, 0.0)])
    if problem == "duplicate_ids":
        df = pd.concat([df, df])
    if problem == "missing_structure":
        df = df.drop(columns=["structure"])
    source, output, structures = tmp_path / "source.df", tmp_path / "out.csv", tmp_path / "out.df"
    df.to_pickle(source)
    original = source.read_bytes()
    if problem == "same_outputs":
        structures = output
    if problem == "overwrite_input":
        structures = source
    result = CliRunner().invoke(
        cli,
        [
            "composition-screen",
            "--df",
            str(source),
            "--output",
            str(output),
            "--structures-output",
            str(structures),
        ],
    )
    assert result.exit_code != 0
    assert not output.exists()
    assert source.read_bytes() == original


@pytest.mark.parametrize("count", ["1", "4", "5", "2.5"])
def test_composition_only_binary_or_ternary(tmp_path, count):
    source = tmp_path / "source.df"
    source.touch()
    result = CliRunner().invoke(
        cli,
        [
            "composition-screen",
            "--df",
            str(source),
            "--nelems",
            count,
            "--output",
            str(tmp_path / "out.csv"),
        ],
    )
    assert result.exit_code == 2


def test_composition_empty_selection_writes_empty_structure_table(tmp_path):
    df = _screening_df([("mp-1", "CaS", 1.2, 0.0), ("mp-2", "CaSe", 1.3, 0.0)])
    source, structures = tmp_path / "source.df", tmp_path / "candidates.df"
    df.to_pickle(source)
    result = CliRunner().invoke(
        cli,
        [
            "composition-screen",
            "--df",
            str(source),
            "--nelems",
            "2",
            "--nelems",
            "3",
            "--output",
            str(tmp_path / "out.csv"),
            "--structures-output",
            str(structures),
        ],
    )
    assert result.exit_code == 0, result.output
    exported = pd.read_pickle(structures)
    assert exported.empty
    assert list(exported.columns) == list(df.columns)


def test_dataset_mp_command_defaults_to_offline_loader(monkeypatch, tmp_path):
    runner = CliRunner()
    output = tmp_path / "mp.df"
    calls = []

    def fake_load_mp_dataset(output, max_e_hull, backend, offline_db, provenance_path):
        calls.append((output, max_e_hull, backend, offline_db, provenance_path))
        df = _screening_df([("mp-1", "CaS", 0.0, 0.0)])
        df.to_pickle(output)
        return df

    monkeypatch.setattr("ssscreen.data.mp.load_mp_dataset", fake_load_mp_dataset)

    result = runner.invoke(
        cli,
        [
            "dataset",
            "mp",
            "--output",
            str(output),
            "--max-e-hull",
            "0.02",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [(output, 0.02, "offline", None, None)]
    assert "Wrote 1 MP rows" in result.output
    assert f"provenance={output}.provenance.json" in result.output


def test_dataset_mp_command_accepts_explicit_api_backend(monkeypatch, tmp_path):
    runner = CliRunner()
    output = tmp_path / "mp.df"
    calls = []

    def fake_load_mp_dataset(output, max_e_hull, backend, offline_db, provenance_path):
        calls.append((output, max_e_hull, backend, offline_db, provenance_path))
        df = _screening_df([("mp-1", "CaS", 0.0, 0.0)])
        df.to_pickle(output)
        return df

    monkeypatch.setattr("ssscreen.data.mp.load_mp_dataset", fake_load_mp_dataset)

    result = runner.invoke(
        cli,
        [
            "dataset",
            "mp",
            "--backend",
            "api",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [(output, 0.01, "api", None, None)]


def test_dataset_wbm_command_invokes_loader(monkeypatch, tmp_path):
    runner = CliRunner()
    xyz = tmp_path / "wbm.xyz"
    xyz.write_text("placeholder")
    output = tmp_path / "wbm.df"
    calls = []

    def fake_load_wbm_dataset(xyz_path, output, summary_path):
        calls.append((xyz_path, output, summary_path))
        df = _screening_df([("wbm-1", "CaS", 0.0, 0.0)])
        df.to_pickle(output)
        return df

    monkeypatch.setattr("ssscreen.data.wbm.load_wbm_dataset", fake_load_wbm_dataset)

    result = runner.invoke(
        cli,
        [
            "dataset",
            "wbm",
            "--xyz",
            str(xyz),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [(xyz, output, None)]
    assert "Wrote 1 WBM rows" in result.output


def test_dataset_structures_command_invokes_loader(monkeypatch, tmp_path):
    runner = CliRunner()
    input_dir = tmp_path / "structures"
    input_dir.mkdir()
    output = tmp_path / "local.df"
    provenance = tmp_path / "local.provenance.json"
    metadata = tmp_path / "metadata.csv"
    metadata.write_text("material_id,band_gap,e_hull\n")
    calls = []

    def fake_load_structure_dataset(**kwargs):
        calls.append(kwargs)
        df = _screening_df([("CaS", "CaS", 0.0, 0.0)])
        df.to_pickle(kwargs["output"])
        return df

    monkeypatch.setattr(
        "ssscreen.data.structures.load_structure_dataset",
        fake_load_structure_dataset,
    )

    result = runner.invoke(
        cli,
        [
            "dataset",
            "structures",
            "--input-dir",
            str(input_dir),
            "--metadata",
            str(metadata),
            "--band-gap-default",
            "0.1",
            "--e-hull-default",
            "0.02",
            "--source",
            "local-fixture",
            "--output",
            str(output),
            "--provenance",
            str(provenance),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        {
            "input_dirs": [input_dir],
            "inputs": [],
            "metadata_path": metadata,
            "band_gap_default": 0.1,
            "e_hull_default": 0.02,
            "source": "local-fixture",
            "output": output,
            "provenance_path": provenance,
        }
    ]
    assert "Wrote 1 local structure rows" in result.output


def test_structure_match_command_writes_groups_and_summary(monkeypatch, tmp_path):
    runner = CliRunner()
    candidates = tmp_path / "composition_candidates.csv"
    candidates.write_text(
        "template,material_id,x_element,formula,composition,band_gap,e_hull,source\n"
    )
    condensed_dir = tmp_path / "condensed"
    condensed_dir.mkdir()
    output = tmp_path / "groups.json"
    summary = tmp_path / "summary.json"
    calls = []

    def fake_match_structure_candidates(candidates_arg, condensed_dirs, min_x_elements):
        calls.append((candidates_arg, condensed_dirs, min_x_elements))
        return (
            [
                StructureGroup(
                    entry_idx=[0, 1],
                    A_elements=[["Ca"], ["Ca"]],
                    compositions=["CaS", "CaSe"],
                    group_size=2,
                    X_element=["S", "Se"],
                    mp_ids=["mp-1", "mp-2"],
                    group_repr="descriptor",
                    band_gaps=[0.0, 0.3],
                )
            ],
            {
                "candidate_rows": 2,
                "template_count": 1,
                "missing_descriptions": 0,
                "raw_group_count": 1,
                "group_count": 1,
            },
        )

    monkeypatch.setattr(
        "ssscreen.pair.structure_match.match_structure_candidates",
        fake_match_structure_candidates,
    )

    result = runner.invoke(
        cli,
        [
            "structure-match",
            "--candidates",
            str(candidates),
            "--condensed-dir",
            str(condensed_dir),
            "--output",
            str(output),
            "--summary",
            str(summary),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [(candidates, [condensed_dir], 2)]
    groups = loadfn(output)
    assert groups[0]["mp_ids"] == ["mp-1", "mp-2"]
    report = loadfn(summary)
    assert report["group_count"] == 1
    assert "Wrote 1 structure groups" in result.output


def test_gap_export_command_writes_candidate_table(monkeypatch, tmp_path):
    runner = CliRunner()
    groups = tmp_path / "groups.json"
    groups.write_text("[]")
    dataset = tmp_path / "dataset.df"
    dataset.write_bytes(b"placeholder")
    output = tmp_path / "gap_candidates.csv"
    structure_dir = tmp_path / "structures"
    results_template = tmp_path / "gap_results_template.csv"
    method_metadata_template = tmp_path / "method_metadata.json"
    calls = []

    def fake_export_gap_candidates(**kwargs):
        calls.append(kwargs)
        df = pd.DataFrame([{"material_id": "mp-1", "method": "hse06"}])
        df.to_csv(kwargs["output"], index=False)
        return df

    monkeypatch.setattr(
        "ssscreen.pair.gap_export.export_gap_candidates", fake_export_gap_candidates
    )

    result = runner.invoke(
        cli,
        [
            "gap-export",
            "--groups",
            str(groups),
            "--dataset",
            str(dataset),
            "--method",
            "hse06",
            "--structure-dir",
            str(structure_dir),
            "--structure-format",
            "json",
            "--structure-format",
            "cif",
            "--results-template",
            str(results_template),
            "--method-metadata-template",
            str(method_metadata_template),
            "--max-natoms",
            "30",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        {
            "groups_path": groups,
            "dataset_path": dataset,
            "output": output,
            "method": "hse06",
            "structure_dir": structure_dir,
            "structure_formats": ("json", "cif"),
            "results_template": results_template,
            "method_metadata_template": method_metadata_template,
            "structure_col": "structure",
            "max_natoms": 30,
        }
    ]
    assert "Wrote 1 gap candidates" in result.output


def test_gap_validate_command_reports_schema_status(monkeypatch, tmp_path):
    runner = CliRunner()
    gaps = tmp_path / "gap_results.csv"
    gaps.write_text("material_id,formula,method,band_gap,is_direct,transition,status\n")
    tasks = tmp_path / "gap_tasks.csv"
    tasks.write_text("task_id,material_id,formula,method,structure_sha256\n")
    normalized = tmp_path / "normalized.csv"
    rejected = tmp_path / "rejected.csv"
    report = tmp_path / "report.json"
    calls = []

    def fake_validate_gap_results(path, **kwargs):
        calls.append((path, kwargs))
        frame = pd.DataFrame([{"material_id": "mp-1"}])
        frame.attrs["validation_report"] = {"accepted_count": 1, "rejected_count": 0}
        return frame

    monkeypatch.setattr("ssscreen.pair.gap_export.validate_gap_results", fake_validate_gap_results)

    result = runner.invoke(
        cli,
        [
            "gap-validate",
            "--gaps",
            str(gaps),
            "--tasks",
            str(tasks),
            "--output",
            str(normalized),
            "--rejected",
            str(rejected),
            "--report",
            str(report),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        (
            gaps,
            {
                "tasks_path": tasks,
                "method_metadata_path": None,
                "output_path": normalized,
                "rejected_path": rejected,
                "report_path": report,
            },
        )
    ]
    assert "accepted=1 rejected=0" in result.output


def test_gap_collect_vasp_command_invokes_batch_collector(monkeypatch, tmp_path):
    runner = CliRunner()
    tasks = tmp_path / "gap_tasks.csv"
    tasks.write_text("task_id,material_id,formula,method,structure_sha256\n")
    results_dir = tmp_path / "vasp-results"
    results_dir.mkdir()
    output = tmp_path / "gap_results.csv"
    report = tmp_path / "collection_report.json"
    calls = []

    def fake_collect_vasp_gap_results(**kwargs):
        calls.append(kwargs)
        return (
            pd.DataFrame([{"task_id": "gap-1", "status": "success"}]),
            {
                "selected_task_count": 2,
                "missing_count": 1,
                "status_counts": {"success": 1},
            },
        )

    monkeypatch.setattr(
        "ssscreen.pair.gap_collect_vasp.collect_vasp_gap_results",
        fake_collect_vasp_gap_results,
    )

    result = runner.invoke(
        cli,
        [
            "gap-collect-vasp",
            "--tasks",
            str(tasks),
            "--results-dir",
            str(results_dir),
            "--task-id",
            "gap-1",
            "--output",
            str(output),
            "--report",
            str(report),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        {
            "tasks_path": tasks,
            "results_dir": results_dir,
            "output_path": output,
            "report_path": report,
            "method_metadata_path": None,
            "task_ids": ("gap-1",),
        }
    ]
    assert "Scanned 2 VASP tasks and wrote 1 rows" in result.output
    assert f"report={report}" in result.output


def test_gap_validate_command_fails_when_rows_are_rejected(monkeypatch, tmp_path):
    runner = CliRunner()
    gaps = tmp_path / "gap_results.csv"
    gaps.write_text("material_id,formula,method,band_gap,is_direct,transition,status\n")

    def fake_validate_gap_results(path, **kwargs):
        frame = pd.DataFrame()
        frame.attrs["validation_report"] = {"accepted_count": 0, "rejected_count": 2}
        return frame

    monkeypatch.setattr("ssscreen.pair.gap_export.validate_gap_results", fake_validate_gap_results)

    result = runner.invoke(cli, ["gap-validate", "--gaps", str(gaps)])

    assert result.exit_code != 0
    assert "rejected 2 malformed row(s)" in result.output


def test_pair_command_accepts_external_gap_results_schema(monkeypatch, tmp_path):
    runner = CliRunner()
    groups = tmp_path / "groups.json"
    groups.write_text("[]")
    gaps = tmp_path / "gap_results.csv"
    gaps.write_text("material_id,formula,method,band_gap,is_direct,transition,status\n")
    output = tmp_path / "pairs.csv"
    summary = tmp_path / "summary.json"
    calls = []

    def fake_generate_pairs_from_gap_results(**kwargs):
        calls.append(kwargs)
        df = pd.DataFrame([{"mp_id_a": "mp-1", "mp_id_b": "mp-2"}])
        df.to_csv(kwargs["output"])
        return df, {"pair_count": 1, "covered_materials": 2, "materials_in_groups": 2}

    monkeypatch.setattr(
        "ssscreen.pair.gap_feedback.generate_pairs_from_gap_results",
        fake_generate_pairs_from_gap_results,
    )

    result = runner.invoke(
        cli,
        [
            "pair",
            "--groups",
            str(groups),
            "--gap-results",
            str(gaps),
            "--method",
            "hse06",
            "--summary",
            str(summary),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls[0]["groups_path"] == groups
    assert calls[0]["gap_paths"] == (gaps,)
    assert calls[0]["output"] == output
    assert calls[0]["summary"] == summary
    assert calls[0]["method"] == "hse06"
    assert "Wrote 1 pairs" in result.output


def test_gap_compare_command_writes_method_comparison(monkeypatch, tmp_path):
    runner = CliRunner()
    groups = tmp_path / "groups.json"
    groups.write_text("[]")
    gaps = tmp_path / "gap_results.csv"
    gaps.write_text("material_id,formula,method,band_gap,is_direct,transition,status\n")
    output_dir = tmp_path / "comparison"
    summary = tmp_path / "comparison.json"
    calls = []

    def fake_compare_gap_methods(**kwargs):
        calls.append(kwargs)
        kwargs["summary"].write_text("{}")
        return {"methods": ["hse06", "mbj"], "pair_counts": {"hse06": 1, "mbj": 0}}

    monkeypatch.setattr("ssscreen.pair.gap_feedback.compare_gap_methods", fake_compare_gap_methods)

    result = runner.invoke(
        cli,
        [
            "gap-compare",
            "--groups",
            str(groups),
            "--gap-results",
            str(gaps),
            "--output-dir",
            str(output_dir),
            "--summary",
            str(summary),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls[0]["groups_path"] == groups
    assert calls[0]["gap_paths"] == (gaps,)
    assert calls[0]["output_dir"] == output_dir
    assert calls[0]["summary"] == summary
    assert "Compared 2 methods" in result.output


def test_stability_sqs_generate_command_writes_artifacts(monkeypatch, tmp_path):
    runner = CliRunner()
    pairs = tmp_path / "pairs.csv"
    pairs.write_text("comp_a,comp_b,mp_id_a,mp_id_b\n")
    dataset = tmp_path / "dataset.df"
    dataset.write_bytes(b"placeholder")
    output_dir = tmp_path / "sqs"
    manifest = tmp_path / "manifest.jsonl"
    calls = []

    def fake_generate_sqs_inputs(**kwargs):
        calls.append(kwargs)
        kwargs["manifest_path"].write_text('{"status":"written"}\n')
        return [{"status": "written"}, {"status": "skipped"}]

    monkeypatch.setattr("ssscreen.stability.sqs.generate_sqs_inputs", fake_generate_sqs_inputs)

    result = runner.invoke(
        cli,
        [
            "stability",
            "sqs-generate",
            "--pairs",
            str(pairs),
            "--dataset",
            str(dataset),
            "--target-fraction",
            "0.25",
            "--target-fraction",
            "0.5",
            "--backend",
            "icet",
            "--cutoff",
            "4.0",
            "--sqs-steps",
            "10",
            "--supercell",
            "2,1,1",
            "--seed",
            "11",
            "--output-dir",
            str(output_dir),
            "--manifest",
            str(manifest),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        {
            "pairs_path": pairs,
            "dataset_path": dataset,
            "output_dir": output_dir,
            "manifest_path": manifest,
            "target_fractions": (0.25, 0.5),
            "supercell": (2, 1, 1),
            "seed": 11,
            "backend": "icet",
            "cutoffs": (4.0,),
            "sqs_steps": 10,
        }
    ]
    assert "written=1" in result.output
    assert "skipped=1" in result.output


def test_stability_sqs_generate_rejects_invalid_target_fraction(tmp_path):
    runner = CliRunner()
    pairs = tmp_path / "pairs.csv"
    pairs.write_text("comp_a,comp_b,mp_id_a,mp_id_b\n")
    dataset = tmp_path / "dataset.df"
    dataset.write_bytes(b"placeholder")

    result = runner.invoke(
        cli,
        [
            "stability",
            "sqs-generate",
            "--pairs",
            str(pairs),
            "--dataset",
            str(dataset),
            "--target-fraction",
            "1.1",
            "--output-dir",
            str(tmp_path / "sqs"),
            "--manifest",
            str(tmp_path / "manifest.jsonl"),
        ],
    )

    assert result.exit_code != 0
    assert "0.0<=x<=1.0" in result.output


def test_stability_relax_command_passes_mace_settings(monkeypatch, tmp_path):
    runner = CliRunner()
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text('{"status":"written"}\n')
    model = tmp_path / "mace.model"
    model.write_bytes(b"model")
    output_dir = tmp_path / "relax"
    results = output_dir / "results.jsonl"
    backend_calls = []
    relax_calls = []

    class FakeMaceBackend:
        def __init__(self, model_path, **kwargs):
            backend_calls.append((model_path, kwargs))

    def fake_relax_manifest(**kwargs):
        relax_calls.append(kwargs)
        kwargs["results_path"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["results_path"].write_text('{"status":"success"}\n')
        return [
            {"status": "success"},
            {"status": "not_converged"},
            {"status": "failed"},
        ]

    monkeypatch.setattr("ssscreen.stability.mlp.MaceRelaxationBackend", FakeMaceBackend)
    monkeypatch.setattr("ssscreen.stability.relax.relax_manifest", fake_relax_manifest)

    result = runner.invoke(
        cli,
        [
            "stability",
            "relax",
            "--manifest",
            str(manifest),
            "--include-endmembers",
            "--model-path",
            str(model),
            "--model-name",
            "mace-mpa-0-medium",
            "--device",
            "cuda:0",
            "--dtype",
            "float32",
            "--fmax",
            "0.04",
            "--max-steps",
            "250",
            "--positions-only",
            "--limit",
            "3",
            "--retry-failed",
            "--output-dir",
            str(output_dir),
            "--results",
            str(results),
        ],
    )

    assert result.exit_code == 0, result.output
    assert backend_calls == [
        (
            model,
            {
                "device": "cuda:0",
                "dtype": "float32",
                "model_name": "mace-mpa-0-medium",
            },
        )
    ]
    assert relax_calls[0]["manifest_path"] == manifest
    assert relax_calls[0]["backend"].__class__ is FakeMaceBackend
    assert relax_calls[0]["include_endmembers"] is True
    assert relax_calls[0]["fmax"] == 0.04
    assert relax_calls[0]["max_steps"] == 250
    assert relax_calls[0]["relax_cell"] is False
    assert relax_calls[0]["limit"] == 3
    assert relax_calls[0]["retry_failed"] is True
    assert "success=1" in result.output
    assert "not_converged=1" in result.output
    assert "failed=1" in result.output


def test_stability_mixing_enthalpy_command_writes_outputs(monkeypatch, tmp_path):
    runner = CliRunner()
    pairs = tmp_path / "pairs.csv"
    pairs.write_text("comp_a,comp_b,mp_id_a,mp_id_b\n")
    relax_results = tmp_path / "relaxation_results.jsonl"
    relax_results.write_text("{}\n")
    output = tmp_path / "mixing_enthalpy.csv"
    summary_path = tmp_path / "mixing_summary.json"
    calls = []

    def fake_calculate_mixing_enthalpies(**kwargs):
        calls.append(kwargs)
        kwargs["output_path"].write_text("status\nsuccess\n")
        kwargs["summary_path"].write_text("{}\n")
        return pd.DataFrame([{"status": "success"}]), {
            "success_count": 1,
            "failed_count": 2,
        }

    monkeypatch.setattr(
        "ssscreen.stability.thermodynamics.calculate_mixing_enthalpies",
        fake_calculate_mixing_enthalpies,
    )

    result = runner.invoke(
        cli,
        [
            "stability",
            "mixing-enthalpy",
            "--pairs",
            str(pairs),
            "--relax-results",
            str(relax_results),
            "--output",
            str(output),
            "--summary",
            str(summary_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        {
            "pairs_path": pairs,
            "relax_results_path": relax_results,
            "output_path": output,
            "summary_path": summary_path,
        }
    ]
    assert "success=1" in result.output
    assert "failed=2" in result.output


def test_stability_help_lists_phonon_commands():
    result = CliRunner().invoke(cli, ["stability", "--help"])

    assert result.exit_code == 0, result.output
    assert "phonon-export" in result.output
    assert "phonon-forces" in result.output
    assert "phonon-collect" in result.output
    assert "phonon-run" in result.output
    assert "competing-export" in result.output
    assert "competing-relax" in result.output
    assert "convex-hull" in result.output
    assert "phase-diagram" in result.output


def test_stability_phonon_export_passes_generation_settings(monkeypatch, tmp_path):
    runner = CliRunner()
    relax_results = tmp_path / "relaxation_results.jsonl"
    relax_results.write_text("{}\n")
    output_dir = tmp_path / "phonon-inputs"
    manifest = tmp_path / "phonon_jobs.jsonl"
    calls = []

    def fake_export_phonon_tasks(**kwargs):
        calls.append(kwargs)
        kwargs["manifest_path"].write_text("{}\n")
        return [
            {"status": "written", "phonon_id": "p1", "task_role": "reference"},
            {"status": "written", "phonon_id": "p1", "task_role": "displacement"},
        ]

    monkeypatch.setattr("ssscreen.stability.phonon.export_phonon_tasks", fake_export_phonon_tasks)
    result = runner.invoke(
        cli,
        [
            "stability",
            "phonon-export",
            "--relax-results",
            str(relax_results),
            "--structure-id",
            "sqs-1",
            "--supercell",
            "2,1,1",
            "--displacement",
            "0.02",
            "--max-supercell-atoms",
            "200",
            "--allow-loose-input",
            "--output-dir",
            str(output_dir),
            "--manifest",
            str(manifest),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls[0]["relax_results_path"] == relax_results
    assert calls[0]["structure_ids"] == ("sqs-1",)
    assert calls[0]["supercell"] == (2, 1, 1)
    assert calls[0]["displacement_distance"] == 0.02
    assert calls[0]["max_supercell_atoms"] == 200
    assert calls[0]["allow_loose_input"] is True
    assert "tasks=2" in result.output


def test_stability_phonon_run_uses_mace_and_named_settings(monkeypatch, tmp_path):
    runner = CliRunner()
    relax_results = tmp_path / "relaxation_results.jsonl"
    relax_results.write_text("{}\n")
    model = tmp_path / "mace.model"
    model.write_bytes(b"model")
    output_dir = tmp_path / "phonons"
    backend_calls = []
    pipeline_calls = []

    class FakeMaceBackend:
        def __init__(self, model_path, **kwargs):
            backend_calls.append((model_path, kwargs))

    def fake_run_phonon_pipeline(**kwargs):
        pipeline_calls.append(kwargs)
        return pd.DataFrame([{"status": "success"}]), {
            "dynamical_status_counts": {
                "stable": 1,
                "unstable": 0,
                "uncertain": 0,
                "failed": 0,
            }
        }

    monkeypatch.setattr("ssscreen.stability.mlp.MaceRelaxationBackend", FakeMaceBackend)
    monkeypatch.setattr("ssscreen.stability.phonon.run_phonon_pipeline", fake_run_phonon_pipeline)
    result = runner.invoke(
        cli,
        [
            "stability",
            "phonon-run",
            "--relax-results",
            str(relax_results),
            "--structure-id",
            "sqs-1",
            "--supercell",
            "2,1,1",
            "--mesh",
            "6,6,6",
            "--displacement",
            "0.02",
            "--imaginary-tolerance",
            "0.15",
            "--model-path",
            str(model),
            "--device",
            "cuda:0",
            "--dtype",
            "float64",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    assert backend_calls == [(model, {"device": "cuda:0", "dtype": "float64", "model_name": None})]
    call = pipeline_calls[0]
    assert call["relax_results_path"] == relax_results
    assert call["structure_ids"] == ("sqs-1",)
    assert call["supercell"] == (2, 1, 1)
    assert call["settings"].mesh == (6, 6, 6)
    assert call["settings"].displacement_distance == 0.02
    assert call["settings"].imaginary_tolerance_thz == 0.15
    assert "stable=1" in result.output


def test_stability_competing_export_prompts_for_hidden_api_key(monkeypatch, tmp_path):
    runner = CliRunner()
    relax_results = tmp_path / "relaxation_results.jsonl"
    relax_results.write_text("{}\n")
    output_dir = tmp_path / "competing-inputs"
    manifest = tmp_path / "competing.jsonl"
    report_path = tmp_path / "export-summary.json"
    calls = []

    def fake_export_competing_phases(**kwargs):
        calls.append(kwargs)
        kwargs["manifest_path"].write_text("{}\n")
        kwargs["report_path"].write_text("{}\n")
        return (
            [{"status": "written"}],
            {
                "chemical_systems": ["Li-O"],
                "fetched_entry_count": 3,
                "status_counts": {"written": 3},
                "query_failure_count": 0,
            },
        )

    monkeypatch.setattr(
        "ssscreen.stability.competing.export_competing_phases",
        fake_export_competing_phases,
    )
    result = runner.invoke(
        cli,
        [
            "stability",
            "competing-export",
            "--relax-results",
            str(relax_results),
            "--structure-id",
            "sqs-1",
            "--mp-max-e-hull",
            "0.05",
            "--thermo-type",
            "R2SCAN",
            "--max-phase-atoms",
            "80",
            "--output-dir",
            str(output_dir),
            "--manifest",
            str(manifest),
            "--report",
            str(report_path),
        ],
        input="testing-secret\n",
    )

    assert result.exit_code == 0, result.output
    assert "testing-secret" not in result.output
    assert calls[0]["api_key"] == "testing-secret"
    assert calls[0]["mp_backend"] == "api"
    assert calls[0]["offline_db"] is None
    assert calls[0]["structure_ids"] == ("sqs-1",)
    assert calls[0]["settings"].thermo_type == "R2SCAN"
    assert calls[0]["settings"].max_mp_energy_above_hull == 0.05
    assert calls[0]["settings"].max_competing_phase_atoms == 80
    assert "written=3" in result.output


def test_stability_competing_export_uses_mp_api_key_env(monkeypatch, tmp_path):
    runner = CliRunner()
    relax_results = tmp_path / "relaxation_results.jsonl"
    relax_results.write_text("{}\n")
    calls = []

    def fake_export_competing_phases(**kwargs):
        calls.append(kwargs)
        return (
            [{"status": "written"}],
            {
                "chemical_systems": ["Li-O"],
                "fetched_entry_count": 3,
                "status_counts": {"written": 3},
                "query_failure_count": 0,
            },
        )

    monkeypatch.setenv("MP_API_KEY", "env-secret")
    monkeypatch.setattr(
        "ssscreen.stability.competing.export_competing_phases",
        fake_export_competing_phases,
    )
    result = runner.invoke(
        cli,
        [
            "stability",
            "competing-export",
            "--relax-results",
            str(relax_results),
            "--output-dir",
            str(tmp_path / "inputs"),
            "--manifest",
            str(tmp_path / "manifest.jsonl"),
            "--report",
            str(tmp_path / "report.json"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Materials Project API key" not in result.output
    assert "env-secret" not in result.output
    assert calls[0]["api_key"] == "env-secret"


def test_stability_competing_export_uses_offline_database_without_prompt(monkeypatch, tmp_path):
    runner = CliRunner()
    relax_results = tmp_path / "relaxation_results.jsonl"
    relax_results.write_text("{}\n")
    database = tmp_path / "default.db"
    database.write_bytes(b"sqlite")
    calls = []

    def fake_export_competing_phases(**kwargs):
        calls.append(kwargs)
        return (
            [{"status": "written"}],
            {
                "chemical_systems": ["Li-O"],
                "fetched_entry_count": 3,
                "status_counts": {"written": 3},
                "query_failure_count": 0,
            },
        )

    monkeypatch.setattr(
        "ssscreen.stability.competing.export_competing_phases",
        fake_export_competing_phases,
    )
    result = runner.invoke(
        cli,
        [
            "stability",
            "competing-export",
            "--relax-results",
            str(relax_results),
            "--mp-backend",
            "offline",
            "--offline-db",
            str(database),
            "--output-dir",
            str(tmp_path / "inputs"),
            "--manifest",
            str(tmp_path / "manifest.jsonl"),
            "--report",
            str(tmp_path / "report.json"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Materials Project API key" not in result.output
    assert calls[0]["api_key"] is None
    assert calls[0]["mp_backend"] == "offline"
    assert calls[0]["offline_db"] == database
    assert "competing-phase export (offline)" in result.output


def test_stability_convex_hull_passes_strict_settings(monkeypatch, tmp_path):
    runner = CliRunner()
    candidate = tmp_path / "candidate.jsonl"
    manifest = tmp_path / "manifest.jsonl"
    competing = tmp_path / "competing.jsonl"
    for path in (candidate, manifest, competing):
        path.write_text("{}\n")
    calls = []

    def fake_collect_convex_hulls(**kwargs):
        calls.append(kwargs)
        return (
            pd.DataFrame([{"status": "success"}]),
            pd.DataFrame(),
            {
                "success_count": 1,
                "uncertain_count": 0,
                "failed_count": 0,
            },
        )

    monkeypatch.setattr(
        "ssscreen.stability.competing.collect_convex_hulls",
        fake_collect_convex_hulls,
    )
    result = runner.invoke(
        cli,
        [
            "stability",
            "convex-hull",
            "--relax-results",
            str(candidate),
            "--competing-manifest",
            str(manifest),
            "--competing-results",
            str(competing),
            "--structure-id",
            "sqs-1",
            "--screening-cutoff",
            "0.08",
            "--numerical-tolerance",
            "0.00001",
            "--output",
            str(tmp_path / "phase.csv"),
            "--entries-output",
            str(tmp_path / "entries.csv"),
            "--summary",
            str(tmp_path / "summary.json"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls[0]["structure_ids"] == ("sqs-1",)
    assert calls[0]["screening_cutoff"] == 0.08
    assert calls[0]["numerical_tolerance"] == 0.00001
    assert calls[0]["allow_incomplete"] is False
    assert "success=1" in result.output


def test_stability_phase_diagram_prompts_and_builds_mace_pipeline(monkeypatch, tmp_path):
    runner = CliRunner()
    candidate = tmp_path / "candidate.jsonl"
    candidate.write_text("{}\n")
    model = tmp_path / "mace.model"
    model.write_bytes(b"model")
    backend_calls = []
    pipeline_calls = []

    class FakeMaceBackend:
        def __init__(self, model_path, **kwargs):
            backend_calls.append((model_path, kwargs))

    def fake_run_phase_diagram_pipeline(**kwargs):
        pipeline_calls.append(kwargs)
        return (
            pd.DataFrame([{"status": "success"}]),
            pd.DataFrame(),
            {
                "success_count": 1,
                "uncertain_count": 0,
                "failed_count": 0,
            },
        )

    monkeypatch.setattr("ssscreen.stability.mlp.MaceRelaxationBackend", FakeMaceBackend)
    monkeypatch.setattr(
        "ssscreen.stability.competing.run_phase_diagram_pipeline",
        fake_run_phase_diagram_pipeline,
    )
    result = runner.invoke(
        cli,
        [
            "stability",
            "phase-diagram",
            "--relax-results",
            str(candidate),
            "--structure-id",
            "sqs-1",
            "--model-path",
            str(model),
            "--model-name",
            "fixture",
            "--device",
            "cuda:0",
            "--dtype",
            "float64",
            "--fmax",
            "0.02",
            "--max-steps",
            "300",
            "--output-dir",
            str(tmp_path / "phase-diagram"),
        ],
        input="testing-secret\n",
    )

    assert result.exit_code == 0, result.output
    assert "testing-secret" not in result.output
    assert backend_calls == [
        (model, {"device": "cuda:0", "dtype": "float64", "model_name": "fixture"})
    ]
    call = pipeline_calls[0]
    assert call["api_key"] == "testing-secret"
    assert call["mp_backend"] == "api"
    assert call["offline_db"] is None
    assert call["structure_ids"] == ("sqs-1",)
    assert call["fmax"] == 0.02
    assert call["max_steps"] == 300
    assert call["settings"].thermo_type == "GGA_GGA+U_R2SCAN"
    assert "success=1" in result.output


def test_stability_phase_diagram_uses_offline_database_without_prompt(monkeypatch, tmp_path):
    runner = CliRunner()
    candidate = tmp_path / "candidate.jsonl"
    candidate.write_text("{}\n")
    database = tmp_path / "default.db"
    database.write_bytes(b"sqlite")
    model = tmp_path / "mace.model"
    model.write_bytes(b"model")
    pipeline_calls = []

    class FakeMaceBackend:
        def __init__(self, _model_path, **_kwargs):
            pass

    def fake_run_phase_diagram_pipeline(**kwargs):
        pipeline_calls.append(kwargs)
        return (
            pd.DataFrame([{"status": "success"}]),
            pd.DataFrame(),
            {"success_count": 1, "uncertain_count": 0, "failed_count": 0},
        )

    monkeypatch.setattr("ssscreen.stability.mlp.MaceRelaxationBackend", FakeMaceBackend)
    monkeypatch.setattr(
        "ssscreen.stability.competing.run_phase_diagram_pipeline",
        fake_run_phase_diagram_pipeline,
    )
    result = runner.invoke(
        cli,
        [
            "stability",
            "phase-diagram",
            "--relax-results",
            str(candidate),
            "--mp-backend",
            "offline",
            "--offline-db",
            str(database),
            "--model-path",
            str(model),
            "--output-dir",
            str(tmp_path / "phase-diagram"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Materials Project API key" not in result.output
    assert pipeline_calls[0]["api_key"] is None
    assert pipeline_calls[0]["mp_backend"] == "offline"
    assert pipeline_calls[0]["offline_db"] == database


def test_recommend_command_invokes_stage11_aggregator(monkeypatch, tmp_path):
    runner = CliRunner()
    inputs = {}
    for name in ("pairs", "gaps", "mixing", "phonons", "phases"):
        path = tmp_path / f"{name}.csv"
        path.write_text("placeholder\n")
        inputs[name] = path
    output = tmp_path / "recommendations.csv"
    report = tmp_path / "recommendations.md"
    summary_path = tmp_path / "recommendations.json"
    calls = []

    def fake_generate_recommendations(**kwargs):
        calls.append(kwargs)
        return (
            pd.DataFrame([{"classification": "promising"}]),
            {
                "classification_counts": {
                    "promising": 1,
                    "uncertain": 0,
                    "low-priority": 0,
                }
            },
        )

    monkeypatch.setattr(
        "ssscreen.stability.recommendation.generate_recommendations",
        fake_generate_recommendations,
    )

    result = runner.invoke(
        cli,
        [
            "recommend",
            "--pairs",
            str(inputs["pairs"]),
            "--gap-results",
            str(inputs["gaps"]),
            "--mixing-enthalpy",
            str(inputs["mixing"]),
            "--phonons",
            str(inputs["phonons"]),
            "--phase-stability",
            str(inputs["phases"]),
            "--gap-method",
            "hse-v1",
            "--require-defects",
            "--promising-max-mixing",
            "20",
            "--low-priority-mixing",
            "60",
            "--promising-max-hull",
            "0.02",
            "--low-priority-hull",
            "0.12",
            "--gap-consistency-tolerance",
            "0.0001",
            "--output",
            str(output),
            "--report",
            str(report),
            "--summary",
            str(summary_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "promising=1" in result.output
    call = calls[0]
    assert call["pairs_path"] == inputs["pairs"]
    assert call["gap_results_path"] == inputs["gaps"]
    assert call["mixing_enthalpy_path"] == inputs["mixing"]
    assert call["phonons_path"] == inputs["phonons"]
    assert call["phase_stability_path"] == inputs["phases"]
    assert call["defects_path"] is None
    assert call["gap_method"] == "hse-v1"
    assert call["require_defects"] is True
    assert call["output_path"] == output
    assert call["report_path"] == report
    assert call["summary_path"] == summary_path
    settings = call["settings"]
    assert settings.promising_max_mixing_enthalpy_mev_per_atom == 20.0
    assert settings.low_priority_mixing_enthalpy_mev_per_atom == 60.0
    assert settings.promising_max_hull_ev_per_atom == 0.02
    assert settings.low_priority_hull_ev_per_atom == 0.12
    assert settings.gap_consistency_tolerance_ev == 0.0001
