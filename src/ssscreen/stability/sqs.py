"""Generate alloy/SQS input artifacts for preliminary stability screening."""

from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path

import pandas as pd
from monty.serialization import dumpfn
from pymatgen.core import Composition, Structure


def infer_single_site_substitution(comp_a: str, comp_b: str) -> tuple[str, str]:
    """Infer the one-element substitution needed to turn ``comp_a`` into ``comp_b``."""
    a = Composition(comp_a).fractional_composition
    b = Composition(comp_b).fractional_composition
    elements = sorted({str(el) for el in a.elements} | {str(el) for el in b.elements})
    removed: list[str] = []
    added: list[str] = []
    for element in elements:
        delta = b.get_atomic_fraction(element) - a.get_atomic_fraction(element)
        if delta < -1e-8:
            removed.append(element)
        elif delta > 1e-8:
            added.append(element)
    if len(removed) != 1 or len(added) != 1:
        raise ValueError(f"expected a single-site substitution, got {comp_a!r} -> {comp_b!r}")
    return removed[0], added[0]


def _load_pairs(path: str | Path) -> pd.DataFrame:
    pairs = pd.read_csv(path)
    unnamed = [col for col in pairs.columns if str(col).startswith("Unnamed:")]
    if unnamed:
        pairs = pairs.drop(columns=unnamed)
    required = {"comp_a", "comp_b", "mp_id_a", "mp_id_b"}
    missing = sorted(required - set(pairs.columns))
    if missing:
        raise ValueError(f"missing required pair columns: {', '.join(missing)}")
    return pairs


def _structure_for_row(row: pd.Series, structure_col: str) -> Structure:
    if "primitive_structure" in row and row["primitive_structure"] is not None:
        return row["primitive_structure"].copy()
    return row[structure_col].copy()


def _safe_filename(value: object) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value)).strip("-.")
    return cleaned or "structure"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_endpoint_structure(structure: Structure, material_id: str, output_dir: Path) -> Path:
    path = output_dir / "endmembers" / f"{_safe_filename(material_id)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    dumpfn(structure, str(path))
    return path


def _replace_fraction(
    structure: Structure,
    *,
    from_element: str,
    to_element: str,
    target_fraction: float,
    seed: int,
) -> tuple[Structure, int, int]:
    x_site_indices = [
        index
        for index, site in enumerate(structure)
        if getattr(site.specie, "symbol", str(site.specie)) == from_element
    ]
    if not x_site_indices:
        raise ValueError(f"prototype structure has no {from_element} sites")
    n_replace = round(target_fraction * len(x_site_indices))
    rng = random.Random(seed)
    selected = list(x_site_indices)
    rng.shuffle(selected)
    for index in selected[:n_replace]:
        structure.replace(index, to_element)
    return structure, n_replace, len(x_site_indices)


def _generate_icet_structure(
    structure: Structure,
    *,
    from_element: str,
    to_element: str,
    target_fraction: float,
    supercell: tuple[int, int, int],
    seed: int,
    cutoffs: list[float],
    sqs_steps: int | None,
) -> tuple[Structure, int, int]:
    try:
        from icet import ClusterSpace
        from icet.tools.structure_generation import generate_sqs_from_supercells
        from pymatgen.io.ase import AseAtomsAdaptor
    except ImportError as exc:
        raise ImportError(
            "icet SQS generation requires the optional `icet` and `ase` dependencies"
        ) from exc

    atoms = AseAtomsAdaptor.get_atoms(structure)
    atoms.pbc = True
    chemical_symbols = []
    active_sites = 0
    for site in structure:
        symbol = getattr(site.specie, "symbol", str(site.specie))
        if symbol == from_element:
            chemical_symbols.append([from_element, to_element])
            active_sites += 1
        else:
            chemical_symbols.append([symbol])
    if active_sites == 0:
        raise ValueError(f"prototype structure has no {from_element} sites")

    cluster_space = ClusterSpace(
        atoms,
        cutoffs=cutoffs,
        chemical_symbols=chemical_symbols,
    )
    target_concentrations = {}
    for sublattice in cluster_space.get_sublattices(atoms):
        if set(sublattice.chemical_symbols) == {from_element, to_element}:
            target_concentrations[sublattice.symbol] = {
                from_element: 1.0 - float(target_fraction),
                to_element: float(target_fraction),
            }
    if not target_concentrations:
        raise ValueError(f"could not find active icet sublattice for {from_element}->{to_element}")

    supercell_atoms = atoms.repeat(supercell)
    sqs_atoms = generate_sqs_from_supercells(
        cluster_space=cluster_space,
        supercells=[supercell_atoms],
        target_concentrations=target_concentrations,
        n_steps=sqs_steps,
        random_seed=seed,
    )
    generated = AseAtomsAdaptor.get_structure(sqs_atoms)
    generated_to_sites = sum(
        1 for site in generated if getattr(site.specie, "symbol", str(site.specie)) == to_element
    )
    repeat_count = supercell[0] * supercell[1] * supercell[2]
    baseline_to_sites = (
        sum(
            1
            for site in structure
            if getattr(site.specie, "symbol", str(site.specie)) == to_element
        )
        * repeat_count
    )
    replaced = generated_to_sites - baseline_to_sites
    available = active_sites * repeat_count
    if replaced < 0 or replaced > available:
        raise ValueError(f"icet generated an invalid substitution count: {replaced}/{available}")
    return generated, replaced, available


def _record_base(
    pair_index: int,
    row: pd.Series,
    target_fraction: float,
    supercell: tuple[int, int, int],
    seed: int,
    generator: str,
) -> dict:
    record = {
        "pair_index": int(pair_index),
        "mp_id_a": str(row["mp_id_a"]),
        "mp_id_b": str(row["mp_id_b"]),
        "comp_a": str(row["comp_a"]),
        "comp_b": str(row["comp_b"]),
        "target_fraction_b": float(target_fraction),
        "supercell": list(supercell),
        "seed": int(seed),
        "generator": generator,
    }
    for key in ("source_group_index", "gap_method", "gap_a", "gap_b"):
        if key in row and pd.notna(row[key]):
            value = row[key]
            record[key] = value.item() if hasattr(value, "item") else value
    return record


def _write_manifest(records: list[dict], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _validate_target_fractions(target_fractions: tuple[float, ...] | list[float]) -> None:
    invalid = [fraction for fraction in target_fractions if fraction < 0.0 or fraction > 1.0]
    if invalid:
        raise ValueError("target fractions must be between 0 and 1")


def generate_sqs_inputs(
    *,
    pairs_path: str | Path,
    dataset_path: str | Path,
    output_dir: str | Path,
    manifest_path: str | Path,
    target_fractions: tuple[float, ...] | list[float],
    supercell: tuple[int, int, int] = (2, 2, 2),
    seed: int = 0,
    structure_col: str = "structure",
    backend: str = "random",
    cutoffs: tuple[float, ...] | list[float] = (4.0,),
    sqs_steps: int | None = None,
) -> list[dict]:
    """Generate representative alloy structures and a JSONL manifest.

    This first Stage 6 generator is intentionally dependency-light. It creates
    deterministic random-substitution structures and records the limitation in
    the manifest; optimized SQS backends can consume the same artifact schema
    later.
    """
    if backend not in {"random", "icet"}:
        raise ValueError(f"unsupported SQS backend: {backend}")
    _validate_target_fractions(target_fractions)
    generator = "icet-generate_sqs_from_supercells" if backend == "icet" else "random-substitution"
    pairs = _load_pairs(pairs_path)
    input_sha256 = {
        "pairs": _sha256_file(Path(pairs_path)),
        "dataset": _sha256_file(Path(dataset_path)),
    }
    dataset = pd.read_pickle(dataset_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []

    for pair_index, row in pairs.iterrows():
        for fraction_index, target_fraction in enumerate(target_fractions):
            stable_seed = int(seed) + int(pair_index) * 1000003 + fraction_index
            record = _record_base(
                int(pair_index),
                row,
                float(target_fraction),
                supercell,
                stable_seed,
                generator,
            )
            try:
                from_element, to_element = infer_single_site_substitution(
                    str(row["comp_a"]), str(row["comp_b"])
                )
                record["substitution"] = {"from": from_element, "to": to_element}
                mp_id_a = str(row["mp_id_a"])
                mp_id_b = str(row["mp_id_b"])
                if mp_id_a not in dataset.index:
                    raise ValueError(f"dataset is missing endpoint structure {mp_id_a}")
                if mp_id_b not in dataset.index:
                    raise ValueError(f"dataset is missing endpoint structure {mp_id_b}")
                endpoint_a = _structure_for_row(dataset.loc[mp_id_a], structure_col)
                endpoint_b = _structure_for_row(dataset.loc[mp_id_b], structure_col)
                endpoint_a_path = _write_endpoint_structure(endpoint_a, mp_id_a, output_dir)
                endpoint_b_path = _write_endpoint_structure(endpoint_b, mp_id_b, output_dir)
                record.update(
                    {
                        "endpoint_a_structure_path": str(endpoint_a_path),
                        "endpoint_a_structure_sha256": _sha256_file(endpoint_a_path),
                        "endpoint_b_structure_path": str(endpoint_b_path),
                        "endpoint_b_structure_sha256": _sha256_file(endpoint_b_path),
                    }
                )
                structure = endpoint_a.copy()
                if backend == "icet":
                    structure, replaced, available = _generate_icet_structure(
                        structure,
                        from_element=from_element,
                        to_element=to_element,
                        target_fraction=float(target_fraction),
                        supercell=supercell,
                        seed=stable_seed,
                        cutoffs=list(cutoffs),
                        sqs_steps=sqs_steps,
                    )
                    limitation = (
                        "icet SQS generated by simulated annealing; quality metrics are "
                        "not yet exported"
                    )
                else:
                    structure.make_supercell(supercell)
                    structure, replaced, available = _replace_fraction(
                        structure,
                        from_element=from_element,
                        to_element=to_element,
                        target_fraction=float(target_fraction),
                        seed=stable_seed,
                    )
                    limitation = "random substitution only; not an optimized SQS correlation match"
                filename = (
                    f"pair_{int(pair_index):05d}_"
                    f"x{float(target_fraction):.3f}_{mp_id_a}_{row['mp_id_b']}.json"
                )
                structure_path = output_dir / filename
                dumpfn(structure, str(structure_path))
                record.update(
                    {
                        "status": "written",
                        "structure_path": str(structure_path),
                        "structure_sha256": _sha256_file(structure_path),
                        "replaced_sites": int(replaced),
                        "available_substitution_sites": int(available),
                        "actual_fraction_b": float(replaced / available),
                        "limitation": limitation,
                    }
                )
            except Exception as exc:
                record.update(
                    {
                        "status": "skipped",
                        "structure_path": "",
                        "limitation": str(exc),
                    }
                )
            records.append(record)

    _write_manifest(records, manifest_path)
    provenance = {
        "input_sha256": input_sha256,
        "parameters": {
            "target_fractions": list(target_fractions),
            "supercell": list(supercell),
            "seed": seed,
            "backend": backend,
            "cutoffs": list(cutoffs),
            "sqs_steps": sqs_steps,
        },
        "manifest_sha256": _sha256_file(Path(manifest_path)),
    }
    Path(manifest_path).with_suffix(".provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return records
