"""Fixed 10 µm replay profile. Scientific calculations use the production commands."""

import csv
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

PROFILE = "ten_micron.json"
STATE = ".ten_micron_progress.json"
DIRS = (
    "01_dataset",
    "02_composition",
    "03_condensed",
    "04_groups",
    "05_gap",
    "06_pair",
    "07_sqs",
    "08_relax",
    "09_mixing",
    "10_phonon",
    "11_phase",
    "12_recommend",
    "13_geometry",
)
CACHED = {3, 5, 7, 8, 10, 11}
DATABASE = "01_dataset/default.db"
CANDIDATES = "02_composition/composition_candidates.csv"
GROUPS = "04_groups/groups.json"
GAPS = "05_gap/results_normalized.csv"
PAIRS = "06_pair/final_pairs.csv"
RELAX = "08_relax/relaxation_results.jsonl"
MIXING = "09_mixing/mixing_enthalpy.csv"
PHONONS = "10_phonon/phonon_summary.csv"
HULL = "11_phase/phase_stability.csv"
RECOMMENDATIONS = "12_recommend/recommendations.csv"


def digest(path):
    with Path(path).open("rb") as stream:
        return (
            hashlib.file_digest(stream, "sha256").hexdigest()
            if hasattr(hashlib, "file_digest")
            else _hash_stream(stream)
        )


def _hash_stream(stream):
    sha = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        sha.update(block)
    return sha.hexdigest()


def pair_signature(path):
    """Preserve ordered pairs and group indices across relocated project roots."""
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        groups = json.loads(row["source_groups"])
        for group in groups:
            if Path(group["file"]).name != "groups.json":
                raise ValueError("端元配对来源与本批分组不符")
            group["file"] = GROUPS
        row["source_groups"] = groups
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def completed(root):
    state = root / STATE
    return json.loads(state.read_text(encoding="utf-8"))["completed"] if state.exists() else 0


def create_workspace(package, target):
    """Publish an initialized workspace only after all payloads pass their checks."""
    target = Path(target).resolve()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ValueError("请选择一个新的或空的工程目录")
    with TemporaryDirectory(dir=target.parent) as temporary, ZipFile(package) as archive:
        staging = Path(temporary) / "workspace"
        staging.mkdir()
        manifest = json.loads(archive.read(PROFILE))
        if manifest.get("profile") != "10um-116-v1":
            raise ValueError("不支持的 10 µm 模板")
        for folder in DIRS:
            (staging / folder).mkdir()
        for name, expected in manifest["files"].items():
            out = (staging / name).resolve()
            if not out.is_relative_to(staging) or Path(name).parts[0] not in DIRS:
                raise ValueError("模板文件路径无效")
            out.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as src, out.open("xb") as dest:
                shutil.copyfileobj(src, dest)
            if digest(out) != expected:
                raise ValueError(f"模板文件校验失败：{name}")
        (staging / PROFILE).write_bytes(archive.read(PROFILE))
        if target.exists():
            target.rmdir()
        staging.rename(target)


def run_step(root, stage, database=None):
    import fcntl

    from .cli.app import cli

    root = Path(root).resolve()
    profile = json.loads((root / PROFILE).read_text(encoding="utf-8"))
    os.chdir(root)
    with (root / ".ten_micron.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if stage != completed(root) + 1 or not 1 <= stage <= len(DIRS):
            raise ValueError("请按当前工作区的步骤顺序运行")
        state_path = root / STATE
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        generated = state.get("generated", {})

        def verify(name, expected):
            actual = pair_signature(name) if name == PAIRS else digest(name)
            if actual != expected:
                raise ValueError(f"文件与 10 µm 参考批次不一致：{name}")

        for name in {2: ("01_dataset/mp.df",), 12: (MIXING,), 13: (RECOMMENDATIONS,)}.get(
            stage, ()
        ):
            if name in generated:
                verify(name, generated[name])

        if stage == 1:
            source = Path(database or DATABASE).resolve()
            verify(source, profile["database_sha256"])
            if source != Path(DATABASE).resolve():
                temp = Path(DATABASE).with_suffix(".tmp")
                shutil.copyfile(source, temp)
                verify(temp, profile["database_sha256"])
                temp.replace(DATABASE)
        for name, expected in profile["files"].items():
            if name.startswith(DIRS[stage - 1] + "/") or (
                stage in (4, 6, 9, 12) and name in (GAPS, RELAX, PHONONS, HULL)
            ):
                verify(name, expected)
        commands = {
            1: [
                "dataset",
                "mp",
                "--backend",
                "offline",
                "--offline-db",
                DATABASE,
                "--max-e-hull",
                "0.01",
                "--output",
                "01_dataset/mp.df",
                "--provenance",
                "01_dataset/mp.df.provenance.json",
            ],
            2: [
                "composition-screen",
                "--df",
                "01_dataset/mp.df",
                "--nelems",
                "2",
                "--nelems",
                "3",
                "--max-bandgap",
                "1",
                "--max-e-hull",
                "0",
                "--min-group-size",
                "2",
                "--min-x-elements",
                "2",
                "--output",
                CANDIDATES,
                "--summary",
                "02_composition/composition_summary.json",
                "--structures-output",
                "02_composition/candidates.df",
            ],
            4: [
                "structure-match",
                "--candidates",
                CANDIDATES,
                "--condensed-dir",
                "03_condensed/local",
                "--min-x-elements",
                "2",
                "--output",
                GROUPS,
                "--summary",
                "04_groups/structure_match_summary.json",
            ],
            6: [
                "pair-wavelength",
                "--groups",
                GROUPS,
                "--gap-results",
                GAPS,
                "--target-wavelength-um",
                "10",
                "--allow-mixed-methods",
                "--min-gap-exclusive",
                "0",
                "--max-gap-exclusive",
                "0.4",
                "--output",
                PAIRS,
                "--summary",
                "06_pair/summary.json",
            ],
            9: [
                "stability",
                "mixing-enthalpy",
                "--pairs",
                PAIRS,
                "--relax-results",
                RELAX,
                "--output",
                MIXING,
                "--summary",
                "09_mixing/summary.json",
            ],
            12: [
                "recommend",
                "--pairs",
                PAIRS,
                "--gap-results",
                GAPS,
                "--mixing-enthalpy",
                MIXING,
                "--phonons",
                PHONONS,
                "--phase-stability",
                HULL,
                "--promising-max-mixing",
                "25",
                "--low-priority-mixing",
                "50",
                "--promising-max-hull",
                "0.025",
                "--low-priority-hull",
                "0.1",
                "--gap-consistency-tolerance",
                "1e-6",
                "--output",
                RECOMMENDATIONS,
                "--report",
                "12_recommend/recommendation_report.md",
                "--summary",
                "12_recommend/recommendation_summary.json",
            ],
        }
        # Freeze the upstream identities that determine the applicability of the cache.
        for name, expected in profile["anchors"].items():
            if int(name[:2]) < stage:
                verify(name, expected)
        if stage in commands:
            cli.main(args=commands[stage], standalone_mode=False)
        if stage == 13:
            from .detector import (
                assess_rows,
                export_rows,
                format_assessment_rows,
                index_geometry,
                read_csv,
            )

            rows = assess_rows(
                read_csv(Path(RECOMMENDATIONS)),
                10,
                index_geometry(read_csv(Path("13_geometry/candidate_evaluation.csv"))),
            )
            matches = {}
            for match in read_csv(Path("13_geometry/substrate_top_matches.csv")):
                matches.setdefault(match["candidate_id"], []).append(match)
            format_assessment_rows(rows, matches)
            export_rows(Path("13_geometry/candidate_assessment.csv"), rows)
        for name, expected in profile["anchors"].items():
            if int(name[:2]) == stage:
                verify(name, expected)
        pending = root / (STATE + ".tmp")
        for name in {1: ("01_dataset/mp.df",), 9: (MIXING,), 12: (RECOMMENDATIONS,)}.get(stage, ()):
            generated[name] = digest(name)
        pending.write_text(
            json.dumps({"completed": stage, "generated": generated}), encoding="utf-8"
        )
        pending.replace(root / STATE)


if __name__ == "__main__":
    run_step(Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None)
