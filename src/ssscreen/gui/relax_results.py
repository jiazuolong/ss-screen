"""Read existing relaxation evidence before handing it to thermodynamics."""

from __future__ import annotations

import csv
import json
import pickle
from collections import Counter
from pathlib import Path
from typing import Any

from ..stability.thermodynamics import (
    _energy_signature,
    _fraction_b,
    _is_usable,
    _read_jsonl,
    _select_endmember,
)
from .sqs_results import file_sha256, resolve_path


def manifest_rows(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError("SQS清单为空或格式错误。")
    return [row for row in rows if row.get("status") == "written"]


def structure_path(root: Path, manifest: Path, value: str) -> Path:
    path = resolve_path(root, value)
    if not Path(value).is_absolute() and (manifest.parent / value).is_file():
        return manifest.parent / value
    return path


def requires_endpoint_dataset(manifest: Path) -> bool:
    return any(
        not row.get(f"endpoint_{side}_structure_path")
        for row in manifest_rows(manifest)
        for side in ("a", "b")
    )


def relaxation_status(
    root: Path,
    manifest: str,
    pairs: str,
    results: str,
    output_dir: str,
    parameters: dict[str, Any],
    *,
    external: bool = False,
) -> dict[str, Any]:
    """Accept at least one usable SQS/endmember triplet with a shared energy reference.

    The existing thermodynamics selectors remain authoritative for compatibility,
    duplicate endpoints and actual fractions. No model is loaded and no files are written.
    """
    status: dict[str, Any] = {
        "ready": False,
        "success": 0,
        "not_converged": 0,
        "failed": 0,
        "usable_pairs": 0,
        "usable_sqs": 0,
        "evidence_valid": False,
    }
    try:
        result_path = resolve_path(root, results)
        if not result_path.is_file():
            return {**status, "message": "尚无本次弛豫结果。"}
        records = _read_jsonl(result_path)
        counts = Counter(row.get("status") for row in records)
        status.update({key: counts[key] for key in ("success", "not_converged", "failed")})
        manifest_path = resolve_path(root, manifest)
        generated = manifest_rows(manifest_path)
        if not generated:
            raise ValueError("07清单中没有已生成的SQS结构。")
        with resolve_path(root, pairs).open(encoding="utf-8-sig", newline="") as handle:
            pair_rows = list(csv.DictReader(handle))
        hashes: dict[Path, str] = {}

        def digest(path: Path) -> str:
            path = path.resolve()
            if path not in hashes:
                hashes[path] = file_sha256(path)
            return hashes[path]

        sqs_inputs = {}
        endpoint_inputs: dict[str, set[str]] = {}
        legacy_endpoints: set[str] = set()
        dataset = None
        for row in generated:
            index = int(row["pair_index"])
            if (
                index < 0
                or index >= len(pair_rows)
                or any(
                    str(row[f"mp_id_{side}"]) != pair_rows[index][f"mp_id_{side}"]
                    for side in ("a", "b")
                )
            ):
                raise ValueError("07清单与当前06端元对不对应。")
            input_hash = digest(structure_path(root, manifest_path, row["structure_path"]))
            if row.get("structure_sha256", input_hash) != input_hash:
                raise ValueError("07 SQS结构与清单记录不一致。")
            sqs_inputs[(index, float(row["target_fraction_b"]), input_hash)] = row
            for side in ("a", "b"):
                value = row.get(f"endpoint_{side}_structure_path")
                if value:
                    endpoint_hash = digest(structure_path(root, manifest_path, value))
                    if row.get(f"endpoint_{side}_structure_sha256", endpoint_hash) != endpoint_hash:
                        raise ValueError("07端元结构与清单记录不一致。")
                    endpoint_inputs.setdefault(str(row[f"mp_id_{side}"]), set()).add(endpoint_hash)
                else:
                    legacy_endpoints.add(str(row[f"mp_id_{side}"]))

        model_path = resolve_path(root, str(parameters["model_path"]))
        model_hash = digest(model_path) if model_path.is_file() else None
        if model_hash is None and not external:
            raise ValueError("当前模型文件不存在；请选择与结果相同的模型。")
        destination = resolve_path(root, output_dir).resolve()
        endmembers: dict[str, list[dict[str, Any]]] = {}
        sqs_records = []
        for row in records:
            source = row["input_structure"]
            input_hash = digest(resolve_path(root, source["path"]))
            if input_hash != source["sha256"]:
                raise ValueError("弛豫输入结构已改变。")
            role = row["structure_role"]
            if role == "sqs":
                key = (int(row["pair_index"]), float(row["target_fraction_b"]), input_hash)
                generated_row = sqs_inputs.get(key)
                if not generated_row or any(
                    str(row[f"mp_id_{side}"]) != str(generated_row[f"mp_id_{side}"])
                    for side in ("a", "b")
                ):
                    raise ValueError("弛豫结果不属于当前07 SQS批次。")
                sqs_records.append(row)
            elif role == "endmember":
                material = str(row["material_id"])
                if input_hash not in endpoint_inputs.get(material, set()):
                    if material not in legacy_endpoints or not parameters.get("dataset_path"):
                        raise ValueError("弛豫端元与07清单不对应。")
                    # Old manifests use the CLI's dataset fallback. Compare the
                    # complete input structure without loading it for modern batches.
                    import pandas as pd
                    from monty.serialization import loadfn

                    from ..stability.relax import _structure_from_dataset

                    if dataset is None:
                        dataset = pd.read_pickle(
                            resolve_path(root, str(parameters["dataset_path"]))
                        )
                    if loadfn(resolve_path(root, source["path"])) != _structure_from_dataset(
                        dataset, material
                    ):
                        raise ValueError("旧清单的弛豫端元与当前02结构数据不同。")
                    endpoint_inputs.setdefault(material, set()).add(input_hash)
                endmembers.setdefault(material, []).append(row)
            else:
                raise ValueError("当前结果包含非SQS或非端元记录。")
            backend, settings = row["backend"], row["settings"]
            if (
                backend.get("name") != parameters.get("backend", "mace")
                or backend.get("dtype") != parameters["dtype"]
                or (model_hash is not None and backend.get("model_sha256") != model_hash)
                or (
                    parameters.get("model_name")
                    and backend.get("model_name") != parameters["model_name"]
                )
                or settings.get("fmax_ev_per_angstrom") != parameters["fmax"]
                or settings.get("max_steps") != parameters["max_steps"]
                or settings.get("cell_mode")
                != ("full" if parameters["relax_cell"] else "positions")
            ):
                raise ValueError("模型或弛豫条件与已有结果不同，请先运行当前配置。")
            if row.get("status") in {"success", "not_converged"}:
                output = row["output_structure"]
                path = resolve_path(root, output["path"]).resolve()
                if not path.is_relative_to(destination) or digest(path) != output["sha256"]:
                    raise ValueError("弛豫输出结构缺失、改变或不属于当前输出目录。")
        for sqs in sqs_records:
            signature, _ = _energy_signature(sqs)
            if not _is_usable(sqs) or signature is None or _fraction_b(sqs)[3]:
                continue
            status["usable_sqs"] += 1
            if all(
                _select_endmember(
                    str(sqs[f"mp_id_{side}"]), endmembers=endmembers, energy_signature=signature
                )[0]
                is not None
                for side in ("a", "b")
            ):
                status["usable_pairs"] += 1
        status["evidence_valid"] = True
        status["ready"] = status["usable_pairs"] > 0
        status["message"] = (
            f"{status['usable_pairs']} 项合金具备同能量基准的端元结果，可进入09。"
            if status["ready"]
            else "尚无完整可用的合金与端元能量组合；请补齐端元或处理失败、未收敛项。"
        )
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        ImportError,
        EOFError,
        csv.Error,
        pickle.UnpicklingError,
    ) as exc:
        status["message"] = str(exc)
    return status
