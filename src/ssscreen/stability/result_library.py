"""Match historical summaries to the exact input and relaxed structures of a project."""

import csv
import hashlib
import json
import math
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile

from .recommendation import REQUIRED_PHASE_COLUMNS, REQUIRED_PHONON_COLUMNS
from .thermodynamics import _energy_signature, _is_usable

COLUMNS = {"phonon": REQUIRED_PHONON_COLUMNS, "phase": REQUIRED_PHASE_COLUMNS}
HASH_FIELDS = ("library_input_sha256", "library_relaxed_sha256", "library_reference_sha256")
IDENTITY = (*HASH_FIELDS, "mp_id_a", "mp_id_b", "actual_fraction_b")
TOLERANCE_EV = 1e-8


def sha256(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def identity(record):
    signature, _ = _energy_signature(record)
    hashes = (record["input_structure"]["sha256"], record["output_structure"]["sha256"], signature)
    if not all(re.fullmatch("[0-9a-f]{64}", str(h)) for h in hashes):
        raise ValueError("弛豫记录缺少完整结构或计算条件哈希")
    return dict(
        zip(HASH_FIELDS, hashes, strict=True),
        mp_id_a=record.get("mp_id_a", ""),
        mp_id_b=record.get("mp_id_b", ""),
        actual_fraction_b=record.get("actual_fraction_b", ""),
    )


def key(row):
    return tuple(row[f] for f in IDENTITY[:-1]) + (float(row["actual_fraction_b"]),)


def _csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames or [], list(reader)


def historical_rows(kind, summary, relaxation, batch):
    """Bind a historical batch to the actual relaxation manifest used for that batch."""
    records = {}
    for line in Path(relaxation).read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            if record["structure_id"] in records:
                raise ValueError("历史弛豫清单包含重复结构")
            records[record["structure_id"]] = record
    fields, rows = _csv(summary)
    if set(COLUMNS[kind]) - set(fields):
        raise ValueError("历史汇总类型或列不符")
    source_sha = sha256(summary)
    for row in rows:
        record = records[row["structure_id"]]
        linked = identity(record)
        for field in ("mp_id_a", "mp_id_b"):
            if row.get(field) and row[field] != linked[field]:
                raise ValueError(f"历史端元不一致：{row['structure_id']}")
        for column, backend_field in (("model_sha256", "model_sha256"), ("dtype", "dtype")):
            if row.get(column) and row[column] != record["backend"][backend_field]:
                raise ValueError(f"历史计算方法不一致：{row['structure_id']}")
        if (
            row.get("energy_reference_sha256")
            and row["energy_reference_sha256"] != linked["library_reference_sha256"]
        ):
            raise ValueError("历史凸包能量基准不一致")
        if row.get("energy_per_atom_eV") and not math.isclose(
            float(row["energy_per_atom_eV"]),
            record["energy_per_atom_eV"],
            rel_tol=0,
            abs_tol=TOLERANCE_EV,
        ):
            raise ValueError("历史凸包候选能量不一致")
        yield {
            **row,
            **linked,
            "structure_role": record["structure_role"],
            "library_kind": kind,
            "library_batch": batch,
            "library_summary_sha256": source_sha,
        }


def match_library(kind, library, relaxation, pairs, output, database=None):
    fields, history = _csv(library)
    required = (
        set(COLUMNS[kind]) | set(IDENTITY) | {"library_kind", "library_batch", "structure_role"}
    )
    if not history or required - set(fields) or any(r["library_kind"] != kind for r in history):
        raise ValueError("请选择对应步骤的全量历史结果库 CSV")
    db_sha = sha256(database) if database is not None else None
    if kind == "phase" and not db_sha:
        raise ValueError("凸包匹配需要核对本批使用的离线数据库")
    by_key = defaultdict(list)
    for row in history:
        if row["structure_role"] == "sqs":
            by_key[key(row)].append(row)
    _, endpoints = _csv(pairs)
    current = []
    seen = set()
    for line in Path(relaxation).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record["structure_role"] != "sqs":
            continue
        sid = record["structure_id"]
        index = int(record["pair_index"])
        if (
            sid in seen
            or not 0 <= index < len(endpoints)
            or any(record[f] != endpoints[index][f] for f in ("mp_id_a", "mp_id_b"))
        ):
            raise ValueError("08 记录重复或与当前 06 端元对不一致")
        seen.add(sid)
        found = []
        if _is_usable(record):
            linked = identity(record)
            for field in ("input_structure", "output_structure"):
                path = Path(record[field]["path"])
                if sha256(path) != record[field]["sha256"]:
                    raise ValueError(f"当前结构文件已改变：{sid}")
            found = by_key.get(key(linked), [])
            if kind == "phase":
                found = [
                    r
                    for r in found
                    if r.get("mp_database_sha256") == db_sha
                    and r.get("energy_per_atom_eV")
                    and math.isclose(
                        float(r["energy_per_atom_eV"]),
                        float(record["energy_per_atom_eV"]),
                        abs_tol=TOLERANCE_EV,
                        rel_tol=0,
                    )
                ]
        if len(found) == 1:
            row = dict(
                found[0],
                library_structure_id=found[0]["structure_id"],
                library_pair_index=found[0]["pair_index"],
                library_match="matched",
            )
        else:
            row = {
                "status": "missing",
                "library_match": "ambiguous" if found else "missing",
                "usable_for_screening": "False",
                "dynamical_status": "missing",
            }
        row.update(
            structure_id=sid,
            pair_index=index,
            structure_role="sqs",
            mp_id_a=record["mp_id_a"],
            mp_id_b=record["mp_id_b"],
            actual_fraction_b=record["actual_fraction_b"],
        )
        if "current_pair_index" in fields:
            row["current_pair_index"] = index
        current.append(row)
    if not current:
        raise ValueError("08 没有当前合金结构记录")
    target = Path(output)
    if target.resolve() in {Path(p).resolve() for p in (library, relaxation, pairs, database) if p}:
        raise ValueError("输出与输入重叠")
    target.parent.mkdir(parents=True, exist_ok=True)
    columns = list(
        dict.fromkeys([*fields, "library_structure_id", "library_pair_index", "library_match"])
    )
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=target.parent, delete=False
    ) as stream:
        temp = Path(stream.name)
        try:
            writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(current)
        except BaseException:
            stream.close()
            temp.unlink(missing_ok=True)
            raise
    backup = None
    try:
        if target.exists() and sha256(target) != sha256(temp):
            backup = target.with_name(f"{target.stem}.before-library-{sha256(target)[:16]}.csv")
            if not backup.exists():
                shutil.copy2(target, backup)
            if sha256(backup) != sha256(target):
                raise ValueError("无法验证旧结果备份")
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    return current, backup
