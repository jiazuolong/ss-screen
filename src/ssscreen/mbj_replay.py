# Adapted from mp-2944-mbj-results-20261104/replay_results.py (2026-11-04).
# The original bundle and its file manifest remain immutable.
"""Verify and replay this frozen result handoff using the active ss-screen env.

CPU postprocessing only. Never launches VASP, AiiDA, or SQS calculations.
"""

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

FILE_VERIFICATION_WORKERS = 8


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verify_manifest_files(bundle: Path, manifest: dict) -> None:
    """Validate every file; bounded I/O threads reduce WSL small-file latency."""

    def verify(item):
        relative, expected = item
        path = (bundle / relative).resolve()
        require(path.is_relative_to(bundle), f"Unsafe manifest path: {relative}")
        require(
            path.is_file()
            and digest(path) == expected["sha256"]
            and path.stat().st_size == expected["size"],
            f"File verification failed: {relative}",
        )

    with ThreadPoolExecutor(max_workers=FILE_VERIFICATION_WORKERS) as pool:
        for count, _ in enumerate(pool.map(verify, manifest.items()), 1):
            if count % 1000 == 0:
                print(f"Verified files {count}/{len(manifest)}", flush=True)


def replay_bundle(bundle: Path, output: Path) -> dict:
    """Validate immutable mBJ evidence and reproduce its frozen-group pairs."""
    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    require(not output.exists(), "Output must be a new directory; existing results are preserved")
    require(not output.is_relative_to(bundle), "Output must be outside the immutable bundle")
    manifest = json.loads((bundle / "FILE_MANIFEST.json").read_text(encoding="utf-8"))
    verify_manifest_files(bundle, manifest)
    print(f"Verified {len(manifest)} packaged files", flush=True)

    import pandas as pd

    import ssscreen
    from ssscreen.config import PairThresholds
    from ssscreen.pair.gap_export import validate_gap_results
    from ssscreen.pair.gap_feedback import generate_pairs_from_gap_results

    source = bundle / "snapshot"
    frozen = json.loads((source / "summary.json").read_text())
    tasks = pd.read_csv(source / "all_gap_tasks.csv", keep_default_na=False)
    expected = pd.read_csv(source / "all_gap_results.csv", keep_default_na=False)
    with (bundle / "structure_index.csv").open(newline="", encoding="utf-8") as stream:
        structure_index = {r["task_id"]: r for r in csv.DictReader(stream)}
    require(
        len(tasks) == tasks.task_id.nunique() == tasks.material_id.nunique() == 2944,
        "Task coverage/uniqueness",
    )
    require(set(tasks.task_id) == set(structure_index), "Structure coverage")
    for row in tasks.to_dict("records"):
        entry = structure_index[row["task_id"]]
        for key in ["material_id", "source_task_id", "structure_sha256"]:
            require(
                str(row[key]) == entry[key], f"Structure index identity mismatch: {row['task_id']}"
            )
        raw = json.loads((bundle / entry["json_path"]).read_text())
        raw.pop("@version", None)
        require(
            canonical(raw) == row["structure_sha256"], f"Structure canonical SHA: {row['task_id']}"
        )
        payload = dict(
            schema_version=1,
            material_id=row["material_id"],
            method=row["method"],
            structure_sha256=row["structure_sha256"],
        )
        require(
            row["task_id"] == "gap-" + canonical(payload)[:24],
            f"Task ID mismatch: {row['task_id']}",
        )

    output.mkdir(parents=True)
    frames, reports = [], {}
    for batch in sorted((source / "batches").iterdir()):
        dest = output / "validation" / batch.name
        dest.mkdir(parents=True)
        accepted = validate_gap_results(
            batch / "gap_results.csv",
            tasks_path=batch / "gap_tasks.csv",
            method_metadata_path=batch / "method_metadata.json",
            output_path=dest / "validated.csv",
            rejected_path=dest / "rejected.csv",
            report_path=dest / "report.json",
        )
        report = accepted.attrs["validation_report"]
        require(
            report["rejected_count"] == 0
            and not report["missing_task_ids"]
            and not report["unaccepted_task_ids"],
            f"Strict validation failed: {batch.name}",
        )
        qc = pd.read_csv(batch / "independent_qc.csv", keep_default_na=False).set_index("task_id")
        for row in accepted[accepted.status == "success"].itertuples():
            q = qc.loc[row.task_id]
            require(
                q.status == "success"
                and all(
                    str(q[k]).lower() == "true"
                    for k in ["structure_matches", "method_matches", "electronic_converged"]
                ),
                f"QC rejected {row.task_id}",
            )
            require(
                abs(float(q.gap_eV) - row.band_gap) < 1e-8
                and str(q.is_direct).lower() == str(row.is_direct).lower(),
                f"QC values differ: {row.task_id}",
            )
        frames.append(accepted)
        reports[batch.name] = report
        print(f"Strictly validated {batch.name}: {len(accepted)} rows", flush=True)

    allg = pd.concat(frames, ignore_index=True)
    require(
        len(allg) == allg.task_id.nunique() == allg.material_id.nunique() == 2944,
        "Result coverage/duplicates",
    )
    require(set(allg.task_id) == set(tasks.task_id), "Result/task identity coverage")
    counts = {str(k): int(v) for k, v in allg.status.value_counts().items()}
    require(counts == frozen["result_counts"], "Frozen status counts differ")
    left, right = allg.set_index("task_id"), expected.set_index("task_id")
    for key in [
        "material_id",
        "formula",
        "method",
        "structure_sha256",
        "settings_sha256",
        "status",
        "error",
        "backend",
        "backend_version",
        "completed_at",
        "transition",
    ]:
        require(
            left[key].fillna("").astype(str).to_dict()
            == right[key].fillna("").astype(str).to_dict(),
            f"Frozen result field differs: {key}",
        )
    for tid in left.index:
        a, b = left.loc[tid], right.loc[tid]
        if b.band_gap != "":
            require(
                abs(float(a.band_gap) - float(b.band_gap)) < 1e-12, f"Frozen gap differs: {tid}"
            )
        else:
            require(pd.isna(a.band_gap), f"Unexpected filled gap: {tid}")
        if b.is_direct != "":
            require(
                str(a.is_direct).lower() == str(b.is_direct).lower(),
                f"Frozen directness differs: {tid}",
            )
    allg.to_csv(output / "all_gap_results.csv", index=False)
    good = allg[allg.status == "success"].copy()
    good.to_csv(output / "successful_gap_results.csv", index=False)
    allg[allg.status != "success"].to_csv(output / "excluded_gap_results.csv", index=False)

    # Change path columns only in a new convenience table; keep source task IDs.
    portable = tasks.copy()
    for idx, row in portable.iterrows():
        entry = structure_index[row.task_id]
        for fmt in ["json", "cif", "poscar"]:
            portable.at[idx, f"structure_{fmt}_path"] = str(bundle / entry[f"{fmt}_path"])
        portable.at[idx, "structure_path"] = str(bundle / entry["json_path"])
    portable.to_csv(output / "gap_tasks_resolved_paths.csv", index=False)
    backfill = portable.merge(
        allg[["task_id", "band_gap", "is_direct", "status", "error", "settings_sha256"]],
        on="task_id",
        validate="one_to_one",
    )
    backfill.to_csv(output / "endmember_gap_backfill.csv", index=False)

    pairframes, coverage = [], {}
    for branch in ["binary", "ternary"]:
        dest = output / branch
        dest.mkdir()
        pairs, report = generate_pairs_from_gap_results(
            groups_path=source / branch / "groups.json",
            gap_paths=[output / "successful_gap_results.csv"],
            method=frozen["method"],
            thresholds=PairThresholds(**frozen["thresholds"]),
            output=dest / "pairs.csv",
            summary=dest / "coverage.json",
        )
        require(
            len(pairs) == frozen["branches"][branch]["pair_count"], f"Pair count differs: {branch}"
        )
        pairs["branch"] = branch
        pairframes.append(pairs)
        coverage[branch] = report
    combined = pd.concat(pairframes, ignore_index=True)
    expected_pairs = pd.read_csv(source / "pairs_all_evidence.csv")

    def evidence(frame):
        return {
            (r.branch, int(r.source_group_index), *sorted([r.mp_id_a, r.mp_id_b]))
            for r in frame.itertuples()
        }

    require(
        evidence(combined) == evidence(expected_pairs),
        "Pair identities/groups differ from frozen snapshot",
    )
    gapmap = good.set_index("material_id")
    for row in combined.itertuples():
        for suffix in ["a", "b"]:
            mid = getattr(row, f"mp_id_{suffix}")
            require(
                abs(getattr(row, f"gap_{suffix}") - gapmap.loc[mid].band_gap) < 1e-12,
                f"Pair gap mismatch: {mid}",
            )
    combined["pair_key"] = combined.apply(
        lambda r: "|".join(sorted([r.mp_id_a, r.mp_id_b])), axis=1
    )
    combined.to_csv(output / "pairs_all_evidence.csv", index=False)
    unique = combined.drop_duplicates("pair_key").copy()
    unique.to_csv(output / "pairs_unique.csv", index=False)
    ids = set(unique.mp_id_a) | set(unique.mp_id_b)
    backfill[backfill.material_id.isin(ids)].to_csv(output / "candidate_materials.csv", index=False)
    require(
        len(unique) == frozen["unique_pairs"] and len(ids) == frozen["candidate_materials"],
        "Unique pair/material count differs",
    )
    versions = {"python": platform.python_version(), "ssscreen": ssscreen.__version__}
    for name in ["pymatgen", "pymatgen-core", "numpy", "scipy", "pandas", "monty", "spglib"]:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    save(output / "environment_this_replay.json", versions)
    summary = dict(
        passed=True,
        task_count=len(tasks),
        status_counts=counts,
        missing_result_rows=0,
        method=frozen["method"],
        pair_counts={b: r["pair_count"] for b, r in coverage.items()},
        unique_pairs=len(unique),
        candidate_materials=len(ids),
        thresholds=frozen["thresholds"],
        pbe_fallback=False,
        input_manifest_sha256=digest(bundle / "FILE_MANIFEST.json"),
        formal_identities_preserved=True,
        local_pending_tasks_used=False,
        scope="Existing results strict import, gap backfill and frozen-group pairing; no DFT/XML recollection/SQS; current environment recorded separately",
    )
    save(output / "replay_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    replay_bundle(args.bundle, args.output)
