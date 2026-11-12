"""Transparent aggregation of validated Stage 13 material evidence."""

from __future__ import annotations

import math
from collections.abc import Mapping

MINIMUM_GAP_CONFIGURATIONS = 2
PHOTON_ENERGY_EV_UM = 1.239841984

EVALUATION_TABLE_MD = """| 项目 | 优先候选条件 | 中间区间或待核验条件 |
|---|---|---|
| 端元带隙范围 | 用户波长对应能量 E=1.239841984/λ（λ单位μm）落入两个端元带隙的闭区间 | 未覆盖时列为次优；端元带隙缺失或目标波长未设置时待补充 |
| **晶格常数匹配（新增）** | **统一晶胞与晶轴后，最大晶格长度失配≤3%，且角度检查通过** | **3%–5%备选；>5%较大失配风险；无法建立可靠对应关系时待核验** |
| 声子谱 | 无低于−0.1 THz的显著虚频，且质检通过 | 临界软模、未收敛或采样不足需复核；显著虚频降低优先级 |
| 混合焓 | ≤25 meV/atom | 25–50 meV/atom备选；>50降低优先级 |
| 凸包上能 | ≤25 meV/atom | 25–100 meV/atom备选；>100降低优先级 |
| 衬底主应变 | 保持当前配置：选定代表构型最佳匹配的最大绝对主应变≤1% | 1%–3%备选；保留当前搜索和前三衬底规则 |

数值为默认评价阈值；实际判定采用工程配置。缺失数据不会填零。
带隙项仅采用端元范围覆盖规则，不要求合金带隙计算或两个合金构型。
范围覆盖是材料配对筛选条件，不代表已得到特定组分的实际合金带隙。
只有六项有效证据均达到优先条件才给出“优先进一步验证”。显著虚频或高混合焓/凸包上能
给出“降低优先级”，同时保留缺失项；其他不完整证据为“待补充”，中间区间为“备选/需复核”。
"""

EVIDENCE_DIMENSIONS = (
    ("gap_target_status", "端元带隙范围"),
    ("lattice_status", "晶格匹配"),
    ("phonon_status", "声子谱"),
    ("mixing_status", "混合焓"),
    ("hull_status", "凸包上能"),
    ("substrate_status", "衬底主应变"),
)

_COMPLETE_STATUSES = {
    "优先",
    "通过",
    "备选",
    "较大失配风险",
    "显著虚频",
    "高风险",
    "降低优先级",
    "较高应变",
    "跨越或偏离目标区间",
    "范围内未找到",
    "表面原胞超面积上限",
    "次优",
}


def assess_endpoint_gap_range(gap_a: object, gap_b: object, target_um: object) -> dict[str, object]:
    """Evaluate endpoint coverage only; a zero endpoint gap is valid evidence."""

    def number(value: object) -> float | None:
        if isinstance(value, bool):
            return None
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return value if math.isfinite(value) and value >= 0 else None

    a, b, wavelength = number(gap_a), number(gap_b), number(target_um)
    wavelength = wavelength if wavelength and wavelength > 0 else None
    energy = PHOTON_ENERGY_EV_UM / wavelength if wavelength else None
    lo, hi = (min(a, b), max(a, b)) if a is not None and b is not None else (None, None)
    if energy is None:
        match, status = "目标波长未设置", "待补充"
    elif lo is None:
        match, status = "端元带隙缺失", "待补充"
    elif lo <= energy <= hi:
        match, status = "端元范围覆盖", "优先"
    else:
        match, status = "端元范围未覆盖", "次优"
    return {
        "gap_a_eV": a,
        "gap_b_eV": b,
        "endpoint_gap_min_eV": lo,
        "endpoint_gap_max_eV": hi,
        "endpoint_gap_range_eV": f"{lo:.4f}–{hi:.4f}" if lo is not None else "",
        "target_um": wavelength,
        "target_gap_eV": energy,
        "band_match": match,
        "gap_target_status": status,
        "gap_rule": "endpoint_range_covers_photon_energy",
        "endpoint_gap_origin": "两个端元带隙范围与用户目标波长",
    }


def summarize_material_evidence(row: Mapping[str, object]) -> dict[str, str]:
    """Combine explicit per-property QC/threshold statuses, without an opaque score.

    Unknown statuses remain incomplete. Negative evidence remains visible even
    when another dimension (for example an endpoint gap) is still missing.
    """
    statuses = {key: str(row.get(key) or "待补充").strip() for key, _ in EVIDENCE_DIMENSIONS}
    pending = any(value not in _COMPLETE_STATUSES for value in statuses.values())
    adverse = (
        statuses["phonon_status"] == "显著虚频"
        or statuses["mixing_status"] in {"高风险", "降低优先级"}
        or statuses["hull_status"] in {"高风险", "降低优先级"}
    )
    if adverse:
        grade = "降低优先级"
    elif pending:
        grade = "待补充"
    elif all(value in {"优先", "通过"} for value in statuses.values()):
        grade = "优先进一步验证"
    else:
        grade = "备选/需复核"
    return {
        "candidate_grade": grade,
        "evidence_completeness": "部分缺失" if pending else "完整",
        "recommendation_reason": "；".join(
            f"{label}：{statuses[key]}" for key, label in EVIDENCE_DIMENSIONS
        ),
    }
