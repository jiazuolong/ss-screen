"""Robocrys condensation helpers for ``ss-screen condense``.

This ports the single-structure / batch condensation pattern from the read-only
reference scripts ``mp-condense/condense_one.py`` and ``mp-condense/condense.py``.
The optional ``robocrys`` dependency is imported only inside the runtime path so
the core package and default tests do not need it installed.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from monty.serialization import dumpfn, loadfn
from pymatgen.core import Structure


@dataclass(frozen=True)
class CondenseSummary:
    """Counts from a condensation run."""

    written: int = 0
    skipped: int = 0
    failed: int = 0
    stopped: bool = False
    pending: int = 0


@dataclass(frozen=True)
class CondenseRecord:
    """Metadata for one attempted condensed-structure archive member."""

    material_id: str
    status: str
    output_path: str
    source_path: str = ""
    formula: str = ""
    error: str = ""
    file_size: int = 0
    sha256: str = ""


REQUIRED_CONDENSED_KEYS = {
    "formula",
    "spg_symbol",
    "crystal_system",
    "mineral",
    "dimensionality",
    "sites",
    "distances",
    "angles",
    "nnn_distances",
    "components",
    "component_makeup",
    "vdw_heterostructure_info",
}


def expand_input_paths(inputs: Sequence[str | Path]) -> list[Path]:
    """Expand input files/directories into a deterministic file list."""
    paths: list[Path] = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            paths.extend(
                sorted(p for p in path.iterdir() if p.is_file() and not p.name.startswith("."))
            )
        else:
            paths.append(path)
    return paths


def load_structure(path: str | Path) -> Structure:
    """Load a pymatgen Structure from a Monty JSON or pymatgen-readable file."""
    path = Path(path)
    try:
        obj = loadfn(str(path))
        if isinstance(obj, Structure):
            return obj
        if isinstance(obj, dict):
            return Structure.from_dict(obj)
    except Exception:
        pass
    return Structure.from_file(str(path))


def _make_condenser():
    try:
        from robocrys import StructureCondenser
    except ImportError as exc:
        raise ImportError(
            "The optional 'robocrys' dependency is required for `ss-screen condense`. "
            "Install it with `pip install -e '.[condense]'`."
        ) from exc
    return StructureCondenser()


def condense_structure(structure: Structure, condenser=None) -> dict:
    """Condense one structure with robocrys."""
    condenser = condenser or _make_condenser()
    try:
        structure.add_oxidation_state_by_guess()
    except Exception:
        pass
    return condenser.condense_structure(structure)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_dumpfn(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        dumpfn(obj, str(tmp_path))
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _write_jsonl(records: Sequence[CondenseRecord], manifest_path: str | Path | None) -> None:
    if manifest_path is None:
        return
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")


def write_index(records: Sequence[CondenseRecord], index_path: str | Path | None) -> None:
    """Write a compact CSV index for a condensation run."""
    if index_path is None:
        return
    path = Path(index_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame.from_records(
        [asdict(record) for record in records], columns=list(CondenseRecord.__dataclass_fields__)
    ).to_csv(path, index=False)


def _record_for_file(material_id: str, path: Path, status: str, error: str = "") -> CondenseRecord:
    try:
        condensed = loadfn(str(path))
        formula = str(condensed.get("formula", "")) if isinstance(condensed, dict) else ""
    except Exception:
        formula = ""
    if path.exists():
        return CondenseRecord(
            material_id=material_id,
            status=status,
            output_path=str(path),
            source_path="",
            formula=formula,
            error=error,
            file_size=path.stat().st_size,
            sha256=_sha256(path),
        )
    return CondenseRecord(
        material_id=material_id, status=status, output_path=str(path), error=error
    )


def condense_materials(
    materials: Sequence[tuple[str, Structure]],
    output_dir: str | Path,
    *,
    overwrite: bool = False,
    manifest_path: str | Path | None = None,
    index_path: str | Path | None = None,
    condense_func=condense_structure,
    condenser=None,
    continue_on_error: bool = True,
    stop_file: str | Path | None = None,
) -> CondenseSummary:
    """Condense ``(material_id, structure)`` pairs into per-material JSON files."""
    summary, records = _condense_materials_with_records(
        materials,
        output_dir,
        overwrite=overwrite,
        condense_func=condense_func,
        condenser=condenser,
        continue_on_error=continue_on_error,
        manifest_path=manifest_path,
        index_path=index_path,
        stop_file=stop_file,
    )
    _write_jsonl(records, manifest_path)
    write_index(records, index_path)
    return summary


def _condense_materials_with_records(
    materials: Sequence[tuple[str, Structure]],
    output_dir: str | Path,
    *,
    overwrite: bool = False,
    condense_func=condense_structure,
    condenser=None,
    continue_on_error: bool = True,
    manifest_path: str | Path | None = None,
    index_path: str | Path | None = None,
    stop_file: str | Path | None = None,
) -> tuple[CondenseSummary, list[CondenseRecord]]:
    """Journal attempts and save an index on completion, cancellation or error."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records: list[CondenseRecord] = []
    written = skipped = failed = 0
    stopped = False
    _write_jsonl([], manifest_path)
    try:
        for material_id, structure in materials:
            if stop_file is not None and Path(stop_file).is_file():
                stopped = True
                break
            material_id = str(material_id)
            outpath = output_dir / f"{material_id}.json"
            try:
                if outpath.exists() and not overwrite:
                    skipped += 1
                    records.append(_record_for_file(material_id, outpath, "skipped"))
                else:
                    condensed = condense_func(structure, condenser=condenser)
                    _atomic_dumpfn(condensed, outpath)
                    written += 1
                    records.append(_record_for_file(material_id, outpath, "written"))
            except KeyboardInterrupt:
                # A terminal interrupt may arrive during one structure. Its
                # output is atomic; completed earlier JSONs remain usable.
                stopped = True
                break
            except Exception as exc:
                failed += 1
                records.append(
                    CondenseRecord(
                        material_id=material_id,
                        status="failed",
                        output_path=str(outpath),
                        error=str(exc),
                    )
                )
                if not continue_on_error:
                    raise
            if manifest_path is not None:
                with Path(manifest_path).open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(asdict(records[-1]), sort_keys=True) + "\n")
    finally:
        _write_jsonl(records, manifest_path)
        write_index(records, index_path)

    return (
        CondenseSummary(
            written=written,
            skipped=skipped,
            failed=failed,
            stopped=stopped,
            pending=len(materials) - len(records),
        ),
        records,
    )


def dataframe_materials(
    df_path: str | Path,
    *,
    structure_col: str = "structure",
    material_id_col: str | None = None,
    limit: int | None = None,
) -> list[tuple[str, Structure]]:
    """Load ``(material_id, structure)`` pairs from a normalized pickle DataFrame."""
    df = pd.read_pickle(df_path)
    if limit is not None:
        df = df.head(limit)

    materials: list[tuple[str, Structure]] = []
    for index, row in df.iterrows():
        material_id = row[material_id_col] if material_id_col else index
        materials.append((str(material_id), row[structure_col]))
    return materials


def condense_dataframe(
    df_path: str | Path,
    output_dir: str | Path,
    *,
    structure_col: str = "structure",
    material_id_col: str | None = None,
    limit: int | None = None,
    overwrite: bool = False,
    manifest_path: str | Path | None = None,
    index_path: str | Path | None = None,
    condense_func=condense_structure,
    condenser=None,
    continue_on_error: bool = True,
    stop_file: str | Path | None = None,
) -> CondenseSummary:
    """Condense structures from a normalized dataset DataFrame archive."""
    if condenser is None and condense_func is condense_structure:
        condenser = _make_condenser()
    return condense_materials(
        dataframe_materials(
            df_path,
            structure_col=structure_col,
            material_id_col=material_id_col,
            limit=limit,
        ),
        output_dir,
        overwrite=overwrite,
        manifest_path=manifest_path,
        index_path=index_path,
        condense_func=condense_func,
        condenser=condenser,
        continue_on_error=continue_on_error,
        stop_file=stop_file,
    )


def condense_paths(
    inputs: Sequence[str | Path],
    output_dir: str | Path,
    *,
    overwrite: bool = False,
    manifest_path: str | Path | None = None,
    index_path: str | Path | None = None,
    continue_on_error: bool = True,
    stop_file: str | Path | None = None,
) -> CondenseSummary:
    """Condense input structure files into ``{material_id}.json`` outputs."""
    condenser = _make_condenser()
    materials = []
    load_failure_records: list[CondenseRecord] = []
    load_failures = 0
    output_dir = Path(output_dir)
    for path in expand_input_paths(inputs):
        try:
            materials.append((path.stem, load_structure(path)))
        except Exception as exc:
            load_failures += 1
            load_failure_records.append(
                CondenseRecord(
                    material_id=path.stem,
                    status="failed",
                    output_path=str(output_dir / f"{path.stem}.json"),
                    source_path=str(path),
                    error=str(exc),
                )
            )
            if not continue_on_error:
                _write_jsonl(load_failure_records, manifest_path)
                write_index(load_failure_records, index_path)
                raise
    summary, condense_records = _condense_materials_with_records(
        materials,
        output_dir,
        overwrite=overwrite,
        condenser=condenser,
        continue_on_error=continue_on_error,
        manifest_path=manifest_path,
        index_path=index_path,
        stop_file=stop_file,
    )
    records = [*load_failure_records, *condense_records]
    _write_jsonl(records, manifest_path)
    write_index(records, index_path)
    return CondenseSummary(
        written=summary.written,
        skipped=summary.skipped,
        failed=summary.failed + load_failures,
        stopped=summary.stopped,
        pending=summary.pending,
    )


def build_archive_index(
    condensed_dir: str | Path, index_path: str | Path | None = None
) -> pd.DataFrame:
    """Build a compact index from an existing per-material JSON archive."""
    records = [
        _record_for_file(path.stem, path, "present")
        for path in sorted(Path(condensed_dir).glob("*.json"))
    ]
    df = pd.DataFrame.from_records([asdict(record) for record in records])
    if index_path is not None:
        Path(index_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(index_path, index=False)
    return df


def validate_archive(
    condensed_dir: str | Path,
    *,
    index_path: str | Path | None = None,
) -> pd.DataFrame:
    """Validate required robocrys condensed JSON keys for an archive directory."""
    records = []
    for path in sorted(Path(condensed_dir).glob("*.json")):
        try:
            condensed = loadfn(str(path))
            if not isinstance(condensed, dict):
                raise ValueError("condensed file is not a dictionary")
            missing = sorted(REQUIRED_CONDENSED_KEYS - set(condensed.keys()))
            if missing:
                raise ValueError(f"missing required keys: {', '.join(missing)}")
            records.append(asdict(_record_for_file(path.stem, path, "valid")))
        except Exception as exc:
            records.append(
                asdict(
                    CondenseRecord(
                        material_id=path.stem,
                        status="invalid",
                        output_path=str(path),
                        error=str(exc),
                        file_size=path.stat().st_size if path.exists() else 0,
                        sha256=_sha256(path) if path.exists() else "",
                    )
                )
            )
    df = pd.DataFrame.from_records(records)
    if index_path is not None:
        Path(index_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(index_path, index=False)
    return df
