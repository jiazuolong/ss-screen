"""Command-line interface: ``ss-screen``.

Subcommands mirroring the implemented pipeline stages:

  ``ss-screen valence-filter``  pre-filter metallic / mixed-valence structures
  ``ss-screen dataset mp``      build normalized MP dataset DataFrames
  ``ss-screen dataset structures`` normalize local POSCAR/CIF inputs
  ``ss-screen composition-screen`` pre-screen composition-template candidates
  ``ss-screen condense``        build robocrys condensed JSON inputs
  ``ss-screen structure-match`` match candidates by condensed structure archive
  ``ss-screen gap-export``      export candidates for external gap calculations
  ``ss-screen gap-compare``     compare final pairs across gap methods
  ``ss-screen stability``       generate optional stability-screening inputs
  ``ss-screen recommend``       rank candidates from Stage 5 and Stage 8--10 evidence
  ``ss-screen group``           group by composition template + environment
  ``ss-screen pair``            enumerate promising alloying pairs from gaps

Each command surfaces the notebook magic numbers as ``--options`` with sensible
defaults (the research values). All paths are CLI arguments — nothing is
hard-coded.
"""

from __future__ import annotations

import os
from pathlib import Path

import click
import pandas as pd

from .. import __version__
from ..config import (
    GAP_EXPORT_MAX_ATOMS,
    CompetingPhaseSettings,
    MLPRelaxationSettings,
    PhononSettings,
    RecommendationSettings,
    Thresholds,
    coerce_excluded,
)
from ..data.io import (
    CondenseLoader,
    dump_group_df,
    load_group_df,
    read_mbj_gaps,
    write_pairs_csv,
)
from ..pair.envmatch import find_unique_envs, group_similar_structures
from ..pair.filters import apply_element_exclusion, apply_size_gate, has_gap_diversity
from ..pair.grouping import (
    attach_band_gaps,
    candidate_structures,
    group_by_composition_template,
    screen_composition_batches,
)
from ..pair.pairing import enumerate_pairs, pairs_to_dataframe

VERSION_BANNER = r""" ____  ____        ____   ____ ____  _____ _____ _   _
/ ___|/ ___|      / ___| / ___|  _ \| ____| ____| \ | |
\___ \\___ \ _____\___ \| |   | |_) |  _| |  _| |  \| |
 ___) |__) |_____|___) | |___|  _ <| |___| |___| |\  |
|____/____/      |____/ \____|_| \_\_____|_____|_| \_|"""


def _show_version(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    if not value or ctx.resilient_parsing:
        return
    click.echo(VERSION_BANNER)
    click.echo()
    click.echo(f"SS-Screen version {__version__}")
    ctx.exit()


@click.group()
@click.option(
    "--version",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_show_version,
    help="Show the SS-Screen banner and version, then exit.",
)
def cli() -> None:
    """Screen materials pairs for solid-solution formation."""


def _parse_supercell(value: str) -> tuple[int, int, int]:
    parts = [part.strip() for part in value.replace("x", ",").split(",")]
    if len(parts) != 3:
        raise click.BadParameter("expected three integers, for example 2,2,2")
    try:
        supercell = tuple(int(part) for part in parts)
    except ValueError as exc:
        raise click.BadParameter("expected three integers, for example 2,2,2") from exc
    if any(dim <= 0 for dim in supercell):
        raise click.BadParameter("supercell dimensions must be positive")
    return supercell


def _parse_optional_supercell(
    _ctx: click.Context, _param: click.Parameter, value: str | None
) -> tuple[int, int, int] | None:
    return None if value is None else _parse_supercell(value)


def _prompt_mp_api_key() -> str:
    """Read an MP API key without echoing it or accepting a leaky CLI option."""
    key = os.environ.get("MP_API_KEY", "").strip()
    if key:
        return key
    return click.prompt("Materials Project API key", hide_input=True, type=str)


# ---------------------------------------------------------------------------
# dataset
# ---------------------------------------------------------------------------
@cli.group("dataset")
def dataset_cmd() -> None:
    """Build normalized source dataset DataFrames."""


@dataset_cmd.command("mp")
@click.option(
    "--backend",
    type=click.Choice(["offline", "api"]),
    default="offline",
    show_default=True,
    help="Materials Project source backend.",
)
@click.option(
    "--offline-db",
    "offline_db",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Optional mp_offline SQLite database path.",
)
@click.option(
    "--output",
    "output",
    type=click.Path(path_type=Path),
    required=True,
    help="Where to write the normalized MP pickle DataFrame.",
)
@click.option(
    "--provenance",
    "provenance_path",
    type=click.Path(path_type=Path),
    help="MP dataset provenance JSON (default: <output>.provenance.json).",
)
@click.option(
    "--max-e-hull",
    "max_e_hull",
    type=float,
    default=0.01,
    show_default=True,
    help="Maximum MP energy above hull to request (eV/atom).",
)
def dataset_mp_cmd(
    backend: str,
    offline_db: Path | None,
    output: Path,
    provenance_path: Path | None,
    max_e_hull: float,
) -> None:
    """Fetch Materials Project summaries into the screening schema."""
    from ..data.mp import load_mp_dataset

    try:
        df = load_mp_dataset(
            output=output,
            max_e_hull=max_e_hull,
            backend=backend,
            offline_db=offline_db,
            provenance_path=provenance_path,
        )
    except (ImportError, FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    from ..data.mp import default_mp_provenance_path

    sidecar = provenance_path or default_mp_provenance_path(output)
    click.echo(f"Wrote {len(df)} MP rows to {output}; provenance={sidecar}")


@dataset_cmd.command("wbm")
@click.option(
    "--xyz",
    "xyz_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="WBM extxyz file, e.g. wbm-dataset.xyz.",
)
@click.option(
    "--summary",
    "summary_path",
    type=click.Path(exists=True, path_type=Path),
    help="Optional WBM summary TSV/CSV file.",
)
@click.option(
    "--output",
    "output",
    type=click.Path(path_type=Path),
    required=True,
    help="Where to write the normalized WBM pickle DataFrame.",
)
def dataset_wbm_cmd(xyz_path: Path, summary_path: Path | None, output: Path) -> None:
    """Load WBM extxyz data into the screening schema."""
    from ..data.wbm import load_wbm_dataset

    try:
        df = load_wbm_dataset(xyz_path=xyz_path, output=output, summary_path=summary_path)
    except ImportError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Wrote {len(df)} WBM rows to {output}")


@dataset_cmd.command("structures")
@click.option(
    "--input-dir",
    "input_dirs",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    multiple=True,
    help="Directory to scan recursively for POSCAR/CIF/vasp/json structures.",
)
@click.option(
    "--input",
    "inputs",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    multiple=True,
    help="Single structure file to include; may be repeated.",
)
@click.option(
    "--metadata",
    "metadata_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Optional CSV/TSV with material_id, band_gap, e_hull, and source columns.",
)
@click.option(
    "--band-gap-default",
    type=float,
    default=0.0,
    show_default=True,
    help="Band gap assigned when metadata is absent.",
)
@click.option(
    "--e-hull-default",
    type=float,
    default=0.0,
    show_default=True,
    help="Energy above hull assigned when metadata is absent.",
)
@click.option(
    "--source",
    default="local-structures",
    show_default=True,
    help="Source label for rows without metadata source.",
)
@click.option(
    "--output",
    "output",
    type=click.Path(path_type=Path),
    required=True,
    help="Where to write the normalized local structure pickle DataFrame.",
)
@click.option(
    "--provenance",
    "provenance_path",
    type=click.Path(path_type=Path),
    help="Optional provenance JSON for the local structure import.",
)
def dataset_structures_cmd(
    input_dirs: tuple[Path, ...],
    inputs: tuple[Path, ...],
    metadata_path: Path | None,
    band_gap_default: float,
    e_hull_default: float,
    source: str,
    output: Path,
    provenance_path: Path | None,
) -> None:
    """Load local POSCAR/CIF structures into the screening schema."""
    from ..data.structures import load_structure_dataset

    try:
        df = load_structure_dataset(
            input_dirs=list(input_dirs),
            inputs=list(inputs),
            metadata_path=metadata_path,
            band_gap_default=band_gap_default,
            e_hull_default=e_hull_default,
            source=source,
            output=output,
            provenance_path=provenance_path,
        )
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Wrote {len(df)} local structure rows to {output}")


# ---------------------------------------------------------------------------
# valence-filter
# ---------------------------------------------------------------------------
@cli.command("valence-filter")
@click.option(
    "--df-mp",
    "df_mp",
    type=click.Path(exists=True, path_type=Path),
    help="Pickled MP dataset DataFrame (e.g. mp.df).",
)
@click.option(
    "--df-wbm",
    "df_wbm",
    type=click.Path(exists=True, path_type=Path),
    help="Pickled WBM dataset DataFrame (e.g. wbm-dataset.df).",
)
@click.option(
    "--output",
    "output",
    type=click.Path(path_type=Path),
    required=True,
    help="Where to write the JSON list of valid material IDs.",
)
@click.option("--no-verbose", is_flag=True, default=False, help="Disable the progress bar.")
def valence_filter_cmd(
    df_mp: Path | None, df_wbm: Path | None, output: Path, no_verbose: bool
) -> None:
    """Pre-filter metallic / mixed-valence structures via bond-valence analysis.

    Loads one or both pickled DataFrames (indexed by material ID, with a
    ``structure`` column of pymatgen Structures) and writes the IDs whose
    oxidation states BVAnalyzer can assign.
    """
    from monty.serialization import dumpfn

    from ..pair.filters import valence_filter

    frames = []
    if df_mp:
        frames.append(pd.read_pickle(df_mp))
    if df_wbm:
        frames.append(pd.read_pickle(df_wbm))
    if not frames:
        raise click.UsageError("Provide at least one of --df-mp / --df-wbm.")
    df = pd.concat(frames, axis=0)

    valid = valence_filter(df, verbose=not no_verbose)
    dumpfn(valid, str(output))
    click.echo(f"Wrote {len(valid)} valence-valid IDs to {output}")


# ---------------------------------------------------------------------------
# condense
# ---------------------------------------------------------------------------
@cli.command("condense")
@click.option(
    "--input",
    "inputs",
    multiple=True,
    type=click.Path(exists=True, path_type=Path),
    help="Structure file or directory to condense (repeatable).",
)
@click.option(
    "--df",
    "df_path",
    type=click.Path(exists=True, path_type=Path),
    help="Pickled normalized dataset DataFrame to condense.",
)
@click.option(
    "--structure-column",
    "structure_col",
    default="structure",
    show_default=True,
    help="DataFrame column containing pymatgen Structure objects.",
)
@click.option(
    "--material-id-column",
    "material_id_col",
    help="Optional DataFrame column for material IDs; default uses the DataFrame index.",
)
@click.option(
    "--output-dir",
    "output_dir",
    type=click.Path(path_type=Path),
    required=True,
    help="Directory for {material_id}.json condensed outputs.",
)
@click.option("--manifest", "manifest_path", type=click.Path(path_type=Path))
@click.option("--index", "index_path", type=click.Path(path_type=Path))
@click.option(
    "--stop-file",
    type=click.Path(path_type=Path),
    help="Stop after the current structure when this file appears; save completed records.",
)
@click.option("--limit", type=int, help="Limit number of DataFrame rows to condense.")
@click.option("--overwrite", is_flag=True, default=False, help="Overwrite existing outputs.")
@click.option(
    "--stop-on-error",
    is_flag=True,
    default=False,
    help="Stop on the first condensation error instead of recording failures.",
)
def condense_cmd(
    inputs: tuple[Path, ...],
    df_path: Path | None,
    structure_col: str,
    material_id_col: str | None,
    output_dir: Path,
    manifest_path: Path | None,
    index_path: Path | None,
    limit: int | None,
    overwrite: bool,
    stop_on_error: bool,
    stop_file: Path | None,
) -> None:
    """Build robocrys condensed-structure JSON files."""
    from ..data.condense import condense_dataframe, condense_paths

    if bool(inputs) == bool(df_path):
        raise click.UsageError("Provide exactly one of --input or --df.")
    control = {"stop_file": stop_file} if stop_file is not None else {}
    try:
        if df_path:
            summary = condense_dataframe(
                df_path=df_path,
                output_dir=output_dir,
                structure_col=structure_col,
                material_id_col=material_id_col,
                limit=limit,
                overwrite=overwrite,
                manifest_path=manifest_path,
                index_path=index_path,
                continue_on_error=not stop_on_error,
                **control,
            )
        else:
            summary = condense_paths(
                list(inputs),
                output_dir,
                overwrite=overwrite,
                manifest_path=manifest_path,
                index_path=index_path,
                continue_on_error=not stop_on_error,
                **control,
            )
    except ImportError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(
        "Condense summary: "
        f"written={summary.written} skipped={summary.skipped} failed={summary.failed} "
        f"stopped={summary.stopped} pending={summary.pending}"
    )
    if summary.stopped:
        click.echo("Stopped; completed descriptions and manifest/index have been preserved.")
        raise click.exceptions.Exit(130)


@cli.command("condense-index")
@click.option(
    "--condensed-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
)
@click.option("--output", type=click.Path(path_type=Path), required=True)
def condense_index_cmd(condensed_dir: Path, output: Path) -> None:
    """Build a CSV index for a condensed-structure JSON directory."""
    from ..data.condense import build_archive_index

    index = build_archive_index(condensed_dir, output)
    click.echo(f"Indexed {len(index)} condensed files to {output}")


@cli.command("condense-validate")
@click.option(
    "--condensed-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
)
@click.option("--output", type=click.Path(path_type=Path), required=True)
def condense_validate_cmd(condensed_dir: Path, output: Path) -> None:
    """Validate required robocrys keys in a condensed-structure archive."""
    from ..data.condense import validate_archive

    validation = validate_archive(condensed_dir, index_path=output)
    counts = validation["status"].value_counts().to_dict() if len(validation) else {}
    click.echo(
        f"Validation summary: valid={counts.get('valid', 0)} "
        f"invalid={counts.get('invalid', 0)} output={output}"
    )


# ---------------------------------------------------------------------------
# structure-match
# ---------------------------------------------------------------------------
@cli.command("structure-match")
@click.option(
    "--candidates",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Composition-candidate CSV from `ss-screen composition-screen`.",
)
@click.option(
    "--condensed-dir",
    "condensed_dirs",
    multiple=True,
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Condensed JSON archive directory (repeatable).",
)
@click.option("--min-x-elements", type=int, default=2, show_default=True)
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    required=True,
    help="Output structure-group JSON.",
)
@click.option(
    "--summary",
    type=click.Path(path_type=Path),
    help="Optional JSON structure-match summary.",
)
def structure_match_cmd(
    candidates: Path,
    condensed_dirs: tuple[Path, ...],
    min_x_elements: int,
    output: Path,
    summary: Path | None,
) -> None:
    """Match composition candidates by robocrys environment descriptors."""
    from monty.serialization import dumpfn

    from ..pair.structure_match import match_structure_candidates

    groups, report = match_structure_candidates(
        candidates,
        list(condensed_dirs),
        min_x_elements=min_x_elements,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    dump_group_df(groups, output)
    if summary:
        summary.parent.mkdir(parents=True, exist_ok=True)
        dumpfn(report, str(summary))
    click.echo(
        f"Wrote {len(groups)} structure groups to {output} "
        f"(missing_descriptions={report['missing_descriptions']})"
    )


# ---------------------------------------------------------------------------
# gap-export / gap-collect-vasp / gap-validate
# ---------------------------------------------------------------------------
@cli.command("gap-export")
@click.option(
    "--groups", "groups_path", type=click.Path(exists=True, path_type=Path), required=True
)
@click.option(
    "--dataset",
    "dataset_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Normalized dataset pickle containing source structures.",
)
@click.option("--method", default="external", show_default=True)
@click.option("--structure-dir", type=click.Path(path_type=Path))
@click.option(
    "--structure-format",
    "structure_formats",
    multiple=True,
    type=click.Choice(["json", "cif", "poscar"]),
    default=("json", "cif", "poscar"),
    show_default=True,
    help="Portable structure format(s) written under --structure-dir.",
)
@click.option("--results-template", type=click.Path(path_type=Path))
@click.option("--method-metadata-template", type=click.Path(path_type=Path))
@click.option("--structure-column", "structure_col", default="structure", show_default=True)
@click.option("--max-natoms", type=int, default=GAP_EXPORT_MAX_ATOMS, show_default=True)
@click.option(
    "--bundle",
    is_flag=True,
    help="Write one portable ZIP with all structures, tasks and templates.",
)
@click.option("--output", type=click.Path(path_type=Path), required=True)
def gap_export_cmd(
    groups_path: Path,
    dataset_path: Path,
    method: str,
    structure_dir: Path | None,
    structure_formats: tuple[str, ...],
    results_template: Path | None,
    method_metadata_template: Path | None,
    structure_col: str,
    max_natoms: int | None,
    bundle: bool,
    output: Path,
) -> None:
    """Export matched group members for external high-level gap calculations."""
    if bundle:
        from ..pair.gap_bundle import export_gap_bundle

        if any((structure_dir, results_template, method_metadata_template)) or method != "external":
            raise click.UsageError(
                "--bundle manages its own internal paths and pending method; use --output FILE.zip."
            )
        try:
            report = export_gap_bundle(
                groups_path,
                dataset_path,
                output,
                max_natoms=max_natoms,
                structure_col=structure_col,
            )
        except (OSError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(
            f"Wrote gap input ZIP: {output}; tasks={report['task_count']}, skipped={report['skipped_count']}"
        )
        return

    from ..pair.gap_export import export_gap_candidates

    exported = export_gap_candidates(
        groups_path=groups_path,
        dataset_path=dataset_path,
        output=output,
        method=method,
        structure_dir=structure_dir,
        structure_formats=structure_formats,
        results_template=results_template,
        method_metadata_template=method_metadata_template,
        structure_col=structure_col,
        max_natoms=max_natoms,
    )
    click.echo(f"Wrote {len(exported)} gap candidates to {output}")


@cli.command("gap-collect-vasp")
@click.option(
    "--tasks",
    "tasks_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Legacy explicit task table; the GUI uses its project's --task-source automatically.",
)
@click.option(
    "--task-source",
    "task_sources",
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Project export ZIP or registered task CSV used for result collection.",
)
@click.option(
    "--results-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory containing one task_id/vasprun.xml subdirectory per VASP task.",
)
@click.option("--historical-library", is_flag=True, help="Match CSV records to the current export by material and crystal structure.")
@click.option("--library-method", default="", help="Select a historical calculation method.")
@click.option(
    "--results-csv",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Prepared gap-result CSV; choose this or --results-dir.",
)
@click.option(
    "--method-metadata",
    "method_metadata_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Optional method metadata JSON used to populate settings_sha256.",
)
@click.option(
    "--task-id",
    "task_ids",
    multiple=True,
    help="Collect only this task ID; repeat to select multiple tasks.",
)
@click.option("--output", "output_path", type=click.Path(path_type=Path), required=True)
@click.option(
    "--report",
    "report_path",
    type=click.Path(path_type=Path),
    help="JSON report path; defaults beside OUTPUT.",
)
def gap_collect_vasp_cmd(
    historical_library: bool,
    library_method: str,
    tasks_path: Path | None,
    task_sources: tuple[Path, ...],
    results_dir: Path | None,
    results_csv: Path | None,
    method_metadata_path: Path | None,
    task_ids: tuple[str, ...],
    output_path: Path,
    report_path: Path | None,
) -> None:
    """Collect VASP XML files or import a prepared gap-result CSV."""
    from ..pair.gap_collect_vasp import collect_vasp_gap_results

    if (historical_library and results_csv is None) or (library_method and not historical_library):
        raise click.UsageError("Historical matching requires --historical-library and --results-csv.")
    if (results_dir is None) == (results_csv is None):
        raise click.UsageError("Choose exactly one of --results-dir or --results-csv.")
    if results_csv is not None:
        from ..pair.gap_collect_csv import collect_gap_csv

        if not task_sources or tasks_path or method_metadata_path or task_ids:
            raise click.UsageError(
                "--results-csv requires project --task-source without legacy task/method options."
            )
        try:
            results, report = collect_gap_csv(
                task_sources=task_sources,
                results_csv=results_csv,
                library_method=library_method if historical_library else None,
                output_path=output_path,
                report_path=report_path,
            )
        except (OSError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
    elif task_sources:
        from ..pair.gap_collect_folder import collect_vasp_gap_folder

        if tasks_path or method_metadata_path or task_ids:
            raise click.UsageError(
                "--task-source uses the complete project batch and XML settings; do not combine it with legacy task/method options."
            )
        try:
            results, report = collect_vasp_gap_folder(
                task_sources=task_sources,
                results_dir=results_dir,
                output_path=output_path,
                report_path=report_path,
            )
        except (OSError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
    else:
        if tasks_path is None:
            raise click.UsageError(
                "Provide --task-source for folder collection or legacy --tasks."
            )
        results, report = collect_vasp_gap_results(
            tasks_path=tasks_path,
            results_dir=results_dir,
            output_path=output_path,
            report_path=report_path,
            method_metadata_path=method_metadata_path,
            task_ids=task_ids,
        )
    statuses = ", ".join(
        f"{status}={count}" for status, count in report["status_counts"].items()
    )
    suffix = f" ({statuses})" if statuses else ""
    operation = "Imported CSV for" if results_csv is not None else "Scanned"
    task_label = "tasks" if results_csv is not None else "VASP tasks"
    click.echo(
        f"{operation} {report['selected_task_count']} {task_label} and wrote {len(results)} rows "
        f"to {output_path}; report={report_path or output_path.with_name(f'{output_path.stem}.collection-report.json')}"
        f"{suffix}"
    )


@cli.command("gap-validate")
@click.option("--gaps", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--tasks", "tasks_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--method-metadata",
    "method_metadata_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--output", "output_path", type=click.Path(path_type=Path))
@click.option("--rejected", "rejected_path", type=click.Path(path_type=Path))
@click.option("--report", "report_path", type=click.Path(path_type=Path))
def gap_validate_cmd(
    gaps: Path,
    tasks_path: Path | None,
    method_metadata_path: Path | None,
    output_path: Path | None,
    rejected_path: Path | None,
    report_path: Path | None,
) -> None:
    """Validate and normalize externally calculated band-gap results."""
    from ..pair.gap_export import validate_gap_results

    results = validate_gap_results(
        gaps,
        tasks_path=tasks_path,
        method_metadata_path=method_metadata_path,
        output_path=output_path,
        rejected_path=rejected_path,
        report_path=report_path,
    )
    report = results.attrs.get(
        "validation_report",
        {"accepted_count": len(results), "rejected_count": 0},
    )
    click.echo(
        "Gap-result validation: "
        f"accepted={report['accepted_count']} rejected={report['rejected_count']} source={gaps}"
    )
    if report["rejected_count"]:
        raise click.ClickException(
            f"gap validation rejected {report['rejected_count']} malformed row(s)"
        )


@cli.command("gap-compare")
@click.option(
    "--groups", "groups_path", type=click.Path(exists=True, path_type=Path), required=True
)
@click.option(
    "--gap-results",
    "gap_results",
    multiple=True,
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="External gap-result CSV using the stable schema from `gap-validate`.",
)
@click.option("--low-gap", "low_gap", type=float, default=0.15, show_default=True)
@click.option("--direct-min", "direct_min", type=float, default=0.15, show_default=True)
@click.option("--direct-max", "direct_max", type=float, default=1.5, show_default=True)
@click.option("--pair-any-below", "pair_any_below", type=float, default=0.3, show_default=True)
@click.option("--pair-any-above", "pair_any_above", type=float, default=0.2, show_default=True)
@click.option("--pair-both-below", "pair_both_below", type=float, default=0.8, show_default=True)
@click.option("--output-dir", type=click.Path(path_type=Path), required=True)
@click.option("--summary", type=click.Path(path_type=Path), required=True)
def gap_compare_cmd(
    groups_path: Path,
    gap_results: tuple[Path, ...],
    low_gap: float,
    direct_min: float,
    direct_max: float,
    pair_any_below: float,
    pair_any_above: float,
    pair_both_below: float,
    output_dir: Path,
    summary: Path,
) -> None:
    """Compare final pair outputs across external gap methods."""
    from ..config import PairThresholds
    from ..pair.gap_feedback import compare_gap_methods

    report = compare_gap_methods(
        groups_path=groups_path,
        gap_paths=gap_results,
        output_dir=output_dir,
        summary=summary,
        thresholds=PairThresholds(
            low_gap=low_gap,
            direct_min=direct_min,
            direct_max=direct_max,
            pair_any_below=pair_any_below,
            pair_any_above=pair_any_above,
            pair_both_below=pair_both_below,
        ),
    )
    click.echo(f"Compared {len(report['methods'])} methods to {summary} (outputs={output_dir})")


# ---------------------------------------------------------------------------
# stability
# ---------------------------------------------------------------------------
@cli.group("stability")
def stability_cmd() -> None:
    """Generate optional preliminary stability-screening inputs."""


@stability_cmd.command("match-library")
@click.option("--kind", type=click.Choice(["phonon","phase"]), required=True)
@click.option("--library", type=click.Path(exists=True,path_type=Path), required=True)
@click.option("--relaxation", type=click.Path(exists=True,path_type=Path), required=True)
@click.option("--pairs", type=click.Path(exists=True,path_type=Path), required=True)
@click.option("--database", type=click.Path(exists=True,path_type=Path))
@click.option("--output", type=click.Path(path_type=Path), required=True)
def stability_match_library(kind, library, relaxation, pairs, database, output):
    """Match a portable stability library to this project's relaxed alloys."""
    from ..stability.result_library import match_library
    try:
        rows, backup = match_library(kind,library,relaxation,pairs,output,database)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise click.ClickException(str(exc)) from exc
    matched = sum(row["library_match"]=="matched" for row in rows)
    usable = sum(row["status"]=="success" for row in rows)
    click.echo(f"本批 {len(rows)} 个合金，历史记录匹配 {matched}，成功 {usable}，未匹配或待核验 {len(rows)-matched}。输出 {output}")
    if backup:
        click.echo(f"已备份之前的结果：{backup}")


@stability_cmd.command("sqs-generate")
@click.option(
    "--pairs",
    "pairs_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Final pair CSV from `ss-screen pair`.",
)
@click.option(
    "--dataset",
    "dataset_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Normalized dataset pickle containing endpoint structures.",
)
@click.option(
    "--target-fraction",
    "target_fractions",
    multiple=True,
    type=click.FloatRange(0.0, 1.0),
    default=(0.5,),
    show_default=True,
    help="Target fraction of endpoint B on the substituted site.",
)
@click.option(
    "--supercell",
    callback=lambda _ctx, _param, value: _parse_supercell(value),
    default="2,2,2",
    show_default=True,
    help="Diagonal supercell as 'a,b,c' or 'axbxc'.",
)
@click.option(
    "--backend",
    type=click.Choice(["random", "icet"]),
    default="random",
    show_default=True,
    help="Alloy structure generator backend.",
)
@click.option(
    "--cutoff",
    "cutoffs",
    multiple=True,
    type=float,
    default=(4.0,),
    show_default=True,
    help="icet cluster-space cutoff in Angstrom; repeat for higher orders.",
)
@click.option(
    "--sqs-steps",
    type=int,
    help="Number of icet/mchammer Monte Carlo steps; icet chooses a default if omitted.",
)
@click.option("--seed", type=int, default=0, show_default=True)
@click.option("--output-dir", type=click.Path(path_type=Path), required=True)
@click.option("--manifest", "manifest_path", type=click.Path(path_type=Path), required=True)
def stability_sqs_generate_cmd(
    pairs_path: Path,
    dataset_path: Path,
    target_fractions: tuple[float, ...],
    supercell: tuple[int, int, int],
    backend: str,
    cutoffs: tuple[float, ...],
    sqs_steps: int | None,
    seed: int,
    output_dir: Path,
    manifest_path: Path,
) -> None:
    """Generate representative random-substitution alloy structures."""
    from ..stability.sqs import generate_sqs_inputs

    records = generate_sqs_inputs(
        pairs_path=pairs_path,
        dataset_path=dataset_path,
        output_dir=output_dir,
        manifest_path=manifest_path,
        target_fractions=target_fractions,
        supercell=supercell,
        seed=seed,
        backend=backend,
        cutoffs=cutoffs,
        sqs_steps=sqs_steps,
    )
    statuses = pd.Series([record["status"] for record in records]).value_counts().to_dict()
    click.echo(
        f"SQS input summary: written={statuses.get('written', 0)} "
        f"skipped={statuses.get('skipped', 0)} manifest={manifest_path}"
    )


@stability_cmd.command("relax")
@click.option(
    "--manifest",
    "manifest_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Stage 6 SQS JSONL manifest.",
)
@click.option(
    "--include-endmembers/--no-include-endmembers",
    default=False,
    show_default=True,
    help="Also relax de-duplicated endpoint A/B structures.",
)
@click.option(
    "--dataset",
    "dataset_path",
    type=click.Path(exists=True, path_type=Path),
    help="Dataset fallback for older manifests without endpoint structure paths.",
)
@click.option(
    "--backend",
    type=click.Choice(["mace"]),
    default="mace",
    show_default=True,
)
@click.option(
    "--model-path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Local MACE checkpoint path.",
)
@click.option("--model-name", help="Optional stable model label stored in provenance.")
@click.option("--device", default="cpu", show_default=True, help="MACE device, e.g. cpu or cuda:0.")
@click.option(
    "--dtype",
    type=click.Choice(["float32", "float64"]),
    default="float32",
    show_default=True,
)
@click.option(
    "--fmax",
    type=click.FloatRange(min=0.0, min_open=True),
    default=MLPRelaxationSettings.force_tolerance,
    show_default=True,
    help="Force convergence tolerance in eV/Angstrom.",
)
@click.option(
    "--max-steps",
    type=click.IntRange(min=1),
    default=MLPRelaxationSettings.max_steps,
    show_default=True,
)
@click.option(
    "--relax-cell/--positions-only",
    default=True,
    show_default=True,
    help="Relax positions and periodic cell, or positions only.",
)
@click.option("--limit", type=click.IntRange(min=1), help="Process at most this many tasks.")
@click.option("--overwrite", is_flag=True, help="Replace results even when fingerprints differ.")
@click.option("--retry-failed", is_flag=True, help="Retry matching failed task records.")
@click.option("--output-dir", type=click.Path(path_type=Path), required=True)
@click.option("--results", "results_path", type=click.Path(path_type=Path), required=True)
def stability_relax_cmd(
    manifest_path: Path,
    include_endmembers: bool,
    dataset_path: Path | None,
    backend: str,
    model_path: Path,
    model_name: str | None,
    device: str,
    dtype: str,
    fmax: float,
    max_steps: int,
    relax_cell: bool,
    limit: int | None,
    overwrite: bool,
    retry_failed: bool,
    output_dir: Path,
    results_path: Path,
) -> None:
    """Relax SQS and optional endpoint structures with a configured MLP."""
    from ..stability.mlp import MaceRelaxationBackend
    from ..stability.relax import relax_manifest

    if backend != "mace":  # The Click choice keeps this explicit for future backends.
        raise click.ClickException(f"unsupported MLP backend: {backend}")
    calculator = MaceRelaxationBackend(
        model_path,
        device=device,
        dtype=dtype,
        model_name=model_name,
    )
    records = relax_manifest(
        manifest_path=manifest_path,
        output_dir=output_dir,
        results_path=results_path,
        backend=calculator,
        include_endmembers=include_endmembers,
        dataset_path=dataset_path,
        fmax=fmax,
        max_steps=max_steps,
        relax_cell=relax_cell,
        overwrite=overwrite,
        retry_failed=retry_failed,
        limit=limit,
    )
    statuses = pd.Series([record["status"] for record in records]).value_counts().to_dict()
    click.echo(
        "MLP relaxation summary: "
        f"success={statuses.get('success', 0)} "
        f"not_converged={statuses.get('not_converged', 0)} "
        f"failed={statuses.get('failed', 0)} results={results_path}"
    )


@stability_cmd.command("mixing-enthalpy")
@click.option(
    "--pairs",
    "pairs_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Final pair CSV used to generate the Stage 6 SQS manifest.",
)
@click.option(
    "--relax-results",
    "relax_results_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Stage 7 relaxation-results JSONL containing SQS and endmembers.",
)
@click.option("--output", "output_path", type=click.Path(path_type=Path), required=True)
@click.option("--summary", "summary_path", type=click.Path(path_type=Path), required=True)
def stability_mixing_enthalpy_cmd(
    pairs_path: Path,
    relax_results_path: Path,
    output_path: Path,
    summary_path: Path,
) -> None:
    """Calculate preliminary per-composition mixing enthalpies."""
    from ..stability.thermodynamics import calculate_mixing_enthalpies

    _frame, summary = calculate_mixing_enthalpies(
        pairs_path=pairs_path,
        relax_results_path=relax_results_path,
        output_path=output_path,
        summary_path=summary_path,
    )
    click.echo(
        "Mixing enthalpy summary: "
        f"success={summary['success_count']} "
        f"failed={summary['failed_count']} output={output_path} summary={summary_path}"
    )


@stability_cmd.command("phonon-export")
@click.option(
    "--relax-results",
    "relax_results_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Stage 7 relaxation-results JSONL.",
)
@click.option(
    "--structure-id",
    "structure_ids",
    multiple=True,
    help="Process only this structure ID; repeat to select more than one.",
)
@click.option("--include-endmembers/--sqs-only", default=False, show_default=True)
@click.option(
    "--supercell",
    callback=_parse_optional_supercell,
    help="Optional diagonal supercell as 'a,b,c'; otherwise choose from cell lengths.",
)
@click.option(
    "--min-supercell-length",
    type=click.FloatRange(min=0.0, min_open=True),
    default=PhononSettings.min_supercell_length,
    show_default=True,
    help="Automatic supercells target this lattice-vector length in Angstrom.",
)
@click.option(
    "--max-supercell-atoms",
    type=click.IntRange(min=1),
    default=PhononSettings.max_supercell_atoms,
    show_default=True,
)
@click.option(
    "--displacement",
    "displacement_distance",
    type=click.FloatRange(min=0.0, min_open=True),
    default=PhononSettings.displacement_distance,
    show_default=True,
    help="Finite-displacement amplitude in Angstrom.",
)
@click.option(
    "--symprec",
    "symmetry_tolerance",
    type=click.FloatRange(min=0.0, min_open=True),
    default=PhononSettings.symmetry_tolerance,
    show_default=True,
)
@click.option(
    "--max-input-force",
    type=click.FloatRange(min=0.0, min_open=True),
    default=PhononSettings.max_input_force,
    show_default=True,
    help="Maximum accepted Stage 7 residual force in eV/Angstrom.",
)
@click.option(
    "--allow-loose-input",
    is_flag=True,
    help="Generate tasks even when the Stage 7 residual force exceeds the limit.",
)
@click.option("--output-dir", type=click.Path(path_type=Path), required=True)
@click.option("--manifest", "manifest_path", type=click.Path(path_type=Path), required=True)
def stability_phonon_export_cmd(
    relax_results_path: Path,
    structure_ids: tuple[str, ...],
    include_endmembers: bool,
    supercell: tuple[int, int, int] | None,
    min_supercell_length: float,
    max_supercell_atoms: int,
    displacement_distance: float,
    symmetry_tolerance: float,
    max_input_force: float,
    allow_loose_input: bool,
    output_dir: Path,
    manifest_path: Path,
) -> None:
    """Generate Phonopy reference and displaced-supercell tasks."""
    from ..stability.phonon import export_phonon_tasks

    records = export_phonon_tasks(
        relax_results_path=relax_results_path,
        output_dir=output_dir,
        manifest_path=manifest_path,
        structure_ids=structure_ids,
        include_endmembers=include_endmembers,
        supercell=supercell,
        displacement_distance=displacement_distance,
        symmetry_tolerance=symmetry_tolerance,
        min_supercell_length=min_supercell_length,
        max_supercell_atoms=max_supercell_atoms,
        max_input_force=max_input_force,
        allow_loose_input=allow_loose_input,
    )
    written = sum(record.get("status") == "written" for record in records)
    skipped = sum(record.get("status") == "skipped" for record in records)
    structures = len({record.get("phonon_id") for record in records})
    click.echo(
        f"Phonon export summary: structures={structures} tasks={written} "
        f"skipped={skipped} manifest={manifest_path}"
    )


@stability_cmd.command("phonon-forces")
@click.option(
    "--manifest",
    "manifest_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option("--backend", type=click.Choice(["mace"]), default="mace", show_default=True)
@click.option(
    "--model-path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option("--model-name", help="Optional stable model label stored in provenance.")
@click.option("--device", default="cpu", show_default=True)
@click.option(
    "--dtype",
    type=click.Choice(["float32", "float64"]),
    default="float64",
    show_default=True,
)
@click.option("--limit", type=click.IntRange(min=1), help="Evaluate at most this many tasks.")
@click.option("--overwrite", is_flag=True)
@click.option("--retry-failed", is_flag=True)
@click.option("--output-dir", type=click.Path(path_type=Path), required=True)
@click.option("--results", "results_path", type=click.Path(path_type=Path), required=True)
def stability_phonon_forces_cmd(
    manifest_path: Path,
    backend: str,
    model_path: Path,
    model_name: str | None,
    device: str,
    dtype: str,
    limit: int | None,
    overwrite: bool,
    retry_failed: bool,
    output_dir: Path,
    results_path: Path,
) -> None:
    """Evaluate Phonopy task energies, forces, and stresses with MACE."""
    from ..stability.mlp import MaceRelaxationBackend
    from ..stability.phonon import evaluate_phonon_forces

    if backend != "mace":
        raise click.ClickException(f"unsupported phonon force backend: {backend}")
    calculator = MaceRelaxationBackend(
        model_path,
        device=device,
        dtype=dtype,
        model_name=model_name,
    )
    records = evaluate_phonon_forces(
        manifest_path=manifest_path,
        output_dir=output_dir,
        results_path=results_path,
        backend=calculator,
        overwrite=overwrite,
        retry_failed=retry_failed,
        limit=limit,
    )
    statuses = pd.Series([record["status"] for record in records]).value_counts().to_dict()
    click.echo(
        "Phonon MACE force summary: "
        f"success={statuses.get('success', 0)} failed={statuses.get('failed', 0)} "
        f"results={results_path}"
    )


@stability_cmd.command("phonon-collect")
@click.option(
    "--manifest",
    "manifest_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--force-results",
    "force_results_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--mesh",
    callback=lambda _ctx, _param, value: _parse_supercell(value),
    default=",".join(map(str, PhononSettings.mesh)),
    show_default=True,
    help="Gamma-centered q mesh as 'a,b,c'.",
)
@click.option(
    "--band-points",
    type=click.IntRange(min=2),
    default=PhononSettings.band_points,
    show_default=True,
)
@click.option(
    "--imaginary-tolerance",
    type=click.FloatRange(min=0.0),
    default=PhononSettings.imaginary_tolerance_thz,
    show_default=True,
    help="Magnitude threshold for significant imaginary frequencies in THz.",
)
@click.option("--subtract-reference-forces/--raw-forces", default=True, show_default=True)
@click.option("--symmetrize-fc/--raw-force-constants", default=True, show_default=True)
@click.option("--output-dir", type=click.Path(path_type=Path), required=True)
@click.option("--summary", "summary_path", type=click.Path(path_type=Path), required=True)
@click.option("--report", "report_path", type=click.Path(path_type=Path), required=True)
def stability_phonon_collect_cmd(
    manifest_path: Path,
    force_results_path: Path,
    mesh: tuple[int, int, int],
    band_points: int,
    imaginary_tolerance: float,
    subtract_reference_forces: bool,
    symmetrize_fc: bool,
    output_dir: Path,
    summary_path: Path,
    report_path: Path,
) -> None:
    """Build force constants, phonon bands, DOS, and stability summaries."""
    from ..stability.phonon import collect_phonon_results

    frame, report = collect_phonon_results(
        manifest_path=manifest_path,
        force_results_path=force_results_path,
        output_dir=output_dir,
        summary_path=summary_path,
        report_path=report_path,
        mesh=mesh,
        band_points=band_points,
        imaginary_tolerance=imaginary_tolerance,
        subtract_reference_forces=subtract_reference_forces,
        symmetrize_force_constants=symmetrize_fc,
    )
    counts = report["dynamical_status_counts"]
    click.echo(
        "Phonon collection summary: "
        f"structures={len(frame)} stable={counts.get('stable', 0)} "
        f"unstable={counts.get('unstable', 0)} uncertain={counts.get('uncertain', 0)} "
        f"failed={counts.get('failed', 0)} summary={summary_path}"
    )


@stability_cmd.command("phonon-run")
@click.option(
    "--relax-results",
    "relax_results_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option("--structure-id", "structure_ids", multiple=True)
@click.option("--include-endmembers/--sqs-only", default=False, show_default=True)
@click.option("--supercell", callback=_parse_optional_supercell)
@click.option(
    "--min-supercell-length",
    type=click.FloatRange(min=0.0, min_open=True),
    default=PhononSettings.min_supercell_length,
    show_default=True,
)
@click.option(
    "--max-supercell-atoms",
    type=click.IntRange(min=1),
    default=PhononSettings.max_supercell_atoms,
    show_default=True,
)
@click.option(
    "--displacement",
    type=click.FloatRange(min=0.0, min_open=True),
    default=PhononSettings.displacement_distance,
    show_default=True,
)
@click.option(
    "--symprec",
    type=click.FloatRange(min=0.0, min_open=True),
    default=PhononSettings.symmetry_tolerance,
    show_default=True,
)
@click.option(
    "--max-input-force",
    type=click.FloatRange(min=0.0, min_open=True),
    default=PhononSettings.max_input_force,
    show_default=True,
)
@click.option("--allow-loose-input", is_flag=True)
@click.option(
    "--mesh",
    callback=lambda _ctx, _param, value: _parse_supercell(value),
    default=",".join(map(str, PhononSettings.mesh)),
    show_default=True,
)
@click.option(
    "--band-points",
    type=click.IntRange(min=2),
    default=PhononSettings.band_points,
    show_default=True,
)
@click.option(
    "--imaginary-tolerance",
    type=click.FloatRange(min=0.0),
    default=PhononSettings.imaginary_tolerance_thz,
    show_default=True,
)
@click.option(
    "--model-path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option("--model-name")
@click.option("--device", default="cpu", show_default=True)
@click.option(
    "--dtype",
    type=click.Choice(["float32", "float64"]),
    default="float64",
    show_default=True,
)
@click.option("--overwrite", is_flag=True)
@click.option("--retry-failed", is_flag=True)
@click.option("--output-dir", type=click.Path(path_type=Path), required=True)
def stability_phonon_run_cmd(
    relax_results_path: Path,
    structure_ids: tuple[str, ...],
    include_endmembers: bool,
    supercell: tuple[int, int, int] | None,
    min_supercell_length: float,
    max_supercell_atoms: int,
    displacement: float,
    symprec: float,
    max_input_force: float,
    allow_loose_input: bool,
    mesh: tuple[int, int, int],
    band_points: int,
    imaginary_tolerance: float,
    model_path: Path,
    model_name: str | None,
    device: str,
    dtype: str,
    overwrite: bool,
    retry_failed: bool,
    output_dir: Path,
) -> None:
    """Run harmonic finite-displacement phonons end to end with MACE forces."""
    from ..stability.mlp import MaceRelaxationBackend
    from ..stability.phonon import run_phonon_pipeline

    calculator = MaceRelaxationBackend(
        model_path,
        device=device,
        dtype=dtype,
        model_name=model_name,
    )
    settings = PhononSettings(
        displacement_distance=displacement,
        symmetry_tolerance=symprec,
        min_supercell_length=min_supercell_length,
        max_supercell_atoms=max_supercell_atoms,
        mesh=mesh,
        band_points=band_points,
        imaginary_tolerance_thz=imaginary_tolerance,
        max_input_force=max_input_force,
    )
    frame, report = run_phonon_pipeline(
        relax_results_path=relax_results_path,
        output_dir=output_dir,
        backend=calculator,
        settings=settings,
        structure_ids=structure_ids,
        include_endmembers=include_endmembers,
        supercell=supercell,
        allow_loose_input=allow_loose_input,
        overwrite=overwrite,
        retry_failed=retry_failed,
    )
    counts = report["dynamical_status_counts"]
    click.echo(
        "MACE phonon summary: "
        f"structures={len(frame)} stable={counts.get('stable', 0)} "
        f"unstable={counts.get('unstable', 0)} uncertain={counts.get('uncertain', 0)} "
        f"failed={counts.get('failed', 0)} output={output_dir}"
    )


@stability_cmd.command("competing-export")
@click.option(
    "--relax-results",
    "relax_results_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Stage 7 relaxation-results JSONL containing SQS candidates.",
)
@click.option("--structure-id", "structure_ids", multiple=True)
@click.option(
    "--mp-backend",
    type=click.Choice(["api", "offline"]),
    default="api",
    show_default=True,
    help="Materials Project source used only to discover competing structures.",
)
@click.option(
    "--offline-db",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Explicit mp_offline SQLite snapshot; required for the offline backend.",
)
@click.option(
    "--mp-max-e-hull",
    type=click.FloatRange(min=0.0),
    default=CompetingPhaseSettings.max_mp_energy_above_hull,
    show_default=True,
    help="Maximum MP hull distance used to select competing structures (eV/atom).",
)
@click.option(
    "--thermo-type",
    type=click.Choice(["GGA_GGA+U", "GGA_GGA+U_R2SCAN", "R2SCAN"]),
    default=CompetingPhaseSettings.thermo_type,
    show_default=True,
    help="MP thermo filter for the API backend; not available in offline summaries.",
)
@click.option(
    "--max-phase-atoms",
    type=click.IntRange(min=1),
    default=CompetingPhaseSettings.max_competing_phase_atoms,
    show_default=True,
    help="Maximum atom count after primitive-cell reduction.",
)
@click.option(
    "--api-timeout",
    type=click.FloatRange(min=0.0, min_open=True),
    default=CompetingPhaseSettings.api_timeout_seconds,
    show_default=True,
    help="Per-request and per-system Materials Project timeout in seconds.",
)
@click.option("--output-dir", type=click.Path(path_type=Path), required=True)
@click.option("--manifest", "manifest_path", type=click.Path(path_type=Path), required=True)
@click.option("--report", "report_path", type=click.Path(path_type=Path), required=True)
def stability_competing_export_cmd(
    relax_results_path: Path,
    structure_ids: tuple[str, ...],
    mp_backend: str,
    offline_db: Path | None,
    mp_max_e_hull: float,
    thermo_type: str,
    max_phase_atoms: int,
    api_timeout: float,
    output_dir: Path,
    manifest_path: Path,
    report_path: Path,
) -> None:
    """Export competing structures from MP API or an offline snapshot."""
    from ..stability.competing import export_competing_phases

    if mp_backend == "offline" and offline_db is None:
        raise click.UsageError("--offline-db is required when --mp-backend=offline")
    api_key = _prompt_mp_api_key() if mp_backend == "api" else None
    records, report = export_competing_phases(
        relax_results_path=relax_results_path,
        output_dir=output_dir,
        manifest_path=manifest_path,
        report_path=report_path,
        api_key=api_key,
        mp_backend=mp_backend,
        offline_db=offline_db,
        structure_ids=structure_ids,
        settings=CompetingPhaseSettings(
            thermo_type=thermo_type,
            max_mp_energy_above_hull=mp_max_e_hull,
            max_competing_phase_atoms=max_phase_atoms,
            api_timeout_seconds=api_timeout,
        ),
    )
    counts = report["status_counts"]
    click.echo(
        f"MP competing-phase export ({mp_backend}): "
        f"systems={len(report['chemical_systems'])} fetched={report['fetched_entry_count']} "
        f"written={counts.get('written', 0)} skipped={counts.get('skipped', 0)} "
        f"query_failed={report['query_failure_count']} manifest={manifest_path}"
    )


@stability_cmd.command("competing-relax")
@click.option(
    "--manifest",
    "manifest_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--model-path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option("--model-name")
@click.option("--device", default="cpu", show_default=True)
@click.option(
    "--dtype",
    type=click.Choice(["float32", "float64"]),
    default="float32",
    show_default=True,
)
@click.option(
    "--fmax",
    type=click.FloatRange(min=0.0, min_open=True),
    default=MLPRelaxationSettings.force_tolerance,
    show_default=True,
)
@click.option(
    "--max-steps",
    type=click.IntRange(min=1),
    default=MLPRelaxationSettings.max_steps,
    show_default=True,
)
@click.option("--relax-cell/--positions-only", default=True, show_default=True)
@click.option("--limit", type=click.IntRange(min=1))
@click.option("--overwrite", is_flag=True)
@click.option("--retry-failed", is_flag=True)
@click.option("--output-dir", type=click.Path(path_type=Path), required=True)
@click.option("--results", "results_path", type=click.Path(path_type=Path), required=True)
def stability_competing_relax_cmd(
    manifest_path: Path,
    model_path: Path,
    model_name: str | None,
    device: str,
    dtype: str,
    fmax: float,
    max_steps: int,
    relax_cell: bool,
    limit: int | None,
    overwrite: bool,
    retry_failed: bool,
    output_dir: Path,
    results_path: Path,
) -> None:
    """Relax MP competing structures with MACE and the Stage 7 contract."""
    from ..stability.competing import relax_competing_phases
    from ..stability.mlp import MaceRelaxationBackend

    calculator = MaceRelaxationBackend(
        model_path,
        device=device,
        dtype=dtype,
        model_name=model_name,
    )
    records = relax_competing_phases(
        manifest_path=manifest_path,
        output_dir=output_dir,
        results_path=results_path,
        backend=calculator,
        fmax=fmax,
        max_steps=max_steps,
        relax_cell=relax_cell,
        overwrite=overwrite,
        retry_failed=retry_failed,
        limit=limit,
    )
    counts = pd.Series([record["status"] for record in records]).value_counts().to_dict()
    click.echo(
        "Competing-phase MACE relaxation: "
        f"success={counts.get('success', 0)} "
        f"not_converged={counts.get('not_converged', 0)} "
        f"failed={counts.get('failed', 0)} results={results_path}"
    )


@stability_cmd.command("convex-hull")
@click.option(
    "--relax-results",
    "candidate_relax_results_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--competing-manifest",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--competing-results",
    "competing_relax_results_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option("--structure-id", "structure_ids", multiple=True)
@click.option(
    "--screening-cutoff",
    type=click.FloatRange(min=0.0),
    default=CompetingPhaseSettings.screening_cutoff_ev_per_atom,
    show_default=True,
    help="Maximum e_above_hull retained for screening (eV/atom).",
)
@click.option(
    "--numerical-tolerance",
    type=click.FloatRange(min=0.0),
    default=CompetingPhaseSettings.numerical_tolerance_ev_per_atom,
    show_default=True,
)
@click.option(
    "--allow-incomplete",
    is_flag=True,
    help="Calculate an explicitly uncertain hull despite missing competing phases.",
)
@click.option("--output", "output_path", type=click.Path(path_type=Path), required=True)
@click.option(
    "--entries-output",
    "entries_output_path",
    type=click.Path(path_type=Path),
    required=True,
)
@click.option("--summary", "summary_path", type=click.Path(path_type=Path), required=True)
def stability_convex_hull_cmd(
    candidate_relax_results_path: Path,
    competing_manifest: Path,
    competing_relax_results_path: Path,
    structure_ids: tuple[str, ...],
    screening_cutoff: float,
    numerical_tolerance: float,
    allow_incomplete: bool,
    output_path: Path,
    entries_output_path: Path,
    summary_path: Path,
) -> None:
    """Build strict same-MLIP convex hulls for relaxed SQS candidates."""
    from ..stability.competing import collect_convex_hulls

    frame, _entries, summary = collect_convex_hulls(
        candidate_relax_results_path=candidate_relax_results_path,
        competing_manifest_path=competing_manifest,
        competing_relax_results_path=competing_relax_results_path,
        output_path=output_path,
        entries_output_path=entries_output_path,
        summary_path=summary_path,
        structure_ids=structure_ids,
        screening_cutoff=screening_cutoff,
        numerical_tolerance=numerical_tolerance,
        allow_incomplete=allow_incomplete,
    )
    click.echo(
        "MLIP convex-hull summary: "
        f"candidates={len(frame)} success={summary['success_count']} "
        f"uncertain={summary['uncertain_count']} failed={summary['failed_count']} "
        f"output={output_path}"
    )


@stability_cmd.command("phase-diagram")
@click.option(
    "--relax-results",
    "candidate_relax_results_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option("--structure-id", "structure_ids", multiple=True)
@click.option(
    "--mp-backend",
    type=click.Choice(["api", "offline"]),
    default="api",
    show_default=True,
    help="Materials Project source used only to discover competing structures.",
)
@click.option(
    "--offline-db",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Explicit mp_offline SQLite snapshot; required for the offline backend.",
)
@click.option(
    "--mp-max-e-hull",
    type=click.FloatRange(min=0.0),
    default=CompetingPhaseSettings.max_mp_energy_above_hull,
    show_default=True,
)
@click.option(
    "--thermo-type",
    type=click.Choice(["GGA_GGA+U", "GGA_GGA+U_R2SCAN", "R2SCAN"]),
    default=CompetingPhaseSettings.thermo_type,
    show_default=True,
    help="MP thermo filter for the API backend; not available in offline summaries.",
)
@click.option(
    "--max-phase-atoms",
    type=click.IntRange(min=1),
    default=CompetingPhaseSettings.max_competing_phase_atoms,
    show_default=True,
)
@click.option(
    "--api-timeout",
    type=click.FloatRange(min=0.0, min_open=True),
    default=CompetingPhaseSettings.api_timeout_seconds,
    show_default=True,
)
@click.option(
    "--model-path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
)
@click.option("--model-name")
@click.option("--device", default="cpu", show_default=True)
@click.option(
    "--dtype",
    type=click.Choice(["float32", "float64"]),
    default="float32",
    show_default=True,
)
@click.option(
    "--fmax",
    type=click.FloatRange(min=0.0, min_open=True),
    default=MLPRelaxationSettings.force_tolerance,
    show_default=True,
)
@click.option(
    "--max-steps",
    type=click.IntRange(min=1),
    default=MLPRelaxationSettings.max_steps,
    show_default=True,
)
@click.option("--relax-cell/--positions-only", default=True, show_default=True)
@click.option(
    "--screening-cutoff",
    type=click.FloatRange(min=0.0),
    default=CompetingPhaseSettings.screening_cutoff_ev_per_atom,
    show_default=True,
)
@click.option(
    "--numerical-tolerance",
    type=click.FloatRange(min=0.0),
    default=CompetingPhaseSettings.numerical_tolerance_ev_per_atom,
    show_default=True,
)
@click.option("--allow-incomplete", is_flag=True)
@click.option("--overwrite", is_flag=True)
@click.option("--retry-failed", is_flag=True)
@click.option("--output-dir", type=click.Path(path_type=Path), required=True)
def stability_phase_diagram_cmd(
    candidate_relax_results_path: Path,
    structure_ids: tuple[str, ...],
    mp_backend: str,
    offline_db: Path | None,
    mp_max_e_hull: float,
    thermo_type: str,
    max_phase_atoms: int,
    api_timeout: float,
    model_path: Path,
    model_name: str | None,
    device: str,
    dtype: str,
    fmax: float,
    max_steps: int,
    relax_cell: bool,
    screening_cutoff: float,
    numerical_tolerance: float,
    allow_incomplete: bool,
    overwrite: bool,
    retry_failed: bool,
    output_dir: Path,
) -> None:
    """Discover, relax, and compare MP phases from API or offline data."""
    from ..stability.competing import run_phase_diagram_pipeline
    from ..stability.mlp import MaceRelaxationBackend

    if mp_backend == "offline" and offline_db is None:
        raise click.UsageError("--offline-db is required when --mp-backend=offline")
    api_key = _prompt_mp_api_key() if mp_backend == "api" else None
    calculator = MaceRelaxationBackend(
        model_path,
        device=device,
        dtype=dtype,
        model_name=model_name,
    )
    settings = CompetingPhaseSettings(
        thermo_type=thermo_type,
        max_mp_energy_above_hull=mp_max_e_hull,
        max_competing_phase_atoms=max_phase_atoms,
        api_timeout_seconds=api_timeout,
        screening_cutoff_ev_per_atom=screening_cutoff,
        numerical_tolerance_ev_per_atom=numerical_tolerance,
    )
    frame, _entries, summary = run_phase_diagram_pipeline(
        candidate_relax_results_path=candidate_relax_results_path,
        output_dir=output_dir,
        api_key=api_key,
        mp_backend=mp_backend,
        offline_db=offline_db,
        backend=calculator,
        settings=settings,
        structure_ids=structure_ids,
        fmax=fmax,
        max_steps=max_steps,
        relax_cell=relax_cell,
        allow_incomplete=allow_incomplete,
        overwrite=overwrite,
        retry_failed=retry_failed,
    )
    click.echo(
        "Stage 10 phase-diagram summary: "
        f"candidates={len(frame)} success={summary['success_count']} "
        f"uncertain={summary['uncertain_count']} failed={summary['failed_count']} "
        f"output={output_dir}"
    )


# ---------------------------------------------------------------------------
# Stage 11 recommendation
# ---------------------------------------------------------------------------
@cli.command("recommend")
@click.option(
    "--pairs",
    "pairs_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Stage 5 final-pairs CSV.",
)
@click.option(
    "--gap-results",
    "gap_results_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Normalized external high-fidelity gap results.",
)
@click.option(
    "--mixing-enthalpy",
    "mixing_enthalpy_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Stage 8 mixing-enthalpy CSV.",
)
@click.option(
    "--phonons",
    "phonons_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Stage 9 phonon-summary CSV.",
)
@click.option(
    "--phase-stability",
    "phase_stability_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Stage 10 phase-stability CSV.",
)
@click.option(
    "--defects",
    "defects_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Optional defect evidence with pair_index, status, and defect_signal.",
)
@click.option(
    "--gap-method",
    help="Gap method override for legacy pair tables without a gap_method column.",
)
@click.option(
    "--require-defects",
    is_flag=True,
    help="Downgrade missing defect evidence to uncertain.",
)
@click.option(
    "--promising-max-mixing",
    type=click.FloatRange(min=0.0),
    default=RecommendationSettings.promising_max_mixing_enthalpy_mev_per_atom,
    show_default=True,
    help="Maximum promising mixing enthalpy in meV/atom.",
)
@click.option(
    "--low-priority-mixing",
    type=click.FloatRange(min=0.0),
    default=RecommendationSettings.low_priority_mixing_enthalpy_mev_per_atom,
    show_default=True,
    help="Mixing enthalpy above which a candidate is low priority (meV/atom).",
)
@click.option(
    "--promising-max-hull",
    type=click.FloatRange(min=0.0),
    default=RecommendationSettings.promising_max_hull_ev_per_atom,
    show_default=True,
    help="Maximum promising same-MLIP hull distance in eV/atom.",
)
@click.option(
    "--low-priority-hull",
    type=click.FloatRange(min=0.0),
    default=RecommendationSettings.low_priority_hull_ev_per_atom,
    show_default=True,
    help="Hull distance above which a candidate is low priority (eV/atom).",
)
@click.option(
    "--gap-consistency-tolerance",
    type=click.FloatRange(min=0.0),
    default=RecommendationSettings.gap_consistency_tolerance_ev,
    show_default=True,
    help="Allowed endpoint-gap difference between pair and gap-result tables (eV).",
)
@click.option("--output", "output_path", type=click.Path(path_type=Path), required=True)
@click.option("--report", "report_path", type=click.Path(path_type=Path), required=True)
@click.option("--summary", "summary_path", type=click.Path(path_type=Path))
def recommend_cmd(
    pairs_path: Path,
    gap_results_path: Path,
    mixing_enthalpy_path: Path,
    phonons_path: Path,
    phase_stability_path: Path,
    defects_path: Path | None,
    gap_method: str | None,
    require_defects: bool,
    promising_max_mixing: float,
    low_priority_mixing: float,
    promising_max_hull: float,
    low_priority_hull: float,
    gap_consistency_tolerance: float,
    output_path: Path,
    report_path: Path,
    summary_path: Path | None,
) -> None:
    """Rank candidates for further DFT or experimental study."""
    from ..stability.recommendation import generate_recommendations

    try:
        frame, summary = generate_recommendations(
            pairs_path=pairs_path,
            gap_results_path=gap_results_path,
            mixing_enthalpy_path=mixing_enthalpy_path,
            phonons_path=phonons_path,
            phase_stability_path=phase_stability_path,
            defects_path=defects_path,
            output_path=output_path,
            report_path=report_path,
            summary_path=summary_path,
            gap_method=gap_method,
            require_defects=require_defects,
            settings=RecommendationSettings(
                promising_max_mixing_enthalpy_mev_per_atom=promising_max_mixing,
                low_priority_mixing_enthalpy_mev_per_atom=low_priority_mixing,
                promising_max_hull_ev_per_atom=promising_max_hull,
                low_priority_hull_ev_per_atom=low_priority_hull,
                gap_consistency_tolerance_ev=gap_consistency_tolerance,
            ),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    counts = summary["classification_counts"]
    click.echo(
        "Stage 11 recommendation summary: "
        f"candidates={len(frame)} promising={counts.get('promising', 0)} "
        f"uncertain={counts.get('uncertain', 0)} "
        f"low-priority={counts.get('low-priority', 0)} "
        f"output={output_path} report={report_path}"
    )


# ---------------------------------------------------------------------------
# composition-screen
# ---------------------------------------------------------------------------
@cli.command("composition-screen")
@click.option(
    "--df",
    "df_paths",
    multiple=True,
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Pickled normalized dataset DataFrame (repeatable).",
)
@click.option(
    "--valence-ids",
    "valence_ids",
    type=click.Path(exists=True, path_type=Path),
    help="Optional JSON list of valence-valid IDs (from `valence-filter`).",
)
@click.option(
    "--nelems",
    type=click.IntRange(2, 3),
    multiple=True,
    default=(2,),
    show_default=True,
    help="Element count: 2 or 3; repeat to screen both in one run.",
)
@click.option("--max-bandgap", type=float, default=1.0, show_default=True)
@click.option("--max-e-hull", "max_e_hull", type=float, default=0.0, show_default=True)
@click.option("--min-group-size", type=int, default=2, show_default=True)
@click.option("--min-x-elements", type=int, default=2, show_default=True)
@click.option(
    "--excluded-elements",
    "excluded_elements",
    multiple=True,
    default=[],
    help="Extra elements to exclude (added to the default list).",
)
@click.option(
    "--output",
    "output",
    type=click.Path(path_type=Path),
    required=True,
    help="CSV table of composition-template candidates.",
)
@click.option(
    "--summary",
    "summary",
    type=click.Path(path_type=Path),
    help="Optional JSON screening summary.",
)
@click.option(
    "--structures-output",
    type=click.Path(path_type=Path),
    help="Pickled candidate DataFrame for Stage 03, deduplicated by material ID.",
)
def composition_screen_cmd(
    df_paths: tuple[Path, ...],
    valence_ids: Path | None,
    nelems: tuple[int, ...],
    max_bandgap: float,
    max_e_hull: float,
    min_group_size: int,
    min_x_elements: int,
    excluded_elements: tuple[str, ...],
    output: Path,
    summary: Path | None,
    structures_output: Path | None,
) -> None:
    """Screen composition-template candidates before structure matching."""
    from monty.serialization import dumpfn, loadfn

    destinations = [path.resolve() for path in (output, summary, structures_output) if path]
    sources = {path.resolve() for path in (*df_paths, valence_ids) if path}
    if len(set(destinations)) != len(destinations) or sources.intersection(destinations):
        raise click.ClickException("Output paths must be distinct and must not overwrite inputs.")
    frames = [pd.read_pickle(path) for path in df_paths]
    df = pd.concat(frames, axis=0)
    if valence_ids:
        valid = loadfn(str(valence_ids))
        df = df.loc[valid]

    thresholds = Thresholds.default(nelems[0])
    excluded = (
        coerce_excluded(excluded_elements) if excluded_elements else thresholds.excluded_elements
    )

    try:
        candidates, report = screen_composition_batches(
            df,
            element_counts=nelems,
            max_bandgap=max_bandgap,
            max_e_hull=max_e_hull,
            excluded_elements=excluded,
            min_group_size=min_group_size,
            min_x_elements=min_x_elements,
        )
        structures = candidate_structures(df, candidates) if structures_output else None
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    report["input_files"] = [str(path) for path in df_paths]
    report["valence_ids"] = str(valence_ids) if valence_ids else None
    if structures_output:
        report["structures_output"] = str(structures_output)
        structures_output.parent.mkdir(parents=True, exist_ok=True)
        structures.to_pickle(structures_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(output, index=False)
    if summary:
        summary.parent.mkdir(parents=True, exist_ok=True)
        dumpfn(report, str(summary))

    click.echo(
        f"Wrote {len(candidates)} composition-candidate rows "
        f"across {report['template_count']} templates to {output}"
    )
    if structures_output:
        click.echo(f"Wrote {len(structures)} unique candidate structures to {structures_output}")


# ---------------------------------------------------------------------------
# group
# ---------------------------------------------------------------------------
@cli.command("group")
@click.option("--df-mp", "df_mp", type=click.Path(exists=True, path_type=Path))
@click.option("--df-wbm", "df_wbm", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--valence-ids",
    "valence_ids",
    type=click.Path(exists=True, path_type=Path),
    help="Optional JSON list of valence-valid IDs (from `valence-filter`).",
)
@click.option(
    "--nelems",
    type=int,
    default=2,
    show_default=True,
    help="Number of elements in the reduced composition (2 or 3).",
)
@click.option(
    "--condensed-dirs",
    "condensed_dirs",
    multiple=True,
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Directories of robocrys condensed JSONs (repeatable).",
)
@click.option(
    "--max-bandgap",
    type=float,
    default=1.0,
    show_default=True,
    help="Keep materials with PBE band gap below this (eV).",
)
@click.option(
    "--max-e-hull",
    "max_e_hull",
    type=float,
    default=0.0,
    show_default=True,
    help="Keep materials with energy above hull at most this (eV/atom).",
)
@click.option(
    "--max-natoms",
    type=int,
    default=None,
    help="Primitive-cell atom cap for the *output* structures (default 30 binary / 45 ternary).",
)
@click.option(
    "--excluded-elements",
    "excluded_elements",
    multiple=True,
    default=[],
    help="Extra elements to exclude (added to the default list).",
)
@click.option(
    "--output",
    "output",
    type=click.Path(path_type=Path),
    required=True,
    help="Output group JSON (array of StructureGroup records).",
)
@click.option("--no-verbose", is_flag=True, default=False)
def group_cmd(
    df_mp,
    df_wbm,
    valence_ids,
    nelems,
    condensed_dirs,
    max_bandgap,
    max_e_hull,
    max_natoms,
    excluded_elements,
    output,
    no_verbose,
):
    """Group materials by composition template + environment fingerprint."""
    from tqdm.auto import tqdm

    # Load + concatenate data.
    frames = []
    if df_mp:
        frames.append(pd.read_pickle(df_mp))
    if df_wbm:
        frames.append(pd.read_pickle(df_wbm))
    if not frames:
        raise click.UsageError("Provide at least one of --df-mp / --df-wbm.")
    df_all = pd.concat(frames, axis=0)

    # Optional valence pre-filter.
    if valence_ids:
        from monty.serialization import loadfn

        valid = loadfn(str(valence_ids))
        df_all = df_all.loc[valid]

    # Selection thresholds (stage 1).
    t = Thresholds.default(nelems).with_nelems(nelems)
    sel = t.selection
    if max_bandgap != sel.max_bandgap or max_e_hull != sel.max_e_hull:
        from dataclasses import replace

        t = replace(t, selection=replace(sel, max_bandgap=max_bandgap, max_e_hull=max_e_hull))
    excluded = coerce_excluded(excluded_elements) if excluded_elements else t.excluded_elements
    if max_natoms is not None:
        from dataclasses import replace

        t = replace(t, max_natoms=max_natoms)

    # Stage 1: select by nelems, gap, hull.
    df_t = df_all.loc[
        (df_all["nelems"] == nelems)
        & (df_all["e_hull"] <= max_e_hull)
        & (df_all["band_gap"] < max_bandgap),
        :,
    ]
    click.echo(
        f"Selected {len(df_t)} materials (nelems={nelems}, gap<{max_bandgap}, e_hull<={max_e_hull})"
    )

    # Stage 2: composition-template grouping.
    templates = group_by_composition_template(df_t, nelems=nelems)
    click.echo(f"{len(templates)} composition templates with >=2 members")

    # Stage 3: environment grouping within each template.
    loader = CondenseLoader(list(condensed_dirs))
    all_groups = []
    iterator = tqdm(
        templates.items(), disable=no_verbose, desc="env grouping", total=len(templates)
    )
    for key, entries in iterator:
        # entries: list of [mp_id, x_elem, band_gap]
        mp_ids = [e[0] for e in entries]
        condensed = [loader.get_condensed(mid) for mid in mp_ids]
        envs = find_unique_envs(condensed)
        groups = group_similar_structures(envs, key, mp_ids)
        attach_band_gaps(groups, entries)
        all_groups.extend(groups)

    # Keep groups with X-element diversity.
    import numpy as np

    all_groups = [g for g in all_groups if len(np.unique(g.X_element)) > 1]
    click.echo(f"{len(all_groups)} groups after X-diversity filter")

    # Stage 4: element exclusion + gap-diversity gate.
    valid_groups = []
    for g in all_groups:
        kept = apply_element_exclusion(g, excluded)
        if kept is None:
            continue
        if not has_gap_diversity(kept, require_zero=t.group.require_zero_gap_member):
            continue
        valid_groups.append(kept)
    click.echo(f"{len(valid_groups)} groups after element-exclusion + gap gate")

    # Stage 4b (output preparation): apply size gate to the referenced structures.
    all_ids = {mid for g in valid_groups for mid in g.mp_ids}
    if all_ids:
        calc_df = df_t.loc[list(all_ids)].copy()
        calc_df = apply_size_gate(calc_df, t.max_natoms)
        surviving = set(calc_df.index.astype(str))
        valid_groups = [g for g in valid_groups if all(m in surviving for m in g.mp_ids)]
    click.echo(f"{len(valid_groups)} groups survive the size gate (natoms<{t.max_natoms})")

    dump_group_df(valid_groups, output)
    click.echo(f"Wrote {len(valid_groups)} groups to {output}")


# ---------------------------------------------------------------------------
# pair
# ---------------------------------------------------------------------------
@cli.command("pair")
@click.option(
    "--groups",
    "groups_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Group JSON from `ss-screen group`.",
)
@click.option(
    "--gaps",
    "gaps_path",
    type=click.Path(exists=True, path_type=Path),
    help="Legacy mbj_gaps_*_pmg_info.csv with computed gaps.",
)
@click.option(
    "--gap-results",
    "gap_results",
    multiple=True,
    type=click.Path(exists=True, path_type=Path),
    help="External gap-result CSV using the stable schema from `gap-validate`.",
)
@click.option("--low-gap", "low_gap", type=float, default=0.15, show_default=True)
@click.option("--direct-min", "direct_min", type=float, default=0.15, show_default=True)
@click.option("--direct-max", "direct_max", type=float, default=1.5, show_default=True)
@click.option("--pair-any-below", "pair_any_below", type=float, default=0.3, show_default=True)
@click.option("--pair-any-above", "pair_any_above", type=float, default=0.2, show_default=True)
@click.option("--pair-both-below", "pair_both_below", type=float, default=0.8, show_default=True)
@click.option("--method", help="Method to select from --gap-results when multiple are present.")
@click.option("--summary", type=click.Path(path_type=Path), help="Optional coverage JSON summary.")
@click.option("--output", "output", type=click.Path(path_type=Path), required=True)
def pair_cmd(
    groups_path,
    gaps_path,
    gap_results,
    low_gap,
    direct_min,
    direct_max,
    pair_any_below,
    pair_any_above,
    pair_both_below,
    method,
    summary,
    output,
):
    """Enumerate promising alloying pairs from computed gaps."""
    from ..config import PairThresholds
    from ..pair.pairing import attach_gaps_and_compress, gaps_valid

    t = PairThresholds(
        low_gap=low_gap,
        direct_min=direct_min,
        direct_max=direct_max,
        pair_any_below=pair_any_below,
        pair_any_above=pair_any_above,
        pair_both_below=pair_both_below,
    )
    if bool(gaps_path) == bool(gap_results):
        raise click.UsageError("Provide exactly one of --gaps or --gap-results.")

    if gap_results:
        from ..pair.gap_feedback import generate_pairs_from_gap_results

        pairs_df, report = generate_pairs_from_gap_results(
            groups_path=groups_path,
            gap_paths=gap_results,
            output=output,
            summary=summary,
            method=method,
            thresholds=t,
        )
        click.echo(
            f"Wrote {len(pairs_df)} pairs to {output} "
            f"(coverage={report['covered_materials']}/{report['materials_in_groups']})"
        )
        return

    groups = load_group_df(groups_path)
    gap_map = read_mbj_gaps(gaps_path)

    all_pairs = []
    for g in groups:
        compressed = attach_gaps_and_compress(g, gap_map)
        if compressed is None:
            continue
        g_aligned, gaps = compressed
        if not gaps_valid(gaps, t):
            continue
        all_pairs.extend(enumerate_pairs(g_aligned, gaps, t))

    pairs_df = pairs_to_dataframe(all_pairs)
    write_pairs_csv(pairs_df, output)
    click.echo(f"Wrote {len(pairs_df)} pairs to {output}")


@cli.command("mp-reproduce")
@click.option("--mp-zip", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--mbj-bundle", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--output-dir", required=True, type=click.Path(path_type=Path))
@click.option("--workers", default=4, show_default=True, type=click.IntRange(min=1))
@click.option(
    "--descriptor-cache",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Explicitly reuse verified descriptors; otherwise calculate them afresh.",
)
def mp_reproduce_cmd(
    mp_zip: Path,
    mbj_bundle: Path,
    output_dir: Path,
    workers: int,
    descriptor_cache: Path | None,
) -> None:
    """Reproduce the dated MP ZIP -> 318-pair workflow (Linux/WSL Python 3.11).

    Requires the separately supplied frozen mBJ bundle. Recomputes composition
    candidates and groups from the database; never launches DFT or MACE.
    """
    import json

    from ..mp_reproduction import reproduce_mp_zip

    try:
        result = reproduce_mp_zip(
            mp_zip, mbj_bundle, output_dir, workers=workers, descriptor_cache=descriptor_cache
        )
    except (ValueError, ImportError, FileNotFoundError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(result, ensure_ascii=False, indent=2))


# Stage 13 geometry evaluator is opt-in and does not change legacy CLI behavior.
from ..geometry_cli import main as geometry_evaluate_cmd
cli.add_command(geometry_evaluate_cmd)

from ..pair.wavelength import main as pair_wavelength_cmd
cli.add_command(pair_wavelength_cmd)


if __name__ == "__main__":
    cli()
