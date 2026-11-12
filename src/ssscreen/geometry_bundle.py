"""Build Stage 13 manifests from this package's checked relaxation records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
from pymatgen.core import Composition, Structure

from .geometry_pipeline import DEFAULT_CONFIG

FRACTION_TOLERANCE = 1e-6


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_relaxed(record: dict, expected: Composition, cwd: Path) -> tuple[Path, str]:
    """Require composition, provenance, full-cell relaxation, convergence and QC."""
    if not record.get("converged") or record.get("status") != "success":
        raise ValueError("relaxation did not converge")
    if not record.get("quality_control", {}).get("passed"):
        raise ValueError("relaxation quality control failed")
    settings = record.get("settings", {})
    backend = record.get("backend", {})
    if settings.get("cell_mode") != "full" or not backend.get("model_sha256"):
        raise ValueError("missing full-cell/model provenance")
    output = record["output_structure"]
    path = Path(output["path"])
    path = path if path.is_absolute() else cwd / path
    if digest(path) != output["sha256"]:
        raise ValueError("relaxed structure SHA mismatch")
    structure = Structure.from_file(str(path))
    actual, expected = structure.composition.fractional_composition, expected.fractional_composition
    elements = set(actual) | set(expected)
    if any(abs(actual[e] - expected[e]) > FRACTION_TOLERANCE for e in elements):
        raise ValueError("relaxed structure composition does not match candidate")
    # Device is execution provenance, not a different relaxation method.
    # Preserve it in the source records; compare all remaining backend fields.
    method_backend = {key: value for key, value in backend.items() if key != "device"}
    method = hashlib.sha256(
        json.dumps({"backend": method_backend, "settings": settings}, sort_keys=True).encode()
    ).hexdigest()
    return path.resolve(), method


def build_bundle(
    pairs_path: Path,
    relaxation_path: Path,
    substrates_path: Path,
    output_dir: Path,
    cwd: Path,
    wavelength_um: float,
) -> dict:
    """Preserve every pair; invalid/missing geometry remains explicitly unavailable."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pairs = pd.read_csv(pairs_path)
    records = [json.loads(line) for line in relaxation_path.read_text().splitlines() if line]
    ids = [r["structure_id"] for r in records]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate relaxation structure identities")
    endpoints = {r["material_id"]: r for r in records if r["structure_role"] == "endmember"}
    candidates, ends, alloys, failures = [], [], [], []
    selected = {}
    reference = "relax-" + digest(relaxation_path)
    for index, pair in pairs.iterrows():
        cid = f"pair-{index}-x050"
        sqs = [r for r in records if r["structure_role"] == "sqs" and r["pair_index"] == index]
        if len(sqs) > 1:
            raise ValueError("expected one SQS per pair")
        record = sqs[0] if sqs else None
        fraction = float(record["actual_fraction_b"]) if record else 0.5
        if abs(fraction - 0.5) > FRACTION_TOLERANCE:
            raise ValueError("this run requires actual x=0.5")
        substitution = record.get("substitution", {}) if record else {}
        candidates.append(
            dict(
                candidate_id=cid,
                pair_id=f"pair-{index}",
                stage12_pair_index=index,
                actual_fraction_b=fraction,
                reference_set_id=reference,
                expected_structure_ids=record["structure_id"] if record else "",
                comp_a=pair.comp_a,
                comp_b=pair.comp_b,
                gap_a_eV=pair.gap_a,
                gap_b_eV=pair.gap_b,
                replaceable_a=substitution.get("from", ""),
                replaceable_b=substitution.get("to", ""),
            )
        )
        methods = []
        for role in ("a", "b"):
            end = endpoints.get(pair[f"mp_id_{role}"])
            if end is None:
                failures.append(dict(candidate_id=cid, role=role, error="missing endpoint"))
                continue
            try:
                path, method = validate_relaxed(end, Composition(pair[f"comp_{role}"]), cwd)
                methods.append(method)
                ends.append(
                    dict(
                        pair_id=f"pair-{index}",
                        role=role.upper(),
                        reference_set_id=reference,
                        structure_file=str(path),
                        sha256=end["output_structure"]["sha256"],
                        status="success",
                        qc_status="pass",
                        method=method,
                    )
                )
            except (ValueError, KeyError, OSError) as exc:
                failures.append(dict(candidate_id=cid, role=role, error=str(exc)))
        if record is None:
            continue
        try:
            expected = (1 - fraction) * Composition(
                pair.comp_a
            ).fractional_composition + fraction * Composition(pair.comp_b).fractional_composition
            path, method = validate_relaxed(record, expected, cwd)
            if len(methods) != 2 or any(m != method for m in methods):
                raise ValueError("alloy and endpoints do not share a validated method")
            selected[cid] = record["structure_id"]
            alloys.append(
                dict(
                    candidate_id=cid,
                    structure_id=record["structure_id"],
                    seed=record["seed"],
                    actual_fraction_b=fraction,
                    reference_set_id=reference,
                    structure_file=str(path),
                    sha256=record["output_structure"]["sha256"],
                    status="success",
                    qc_status="pass",
                    method=method,
                    cell_mode="full",
                )
            )
        except (ValueError, KeyError, OSError) as exc:
            failures.append(dict(candidate_id=cid, role="alloy", error=str(exc)))
    substrates = json.loads(substrates_path.read_text())
    substrate_ids = [s["substrate_id"] for s in substrates]
    if len(set(substrate_ids)) != len(substrate_ids):
        raise ValueError("duplicate substrate IDs")
    for substrate in substrates:
        path = Path(substrate["structure_file"])
        path = path if path.is_absolute() else substrates_path.parent / path
        if digest(path) != substrate["sha256"]:
            raise ValueError("substrate SHA mismatch")
        substrate["structure_file"] = str(path.resolve())
    pd.DataFrame(candidates).to_csv(output_dir / "candidates.csv", index=False)
    pd.DataFrame(
        ends,
        columns=[
            "pair_id",
            "role",
            "reference_set_id",
            "structure_file",
            "sha256",
            "status",
            "qc_status",
            "method",
        ],
    ).to_csv(output_dir / "endmembers.csv", index=False)
    pd.DataFrame(
        alloys,
        columns=[
            "candidate_id",
            "structure_id",
            "seed",
            "actual_fraction_b",
            "reference_set_id",
            "structure_file",
            "sha256",
            "status",
            "qc_status",
            "method",
            "cell_mode",
        ],
    ).to_csv(output_dir / "alloy_structures.csv", index=False)
    (output_dir / "substrates.json").write_text(json.dumps(substrates, indent=2))
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    config["detector_context"]["target_wavelength_um"] = wavelength_um
    config["substrate"]["selected_structure_ids"] = selected
    # The underlying geometry evaluator does not implement cache restoration.
    config["execution"]["resume"] = False
    (output_dir / "config.json").write_text(json.dumps(config, indent=2))
    report = dict(
        candidates=len(candidates),
        valid_alloys=len(alloys),
        failures=failures,
        input_relaxation_sha256=digest(relaxation_path),
        substrate_manifest_sha256=digest(substrates_path),
    )
    (output_dir / "assembly_audit.json").write_text(json.dumps(report, indent=2))
    return report
