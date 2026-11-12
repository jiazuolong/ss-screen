"""Dated MP snapshot -> fresh groups -> audited mBJ pairing, without DFT.

The protocol comes from the audited local 2026-11-03 reproduction and
compare_mbj_local_groups.py. A descriptor cache is opt-in and bound to the
database, each input structure and every descriptor hash. Frozen groups are
used only as an acceptance reference, never as the final pairing input.
"""

from __future__ import annotations

import copy
import importlib.metadata
import json
import multiprocessing as mp
import signal
import stat
import time
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

import pandas as pd

from .config import DEFAULT_EXCLUDED_ELEMENTS, PairThresholds
from .data.condense import _make_condenser, condense_materials, validate_archive
from .data.io import dump_group_df
from .data.mp import load_mp_dataset_offline
from .mbj_replay import canonical, digest, replay_bundle, require, save
from .pair.gap_export import export_gap_candidates
from .pair.gap_feedback import generate_pairs_from_gap_results
from .pair.grouping import screen_composition_candidates
from .pair.structure_match import match_structure_candidates

PROFILE = "mp-20260923-local-20261104-v1"
MP_ZIP_SHA = "1bd05b742cf797ce01b8630c23c0c5bcf7949cf72a148f37510ffe96e88ad503"
DATABASE_SHA = "d54bca48d1e00bdfd8db7c1e5a7b5844ccb755b948335930f09fe85444a7ebb8"
DATABASE_BYTES = 2220736512
PREFILTER_HULL = 0.01
COMPOSITION_GAP = 1.0
COMPOSITION_HULL = 0.0
EXPECTED_DATASET = 46675
EXPECTED_CANDIDATES = 4948
EXPECTED_DESCRIPTORS = 4944
EXPECTED_PAIRS = 318
EXPECTED_ENDPOINTS = 317
EXCLUDED_IDS = frozenset({"mp-1205290", "mp-1208530", "mp-568220", "mp-574458"})
BRANCHES = {"binary": (2, 1759, 949, 30), "ternary": (3, 3189, 1995, 45)}
PENDING_METHOD = "external-method-pending-v1"
FIRST_TIMEOUT_SECONDS = 300
RETRY_TIMEOUT_SECONDS = 1800
GAP_TOLERANCE_EV = 1e-12
GEOMETRY_LENGTH_TOL = 1e-8
GEOMETRY_SITE_TOL = 1e-8
GEOMETRY_ANGLE_TOL = 1e-6
DERIVED_LATTICE_FIELDS = ("a", "b", "c", "alpha", "beta", "gamma", "volume")
_condenser = None


def checked_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    """Reject traversal, absolute paths, symlinks and duplicate ZIP names."""
    members = {}
    for info in archive.infolist():
        name = info.filename
        path = PurePosixPath(name)
        require(
            name
            and not path.is_absolute()
            and ".." not in path.parts
            and "\\" not in name
            and ":" not in name
            and not stat.S_ISLNK(info.external_attr >> 16),
            f"Unsafe ZIP member: {name}",
        )
        require(name not in members, f"Duplicate ZIP member: {name}")
        members[name] = info
    return members


def extract_database(
    archive_path: Path,
    destination: Path,
    *,
    expected_sha: str = DATABASE_SHA,
    expected_size: int = DATABASE_BYTES,
) -> Path:
    """Extract only the expected SQLite file, then verify the uncompressed bytes."""
    import hashlib

    require(not destination.exists(), "Database destination already exists")
    with zipfile.ZipFile(archive_path) as archive:
        members = checked_members(archive)
        require(set(members) <= {"mp/", "mp/default.db"}, "Unexpected MP archive contents")
        require("mp/default.db" in members, "mp/default.db is missing")
        require(members["mp/default.db"].file_size == expected_size, "Database size differs")
        destination.parent.mkdir(parents=True, exist_ok=True)
        hasher = hashlib.sha256()
        with archive.open("mp/default.db") as source, destination.open("xb") as target:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                hasher.update(chunk)
                target.write(chunk)
        require(hasher.hexdigest() == expected_sha, "Database SHA differs")
    return destination


def input_structure_hash(structure: Any) -> str:
    value = structure.as_dict()
    value.pop("@version", None)
    return canonical(value)


def load_descriptor_cache(cache: Path, materials: dict, output: Path) -> int:
    """Load explicitly requested descriptors, with exact source binding."""
    with zipfile.ZipFile(cache) as archive:
        members = checked_members(archive)
        manifest = json.loads(archive.read("cache_manifest.json"))
        require(manifest["profile"] == PROFILE, "Cache profile differs")
        require(manifest["database_sha256"] == DATABASE_SHA, "Cache database differs")
        entries = manifest["materials"]
        require(set(entries) == set(materials), "Cache material membership differs")
        expected_names = {"cache_manifest.json"} | {f"condensed/{mid}.json" for mid in entries}
        require(set(members) == expected_names, "Cache has unexpected members")
        output.mkdir(parents=True, exist_ok=True)
        for mid, structure in materials.items():
            entry = entries[mid]
            require(
                entry["input_structure_sha256"] == input_structure_hash(structure),
                f"Cache input structure differs: {mid}",
            )
            raw = archive.read(f"condensed/{mid}.json")
            import hashlib

            require(
                len(raw) == entry["size_bytes"]
                and hashlib.sha256(raw).hexdigest() == entry["sha256"],
                f"Cache descriptor differs: {mid}",
            )
            (output / f"{mid}.json").write_bytes(raw)
    return len(materials)


def _timeout(_signum, _frame):
    raise TimeoutError("Per-material condensation timeout")


def _worker_init():
    global _condenser
    _condenser = _make_condenser()
    signal.signal(signal.SIGALRM, _timeout)


def _describe_one(job):
    from contextlib import redirect_stderr, redirect_stdout

    mid, structure, output, seconds = job
    path = Path(output)
    started = time.monotonic()
    with (path.parent / "logs" / f"{mid}.log").open("a") as log:
        with redirect_stdout(log), redirect_stderr(log):
            signal.alarm(seconds)
            try:
                condense_materials(
                    [(mid, structure)], path, condenser=_condenser, continue_on_error=False
                )
                result = {
                    "material_id": mid,
                    "status": "success",
                    "sha256": digest(path / f"{mid}.json"),
                }
            except Exception as exc:
                result = {"material_id": mid, "status": "failed", "error": str(exc)}
            finally:
                signal.alarm(0)
    result["seconds"] = time.monotonic() - started
    return result


def describe_materials(materials: dict, output: Path, workers: int) -> None:
    """Bounded, isolated robocrys jobs; failures get one longer retry."""
    require(hasattr(signal, "SIGALRM"), "Fresh condensation requires Linux/WSL")
    output.mkdir(parents=True)
    (output.parent / "logs").mkdir()
    pending = materials
    for timeout in (FIRST_TIMEOUT_SECONDS, RETRY_TIMEOUT_SECONDS):
        jobs = [(mid, structure, str(output), timeout) for mid, structure in pending.items()]
        failed = {}
        with (output.parent / "attempts.jsonl").open("a") as log:
            with mp.get_context("spawn").Pool(workers, initializer=_worker_init) as pool:
                for index, record in enumerate(pool.imap_unordered(_describe_one, jobs), 1):
                    log.write(json.dumps(record) + "\n")
                    log.flush()
                    if record["status"] != "success":
                        failed[record["material_id"]] = materials[record["material_id"]]
                    if index % 50 == 0 or index == len(jobs):
                        print(f"Condense {index}/{len(jobs)}, failed={len(failed)}", flush=True)
        pending = failed
        if not pending:
            return
    raise ValueError(f"Descriptors still failed: {sorted(pending)}")


def primary_fields(value: dict) -> dict:
    value = copy.deepcopy(value)
    value.pop("@version", None)
    for key in DERIVED_LATTICE_FIELDS:
        value["lattice"].pop(key, None)
    for site in value["sites"]:
        site.pop("xyz", None)
    return value


def geometry_agrees(local: dict, remote: dict) -> str:
    """Establish correspondence without rewriting either formal task identity."""
    if primary_fields(local) == primary_fields(remote):
        return "primary_fields_equal"
    from pymatgen.analysis.structure_matcher import StructureMatcher
    from pymatgen.core import DummySpecies, Structure

    left, right = Structure.from_dict(local), Structure.from_dict(remote)
    require(
        left.charge == right.charge and left.properties == right.properties,
        "Structure charge/properties differ",
    )
    matcher = StructureMatcher(
        primitive_cell=False,
        scale=False,
        ltol=GEOMETRY_LENGTH_TOL,
        stol=GEOMETRY_SITE_TOL,
        angle_tol=GEOMETRY_ANGLE_TOL,
    )
    # A species-only matcher can choose a symmetry-equivalent permutation that
    # exchanges sites with different magnetic moments. Encode original site
    # attributes as temporary matching classes, without changing either input.
    classes = []

    def labeled_copy(structure):
        codes = []
        for site in structure:
            key = (site.species.as_dict(), site.properties, site.label)
            if key not in classes:
                classes.append(key)
            codes.append(classes.index(key))
        return (
            Structure(
                structure.lattice,
                [DummySpecies(f"Xx{code}") for code in codes],
                structure.frac_coords,
            ),
            Counter(codes),
        )

    matching_left, left_classes = labeled_copy(left)
    matching_right, right_classes = labeled_copy(right)
    require(left_classes == right_classes, "Mapped site attributes differ")
    transformation = matcher.get_transformation(matching_left, matching_right)
    require(transformation is not None, "Periodic geometry differs")
    mapping = transformation[2]
    require(
        len(left) == len(right) == len(mapping) and set(mapping) == set(range(len(right))),
        "Site correspondence is not a bijection",
    )
    # Do not use generated supercell labels: pymatgen adds suffixes to repeats
    # even for a unimodular basis change. Verify the originals via the mapping.
    require(
        all(
            a.species == right[mapping[index]].species
            and a.properties == right[mapping[index]].properties
            and a.label == right[mapping[index]].label
            for index, a in enumerate(left)
        ),
        "Mapped site attributes differ",
    )
    return "strict_periodic_match_allows_orthogonal_reflection"


def group_key(group: dict) -> tuple:
    return tuple(
        sorted(
            (mid, tuple(sorted(a)), x)
            for mid, a, x in zip(
                group["mp_ids"], group["A_elements"], group["X_element"], strict=True
            )
        )
    )


def pair_evidence(frame: pd.DataFrame, groups: list[dict]) -> Counter:
    return Counter(
        (group_key(groups[int(row.source_group_index)]), tuple(sorted((row.mp_id_a, row.mp_id_b))))
        for row in frame.itertuples()
    )


def pair_new_groups(output: Path, bundle: Path, tasks: pd.DataFrame) -> dict:
    replay = output / "06_mbj_replay"
    replay_summary = replay_bundle(bundle, replay)
    remote_tasks = pd.read_csv(bundle / "snapshot/all_gap_tasks.csv")
    require(set(tasks.material_id) == set(remote_tasks.material_id), "Final material IDs differ")
    require(tasks.material_id.is_unique, "Local task materials are duplicated")
    index = pd.read_csv(bundle / "structure_index.csv").set_index("material_id")
    remote_by_id = remote_tasks.set_index("material_id")
    mapping = []
    for row in tasks.itertuples():
        remote_row = remote_by_id.loc[row.material_id]
        require(row.branch == remote_row.branch, "Branch assignment differs")
        remote_path = (bundle / index.loc[row.material_id].json_path).resolve()
        require(remote_path.is_relative_to(bundle), "Unsafe remote structure path")
        status = geometry_agrees(
            json.loads(Path(row.structure_json_path).read_text()),
            json.loads(remote_path.read_text()),
        )
        mapping.append(
            {
                "material_id": row.material_id,
                "local_pending_task_id": row.task_id,
                "mbj_task_id": remote_row.task_id,
                "local_structure_sha256": row.structure_sha256,
                "mbj_structure_sha256": remote_row.structure_sha256,
                "geometry_check": status,
            }
        )
    destination = output / "07_pairs_from_mp"
    destination.mkdir()
    pd.DataFrame(mapping).to_csv(destination / "identity_mapping_audit.csv", index=False)
    frozen = json.loads((bundle / "snapshot/summary.json").read_text())
    successful = pd.read_csv(replay / "successful_gap_results.csv").set_index("material_id")
    frames, reports = [], {}
    for branch in BRANCHES:
        groups_path = output / "04_groups" / f"{branch}.json"
        local_groups = json.loads(groups_path.read_text())
        historical = json.loads((bundle / "snapshot" / branch / "groups.json").read_text())
        dest = destination / branch
        dest.mkdir()
        pairs, report = generate_pairs_from_gap_results(
            groups_path=groups_path,
            gap_paths=[replay / "successful_gap_results.csv"],
            method=frozen["method"],
            thresholds=PairThresholds(**frozen["thresholds"]),
            output=dest / "pairs.csv",
            summary=dest / "coverage.json",
        )
        reference = pd.read_csv(replay / branch / "pairs.csv")
        require(
            pair_evidence(pairs, local_groups) == pair_evidence(reference, historical),
            f"Pair/group evidence differs: {branch}",
        )
        for row in pairs.itertuples():
            for suffix in ("a", "b"):
                require(
                    abs(
                        getattr(row, f"gap_{suffix}")
                        - successful.loc[getattr(row, f"mp_id_{suffix}")].band_gap
                    )
                    < GAP_TOLERANCE_EV,
                    "Pair gap differs",
                )
        pairs["branch"] = branch
        frames.append(pairs)
        reports[branch] = report["pair_count"]
    combined = pd.concat(frames, ignore_index=True)
    combined["pair_key"] = combined.apply(
        lambda row: "|".join(sorted([row.mp_id_a, row.mp_id_b])), axis=1
    )
    unique = combined.drop_duplicates("pair_key")
    ids = set(unique.mp_id_a) | set(unique.mp_id_b)
    require(len(unique) == EXPECTED_PAIRS and len(ids) == EXPECTED_ENDPOINTS, "Final counts differ")
    combined.to_csv(destination / "pairs_all_evidence.csv", index=False)
    unique.to_csv(destination / "pairs_unique.csv", index=False)
    backfill = pd.read_csv(replay / "endmember_gap_backfill.csv")
    backfill[backfill.material_id.isin(ids)].to_csv(
        destination / "candidate_materials.csv", index=False
    )
    return {
        "pair_counts": reports,
        "unique_pairs": len(unique),
        "unique_endpoints": len(ids),
        "mbj_status_counts": replay_summary["status_counts"],
        "geometry_checks": dict(Counter(row["geometry_check"] for row in mapping)),
        "normalized_pair_and_group_evidence_equal": True,
        "formal_identities_preserved": True,
        "pending_tasks_modified": False,
    }


def reproduce_mp_zip(
    mp_zip: Path,
    mbj_bundle: Path,
    output: Path,
    *,
    workers: int = 4,
    descriptor_cache: Path | None = None,
) -> dict:
    """Run the dated protocol; default descriptors are freshly calculated."""
    require(workers >= 1, "workers must be positive")
    mp_zip, bundle, output = (
        Path(mp_zip).resolve(),
        Path(mbj_bundle).resolve(),
        Path(output).resolve(),
    )
    require(not output.exists(), "Use a new output directory; existing results are preserved")
    require(not output.is_relative_to(bundle), "Output must be outside the immutable mBJ bundle")
    require((bundle / "FILE_MANIFEST.json").is_file(), "Extract the mBJ result bundle first")
    # Fail before creating an incomplete run if the reader/descriptor dependency is absent.
    importlib.metadata.version("mp_offline")
    importlib.metadata.version("robocrys")
    require(digest(mp_zip) == MP_ZIP_SHA, "This dated profile requires the specified mp.zip SHA")
    output.mkdir(parents=True)
    stage = "database"

    def state(name: str) -> None:
        nonlocal stage
        stage = name
        save(output / "pipeline_state.json", {"state": "running", "stage": stage})
        print(f"STAGE {stage}", flush=True)

    try:
        state("database")
        database = extract_database(mp_zip, output / "00_input/mp/default.db")
        dataset_path = output / "01_dataset/mp.df"
        dataset_path.parent.mkdir()
        df = load_mp_dataset_offline(
            output=dataset_path, max_e_hull=PREFILTER_HULL, offline_db=database
        )
        require(len(df) == EXPECTED_DATASET and df.index.is_unique, "Prefilter membership differs")
        state("composition")
        (output / "02_composition").mkdir()
        candidates, selected = {}, set()
        for branch, (nelems, expected, _tasks, _limit) in BRANCHES.items():
            frame, report = screen_composition_candidates(
                df,
                nelems=nelems,
                max_bandgap=COMPOSITION_GAP,
                max_e_hull=COMPOSITION_HULL,
                excluded_elements=DEFAULT_EXCLUDED_ELEMENTS,
                min_group_size=2,
                min_x_elements=2,
            )
            require(
                frame.material_id.nunique() == expected, f"Composition candidates differ: {branch}"
            )
            frame.to_csv(output / "02_composition" / f"{branch}.csv", index=False)
            save(output / "02_composition" / f"{branch}_summary.json", report)
            candidates[branch] = frame[~frame.material_id.isin(EXCLUDED_IDS)].copy()
            selected.update(frame.material_id)
        require(
            len(selected) == EXPECTED_CANDIDATES and EXCLUDED_IDS <= selected,
            "Combined candidate/exclusion membership differs",
        )
        materials = {mid: df.loc[mid].structure for mid in sorted(selected - EXCLUDED_IDS)}
        state("descriptors")
        condensed = output / "03_condensation/condensed"
        if descriptor_cache is None:
            describe_materials(materials, condensed, workers)
        else:
            load_descriptor_cache(Path(descriptor_cache), materials, condensed)
        valid = validate_archive(condensed, index_path=condensed.parent / "validation.csv")
        require(
            len(valid) == EXPECTED_DESCRIPTORS
            and valid.status.eq("valid").all()
            and set(valid.material_id) == set(materials),
            "Descriptor validation failed",
        )
        save(
            condensed.parent / "source.json",
            {
                "mode": "fresh" if descriptor_cache is None else "explicit_verified_cache",
                "database_sha256": DATABASE_SHA,
                "cache_sha256": digest(descriptor_cache) if descriptor_cache else None,
                "historical_exclusions": sorted(EXCLUDED_IDS),
                "workers": workers,
            },
        )
        state("groups_and_tasks")
        (output / "04_groups").mkdir()
        frames, group_reports = [], {}
        for branch, (_nelems, _expected, expected_tasks, limit) in BRANCHES.items():
            groups, report = match_structure_candidates(candidates[branch], [condensed])
            require(
                not report["missing_descriptions"] and not report["invalid_descriptions"],
                f"Missing/invalid descriptors: {branch}",
            )
            path = output / "04_groups" / f"{branch}.json"
            dump_group_df(groups, path)
            save(output / "04_groups" / f"{branch}_summary.json", report)
            group_reports[branch] = {
                "groups": len(groups),
                "unique_members": len({mid for group in groups for mid in group.mp_ids}),
            }
            dest = output / "05_pending_tasks" / branch
            dest.mkdir(parents=True)
            tasks = export_gap_candidates(
                path,
                dataset_path,
                dest / "gap_tasks.csv",
                method=PENDING_METHOD,
                max_natoms=limit,
                structure_dir=dest / "structures",
                structure_formats=("json",),
            )
            require(
                len(tasks) == expected_tasks and tasks.material_id.is_unique,
                f"Exported task count differs: {branch}",
            )
            tasks.insert(0, "branch", branch)
            frames.append(tasks)
        local_tasks = pd.concat(frames, ignore_index=True)
        local_tasks.to_csv(output / "05_pending_tasks/all_gap_tasks.csv", index=False)
        # Release the large original DataFrame before mBJ/structure verification.
        del df, materials
        state("mbj_validation_and_new_group_pairing")
        result = pair_new_groups(output, bundle, local_tasks)
        result.update(
            {
                "passed": True,
                "profile": PROFILE,
                "mp_zip_sha256": MP_ZIP_SHA,
                "database_sha256": DATABASE_SHA,
                "dataset_rows": EXPECTED_DATASET,
                "composition_materials": EXPECTED_CANDIDATES,
                "descriptors": EXPECTED_DESCRIPTORS,
                "groups": group_reports,
                "tasks": len(local_tasks),
                "descriptor_cache_used": descriptor_cache is not None,
                "fresh_descriptor_count": 0 if descriptor_cache else EXPECTED_DESCRIPTORS,
                "groups_recomputed_from_mp": True,
                "pbe_fallback": False,
            }
        )
        save(output / "summary.json", result)
        save(output / "pipeline_state.json", {"state": "finished", "stage": "complete"})
        return result
    except Exception as exc:
        save(output / "pipeline_state.json", {"state": "failed", "stage": stage, "error": str(exc)})
        raise
