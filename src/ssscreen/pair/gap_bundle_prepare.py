"""Standalone helper copied into a gap ZIP; requires only Python's standard library."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def canonical(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def prepare(root: Path, metadata_path: Path) -> Path:
    """Bind the pending structures to the actual calculation method without overwriting them."""
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    method = str(metadata.get("method", "")).strip()
    manifest = json.loads((root / "bundle_manifest.json").read_text(encoding="utf-8"))
    if not method or method == manifest["pending_method"]:
        raise ValueError("请在方法文件中填写实际 method 标识后再准备计算。")
    for name in ("calculator", "functional"):
        if not str(metadata.get(name, "")).strip():
            raise ValueError(f"方法文件尚未填写 {name}")
    for name, expected in manifest["files"].items():
        if name == "method_metadata.json":  # This template is intentionally editable.
            continue
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"压缩包文件发生变化：{name}")
    settings_hash = canonical(
        {key: value for key, value in metadata.items() if key not in {"settings_sha256", "notes"}}
    )
    with (root / "tasks.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        task_fields, tasks = list(reader.fieldnames or []), list(reader)
    with (root / "results_template.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        result_fields, results = list(reader.fieldnames or []), list(reader)
    mapping = {}
    for task in tasks:
        old_id = task["task_id"]
        task["method"] = method
        task["task_id"] = (
            "gap-"
            + canonical(
                {
                    "schema_version": 1,
                    "material_id": task["material_id"],
                    "method": method,
                    "structure_sha256": task["structure_sha256"],
                }
            )[:24]
        )
        task["pending_task_id"] = old_id
        task["settings_sha256"] = settings_hash
        # Paths are relative to the extracted bundle root, as in the original task table.
        mapping[old_id] = task["task_id"]
    for result in results:
        result.update(
            task_id=mapping[result["task_id"]], method=method, settings_sha256=settings_hash
        )
    output = root / "prepared"
    output.mkdir(exist_ok=False)
    for name, fields, rows in (
        ("tasks.csv", task_fields + ["pending_task_id", "settings_sha256"], tasks),
        ("results_template.csv", result_fields, results),
    ):
        with (output / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    (output / "method_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, default=Path("method_metadata.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    metadata = args.metadata if args.metadata.is_absolute() else root / args.metadata
    print(f"Prepared actual-method task and result tables: {prepare(root, metadata)}")


if __name__ == "__main__":
    main()
