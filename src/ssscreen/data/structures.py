"""Normalize local structures for screening without inferring electronic properties."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from .condense import load_structure

_STRUCTURE_NAMES = {"POSCAR", "CONTCAR"}
_STRUCTURE_SUFFIXES = {".vasp", ".cif", ".json"}


def _supported(path: Path) -> bool:
    return path.name.upper() in _STRUCTURE_NAMES or path.suffix.lower() in _STRUCTURE_SUFFIXES


def _nonnegative(value: object, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite number >= 0") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} must be a finite number >= 0")
    return number


def load_structure_dataset(
    *,
    output: str | Path,
    input_dirs: Sequence[str | Path] = (),
    inputs: Sequence[str | Path] = (),
    metadata_path: str | Path | None = None,
    band_gap_default: float = 0.0,
    e_hull_default: float = 0.0,
    source: str = "local-structures",
    provenance_path: str | Path | None = None,
) -> pd.DataFrame:
    """Read POSCAR/CIF/VASP/JSON files into the shared screening schema.

    POSCAR and CONTCAR use their parent folder as material ID; other files use
    their filename stem. Duplicate IDs are errors. Missing gap/hull values use
    explicit defaults, recorded as assumptions rather than computed evidence.
    """
    defaults = {
        "band_gap": _nonnegative(band_gap_default, "band_gap_default"),
        "e_hull": _nonnegative(e_hull_default, "e_hull_default"),
    }
    paths: set[Path] = set()
    for directory in input_dirs:
        root = Path(directory)
        if not root.is_dir():
            raise ValueError(f"not a structure directory: {root}")
        paths.update(p.resolve() for p in root.rglob("*") if p.is_file() and _supported(p))
    for item in inputs:
        path = Path(item)
        if not path.is_file() or not _supported(path):
            raise ValueError(f"not a supported structure file: {path}")
        paths.add(path.resolve())
    if not paths:
        raise ValueError("no supported structure files found")

    metadata = pd.DataFrame()
    if metadata_path is not None:
        metadata_path = Path(metadata_path)
        metadata = pd.read_csv(
            metadata_path,
            sep="\t" if metadata_path.suffix.lower() == ".tsv" else ",",
            dtype={"material_id": str},
        )
        if "material_id" not in metadata:
            raise ValueError("metadata must contain a material_id column")
        if metadata["material_id"].isna().any() or metadata["material_id"].str.strip().eq("").any():
            raise ValueError("metadata contains an empty material_id")
        if metadata["material_id"].duplicated().any():
            raise ValueError("metadata contains duplicate material_id values")
        metadata = metadata.set_index("material_id")

    records = []
    file_records = []
    identities: dict[str, Path] = {}
    for path in sorted(paths):
        material_id = path.parent.name if path.name.upper() in _STRUCTURE_NAMES else path.stem
        if material_id in identities:
            raise ValueError(
                f"duplicate material_id {material_id!r}: {identities[material_id]} and {path}"
            )
        identities[material_id] = path
        try:
            structure = load_structure(path)
            if len(structure) == 0:
                raise ValueError("empty structure")
        except Exception as exc:
            raise ValueError(f"could not read structure {path}: {exc}") from exc
        values = metadata.loc[material_id].to_dict() if material_id in metadata.index else {}
        defaulted_fields = [field for field in defaults if pd.isna(values.get(field))]
        properties = {
            field: (
                default
                if field in defaulted_fields
                else _nonnegative(values[field], f"{material_id} {field}")
            )
            for field, default in defaults.items()
        }
        row_source = values.get("source")
        if pd.isna(row_source) or not str(row_source).strip():
            row_source = source
        file_record = {
            "material_id": material_id,
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "defaulted_fields": defaulted_fields,
        }
        composition = structure.composition
        records.append(
            {
                "material_id": material_id,
                "formula": composition.reduced_formula,
                "composition": composition,
                "reduced_composition": composition.reduced_composition,
                "nelems": len(composition),
                **properties,
                "energy_above_hull": properties["e_hull"],
                "structure": structure,
                "primitive_structure": structure.get_primitive_structure(),
                "source": str(row_source),
                "source_metadata": file_record,
            }
        )
        file_records.append(file_record)

    unknown_ids = set(metadata.index) - set(identities)
    if unknown_ids:
        raise ValueError(f"metadata has unknown material_id values: {sorted(unknown_ids)}")
    provenance = {
        "schema_version": 1,
        "source": source,
        "defaults": defaults,
        "note": "Default gap/hull values are workflow assumptions, not computed properties.",
        "metadata_path": str(metadata_path.resolve()) if metadata_path is not None else None,
        "metadata_sha256": (
            hashlib.sha256(metadata_path.read_bytes()).hexdigest()
            if metadata_path is not None
            else None
        ),
        "files": file_records,
        "count": len(records),
    }
    frame = pd.DataFrame.from_records(records).set_index("material_id")
    frame.attrs["ssscreen_local_dataset_provenance"] = provenance
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_pickle(output)
    if provenance_path is not None:
        provenance_path = Path(provenance_path)
        provenance_path.parent.mkdir(parents=True, exist_ok=True)
        provenance_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return frame
