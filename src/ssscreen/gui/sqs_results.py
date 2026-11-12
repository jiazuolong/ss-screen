"""Read-only identity checks for the Stage 07 -> 08 GUI handoff."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def resolve_path(root: Path, value: str) -> Path:
    if os.name == "nt" and value.startswith("/mnt/") and len(value) > 7 and value[6] == "/":
        value = value[5].upper() + ":/" + value[7:]
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pair_count(path: Path) -> int:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not {"mp_id_a", "mp_id_b", "comp_a", "comp_b"} <= set(reader.fieldnames or []):
                return 0
            rows = list(reader)
            if any(
                not row.get(key)
                for row in rows
                for key in ("mp_id_a", "mp_id_b", "comp_a", "comp_b")
            ):
                return 0
            return len(rows)
    except (OSError, ValueError, csv.Error):
        return 0


def sqs_result_status(
    root: Path,
    pairs: str,
    dataset: str,
    output_dir: str,
    manifest: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Check inputs, generation settings, manifest and every written structure."""
    status: dict[str, Any] = {"ready": False, "written": 0, "skipped": 0}
    try:
        manifest_path = resolve_path(root, manifest)
        if not manifest_path.is_file():
            return {**status, "message": "尚未生成本次SQS结构。"}
        records = [
            json.loads(line)
            for line in manifest_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not records or any(
            not isinstance(row, dict) or row.get("status") not in {"written", "skipped"}
            for row in records
        ):
            raise ValueError("SQS清单为空或记录格式不完整。")
        status.update(
            written=sum(row["status"] == "written" for row in records),
            skipped=sum(row["status"] == "skipped" for row in records),
        )
        provenance_path = manifest_path.with_suffix(".provenance.json")
        if not provenance_path.is_file():
            raise ValueError("已有旧版清单；请在新的输出位置生成本次SQS后进入08。")
        report = json.loads(provenance_path.read_text(encoding="utf-8"))
        expected = {
            "pairs": file_sha256(resolve_path(root, pairs)),
            "dataset": file_sha256(resolve_path(root, dataset)),
        }
        if (
            not isinstance(report, dict)
            or report.get("input_sha256") != expected
            or report.get("parameters") != parameters
        ):
            raise ValueError("输入或生成参数与已有结果不一致，请生成本次SQS。")
        if report.get("manifest_sha256") != file_sha256(manifest_path):
            raise ValueError("SQS清单已改变，请检查或重新生成。")
        hashes: dict[Path, str] = {}
        destination = resolve_path(root, output_dir).resolve()
        for row in records:
            if row["status"] != "written":
                continue
            for prefix in ("", "endpoint_a_", "endpoint_b_"):
                value = row[prefix + "structure_path"]
                path = resolve_path(root, value)
                if not Path(value).is_absolute() and (manifest_path.parent / value).is_file():
                    path = manifest_path.parent / value
                path = path.resolve()
                if not path.is_relative_to(destination):
                    raise ValueError("清单中的结构不属于当前输出文件夹。")
                # Repeated endpoints may share a file, but each recorded hash must match.
                if path not in hashes:
                    hashes[path] = file_sha256(path)
                digest = hashes[path]
                if digest != row[prefix + "structure_sha256"]:
                    raise ValueError("SQS或端元结构文件已改变，请检查或重新生成。")
        status["ready"] = status["written"] > 0
        status["message"] = (
            "可进入08进行MACE弛豫。"
            if status["ready"]
            else "没有成功生成的结构；请检查跳过原因并调整参数。"
        )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        status["message"] = str(exc)
    return status
