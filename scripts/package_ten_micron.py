"""Package verified files from the 116-pair demo; omit DB and fast-stage outputs."""

import argparse
import csv
import hashlib
import io
import json
import os
import re
from pathlib import Path, PureWindowsPath
from zipfile import ZIP_DEFLATED, ZipFile

from ssscreen.ten_micron import CANDIDATES, GROUPS, PAIRS, PROFILE, digest, pair_signature


def source_path(raw):
    """Resolve a recorded structure or plot path on the packaging host."""
    if os.name == "nt" and raw.startswith("/mnt/"):
        return Path(raw[5].upper() + ":" + raw[6:])
    win = PureWindowsPath(raw)
    if os.name != "nt" and win.drive and win.is_absolute():
        return Path("/mnt", win.drive[0].lower(), *win.parts[1:])
    return Path(raw)


def build(source, plots, output):
    folders = {p.name[:2]: p for p in source.iterdir() if p.is_dir() and p.name[:2].isdigit()}
    mapping = {
        "03": ("03_condensed/local", "独立复现/condensed"),
        "07": ("07_sqs/structures", "structures"),
        "08": ("08_relax/structures", "structures"),
    }
    files = {}
    for stage, (destination, relative) in mapping.items():
        folder = folders[stage] / relative
        for p in folder.rglob("*.json"):
            files[destination + "/" + p.relative_to(folder).as_posix()] = p
    for stage, dest, names in [
        ("05", "05_gap", ["results_normalized.csv", "validation.json"]),
        ("07", "07_sqs", ["sqs_manifest.jsonl", "pair_index_mapping.csv"]),
        ("08", "08_relax", ["relaxation_results.jsonl"]),
        ("10", "10_phonon", ["phonon_summary.csv"]),
        ("11", "11_phase", ["phase_stability.csv"]),
        ("13", "13_geometry", ["candidate_evaluation.csv", "substrate_top_matches.csv"]),
    ]:
        for name in names:
            files[dest + "/" + name] = folders[stage] / name
    for p in plots.iterdir():
        if p.is_file():
            files["11_phase/plots/" + p.name] = p
    with (folders["10"] / "phonon_summary.csv").open(encoding="utf-8-sig") as stream:
        phonons = list(csv.DictReader(stream))
    for row in phonons:
        if row["plot_path"]:
            plot = source_path(row["plot_path"])
            files["10_phonon/plots/" + plot.name] = plot
            row["plot_path"] = "10_phonon/plots/" + plot.name
        if row["reference_structure_path"]:
            row["reference_structure_path"] = (
                "08_relax/structures/" + Path(row["reference_structure_path"]).name
            )
    phase = json.loads((plots / "phase_plot_index.json").read_text(encoding="utf-8"))
    directory = source_path(phase["competing_structures"])
    with (plots / "hull_entries.csv").open(encoding="utf-8") as stream:
        for entry in csv.DictReader(stream):
            if entry["phase_role"] == "competing_phase":
                name = entry["phase_structure_id"] + ".json"
                files["11_phase/structures/" + name] = Path(directory) / name
    phase.update(
        scope_summary="../phase_stability.csv",
        candidate_structures="../../08_relax/structures",
        competing_structures="../structures",
    )
    anchors = {
        CANDIDATES: folders["02"] / "composition_candidates.csv",
        GROUPS: folders["04"] / "部分结果/groups.json",
        PAIRS: folders["06"] / "final_pairs.csv",
    }
    manifest = {
        "profile": "10um-116-v1",
        "database_sha256": json.loads(
            (folders["01"] / "mp.df.provenance.json").read_text(encoding="utf-8")
        )["database"]["sha256"],
        "anchors": {k: pair_signature(v) if k == PAIRS else digest(v) for k, v in anchors.items()},
        "files": {},
    }
    with ZipFile(output, "x", compression=ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            data = path.read_bytes()
            if name.endswith(".jsonl"):
                text = data.decode("utf-8")
                for key, dest in (("07", "07_sqs"), ("08", "08_relax")):
                    # Paths to bundled structures are relative to the new workspace.
                    text = re.sub(
                        r'"/[^"\n]+/' + folders[key].name + r"/structures/",
                        '"' + dest + "/structures/",
                        text,
                    )
                data = text.encode()
            if name == "11_phase/plots/phase_plot_index.json":
                data = json.dumps(phase, ensure_ascii=False, indent=2).encode()
            if name == "10_phonon/phonon_summary.csv":
                table = io.StringIO()
                writer = csv.DictWriter(table, fieldnames=list(phonons[0]))
                writer.writeheader()
                writer.writerows(phonons)
                data = table.getvalue().encode()
            archive.writestr(name, data)
            manifest["files"][name] = hashlib.sha256(data).hexdigest()
        archive.writestr(PROFILE, json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("source", "plots", "output"):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    build(args.source, args.plots, args.output)
