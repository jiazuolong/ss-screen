"""Stage 13 detector *materials-level* evidence adapter.

Legacy instrument columns are intentionally removed. All structural/energy
values are read from existing evidence; lattice and substrate geometry must
be computed from real structure manifests with geometry_pipeline. No device
figures are inferred from gaps or strain.
"""
from __future__ import annotations

import ast
import csv
import os
import json
import math
from pathlib import Path
from typing import Mapping

from .material_assessment import (
    MINIMUM_GAP_CONFIGURATIONS, PHOTON_ENERGY_EV_UM,
    assess_endpoint_gap_range, summarize_material_evidence,
)

DEFAULT_TARGET_UM = 2.0
BAND_PRESETS_UM = {
    '近红外（NIR）：1.0 μm': 1.0,
    '短波红外（SWIR）：2.0 μm': 2.0,
    '中波红外（MWIR）：4.0 μm': 4.0,
    '长波红外（LWIR）：10.0 μm': 10.0,
}
OUTPUT_COLUMNS = (
    'candidate_id','pair_index','comp_a','comp_b','fraction_b',
    'gap_a_eV','gap_b_eV','endpoint_gap_min_eV','endpoint_gap_max_eV',
    'endpoint_gap_range_eV','endpoint_gap_origin','gap_rule',
    'alloy_gap_eV','gap_range_eV','gap_origin','gap_equivalent_wavelength_um',
    'gap_status','gap_target_status','gap_valid_configuration_count','expected_configuration_count',
    'target_um','target_gap_eV','band_match',
    'lattice_mismatch_pct','lattice_status',
    'phonon_min_THz','phonon_status',
    'mixing_enthalpy_meV_atom','mixing_status',
    'energy_above_hull_meV_atom','hull_status',
    'substrate_principal_strain_pct','substrate_status',
    'substrate_id','film_miller','substrate_miller','match_area_A2','match_id',
    'substrate_recommendations',
    'candidate_grade','material_grade','material_reason','geometry_grade','evidence_completeness',
    'source_structure_id','data_origin','caution',
)


def _number(value: object) -> float | None:
    if value is None or isinstance(value,bool): return None
    try: x = float(str(value).strip())
    except (ValueError,TypeError): return None
    return x if math.isfinite(x) else None


def read_csv(path: Path) -> list[dict[str,str]]:
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def index_geometry(rows: list[dict[str,str]]) -> dict[str,dict[str,str]]:
    """Reject duplicate identity instead of silently replacing a composition."""
    result: dict[str,dict[str,str]] = {}
    for r in rows:
        cid=str(r.get('candidate_id') or '').strip()
        if not cid: raise ValueError('Geometry candidate_id missing')
        if cid in result: raise ValueError(f'Duplicate geometry candidate_id: {cid}')
        result[cid] = r
    return result


def _checked(row: Mapping[str,object], status_key: str, value_key: str, *,
             nonnegative: bool = False) -> float | None:
    status=str(row.get(status_key) or '').lower().strip()
    if status not in ('success','completed','valid','ok'): return None
    n=_number(row.get(value_key))
    return n if n is not None and (not nonnegative or n>=0) else None


def assess_candidate(row: Mapping[str,object], target_um: float,
                     geometry: Mapping[str,object] | None = None, *,
                     data_origin: str = '工程结果') -> dict[str,object]:
    target=_number(target_um)
    if target is None or target<=0: raise ValueError('目标波长须为正的有限数值（μm）')
    candidate_id=str(row.get('recommendation_id') or row.get('candidate_id') or row.get('pair_index') or '未编号')
    x=_number(row.get('actual_fraction_b'))
    if x is None: x=_number(row.get('target_fraction_b'))
    if x is not None and not 0 <= x <= 1: x=None
    endpoint = assess_endpoint_gap_range(
        row.get('gap_a_eV', (geometry or {}).get('gap_a_eV')),
        row.get('gap_b_eV', (geometry or {}).get('gap_b_eV')), target,
    )
    if row.get('endpoint_gap_conflict'):
        endpoint.update(gap_target_status='待核验',band_match='端元带隙来源冲突')
    gap_a, gap_b = endpoint['gap_a_eV'], endpoint['gap_b_eV']
    endpoint_gap_min, endpoint_gap_max = endpoint['endpoint_gap_min_eV'], endpoint['endpoint_gap_max_eV']
    target_gap, band_match = endpoint['target_gap_eV'], endpoint['band_match']
    gap=None;gap_origin='缺少直接合金带隙'
    for key in ('alloy_gap_eV','gap_alloy_eV','band_gap_eV'):
        n=_number(row.get(key))
        if n is not None and n>0:
            gap=n;gap_origin=f'输入合金带隙（{key}，仍需核验来源与QC）';break
    geom=geometry or {}
    # Geometry results are joined by explicit candidate identity and actual composition.
    linked=bool(geom)
    gx=_number(geom.get('actual_fraction_b'))
    if linked and (gx is None or x is None or abs(gx-x)>1e-6):
        raise ValueError(f'{candidate_id}: geometry actual_fraction_b mismatch')
    if linked and str(geom.get('candidate_id')) != candidate_id:
        raise ValueError(f'{candidate_id}: geometry candidate_id mismatch')
    gap_count = _number(geom.get('gap_valid_configuration_count')) or 0
    gap_status = str(geom.get('gap_status') or '待补充')
    gap_target_status = endpoint['gap_target_status']
    if gap_status == '有效' and gap_count < MINIMUM_GAP_CONFIGURATIONS:
        gap_status = '构型数量待核验'
    if linked and gap_status in ('有效','探索性计算') and _number(geom.get('gap_eV')) is not None and _number(geom.get('gap_eV')) >= 0:
        gap = _number(geom['gap_eV'])
        gap_origin = f'已有合金带隙（{int(gap_count)}个有效构型，结构SHA与QC已核验）'
    phonon=_checked(row,'phonon_status','minimum_mesh_frequency_THz')
    mixing=_checked(row,'mixing_status','mixing_enthalpy_meV_per_atom')
    hull=_checked(row,'phase_status','energy_above_hull_eV_per_atom',nonnegative=True)
    # Stage 12 rows carry one structure; two-configuration aggregates from the
    # geometry evaluator take precedence only when explicitly valid.
    def gnumber(key: str) -> float | None:
        return _number(geom.get(key)) if linked else None
    def display(key: str, fallback: object = None) -> object:
        value=geom.get(key) if linked else None
        return value if value not in (None,'') else fallback
    result: dict[str,object] = {
        'candidate_id':candidate_id,'pair_index':row.get('pair_index',''),
        'comp_a':row.get('comp_a',''),'comp_b':row.get('comp_b',''),
        'fraction_b':x,'gap_a_eV':gap_a,'gap_b_eV':gap_b,
        'endpoint_gap_min_eV':endpoint_gap_min,'endpoint_gap_max_eV':endpoint_gap_max,
        'alloy_gap_eV':gap,'gap_origin':gap_origin,
        'gap_range_eV':geom.get('gap_range_eV',''),
        'gap_status':gap_status,'gap_target_status':gap_target_status,
        'gap_valid_configuration_count':int(gap_count),
        'expected_configuration_count':int(_number(geom.get('expected_configuration_count')) or 0),
        'gap_equivalent_wavelength_um':PHOTON_ENERGY_EV_UM/gap if gap else None,
        'target_um':target,'target_gap_eV':target_gap,'band_match':band_match,
        'lattice_mismatch_pct':gnumber('lattice_mismatch_pct'),
        'lattice_status':display('lattice_status','待补充'),
        'phonon_min_THz':gnumber('phonon_min_THz') if gnumber('phonon_min_THz') is not None else phonon,
        'phonon_status':display('phonon_status', '待补充' if phonon is None else '需结合双构型核验'),
        'mixing_enthalpy_meV_atom':gnumber('mixing_enthalpy_meV_atom') if gnumber('mixing_enthalpy_meV_atom') is not None else mixing,
        'mixing_status':display('mixing_status','待补充' if mixing is None else '需结合双构型核验'),
        'energy_above_hull_meV_atom':gnumber('energy_above_hull_meV_atom') if gnumber('energy_above_hull_meV_atom') is not None else (hull*1000 if hull is not None else None),
        'hull_status':display('hull_status','待补充' if hull is None else '需结合双构型核验'),
        'substrate_principal_strain_pct':gnumber('substrate_principal_strain_pct'),
        'substrate_status':display('substrate_status','待补充'),
        'substrate_id':display('substrate_id',''),
        'substrate_recommendations':'',
        'film_miller':display('film_miller',''),
        'substrate_miller':display('substrate_miller',''),
        'match_area_A2':gnumber('match_area_A2'),
        'match_id':display('match_id',''),
        'candidate_grade':display('candidate_grade','待补充'),
        'geometry_grade':display('geometry_grade','几何数据待补充'),
        'evidence_completeness':display('evidence_completeness','部分缺失'),
        'source_structure_id':row.get('structure_id',''),
        'data_origin':data_origin,
        'caution':'材料级预筛；端元带隙范围覆盖仅表示目标光子能量落在两端元带隙之间，不证明合金带隙单调变化或实际探测响应。单seed衬底几何不证明实际外延。',
    }
    # Reevaluate coverage for the current wavelength, never a cached alloy-gap status.
    result.update(endpoint)
    # Stage 13's candidate priority is the requested endpoint-gap-range rule.
    # Keep every pair in the table: covered pairs are priority candidates;
    # uncovered or incomplete endpoint evidence remains visible as secondary.
    result['candidate_grade'] = '优先' if band_match == '端元范围覆盖' else '次优'
    # Validated adverse Stage 12 evidence remains adverse when geometry is
    # absent. Reuse its explicit threshold decisions instead of inventing new
    # cutoffs here; missing/failed property records must never become risks
    # merely because they contain a stale numeric value.
    risks = row.get('risks', [])
    if isinstance(risks, str):
        try:
            risks = json.loads(risks)
        except (ValueError, TypeError):
            risks = []
    if not isinstance(risks, (list, tuple)):
        risks = []
    if phonon is not None and 'phonon:unstable' in risks:
        result['phonon_status'] = '显著虚频'
    if mixing is not None and 'mixing:above_low_priority_threshold' in risks:
        result['mixing_status'] = '高风险'
    if (hull is not None and 'phase:above_low_priority_threshold' in risks
            and str(row.get('competing_set_complete', '')).lower() == 'true'):
        result['hull_status'] = '高风险'
    evidence = summarize_material_evidence(result)
    result['material_grade'] = evidence['candidate_grade']
    result['material_reason'] = evidence['recommendation_reason']
    result['evidence_completeness'] = evidence['evidence_completeness']
    # Endpoint range is a pair-level screening estimate, never an alloy-gap
    # interpolation. A direct alloy gap remains a separate evidence field.
    if data_origin.startswith('内置演示'):
        result['candidate_grade']='演示数据（不可评级）'
        result['material_grade']='演示数据（不可评级）'
    return result


def assess_rows(rows: list[Mapping[str,object]], target_um: float,
                geometry: Mapping[str,Mapping[str,object]] | None = None,
                *,data_origin: str='工程结果') -> list[dict[str,object]]:
    """Group Stage 12 by pair + actual x and join geometry only by explicit key.

    Stage 12 recommendation_id is *per structure*, so it must not be used as
    the sole identity for a pair + composition. A geometry record can bind via
    stage12_pair_index or exactly matching candidate ID, never by row index.
    """
    geometry_rows=list((geometry or {}).values())
    grouped: dict[tuple[str,str],list[Mapping[str,object]]] = {}
    for r in rows:
        pair=str(r.get('pair_index') or '').strip()
        x=_number(r.get('actual_fraction_b'))
        if x is None:x=_number(r.get('target_fraction_b'))
        if pair and x is not None:
            key=(pair,f'{x:.8f}')
        else:
            # Unknown identity is preserved as a standalone row, never merged.
            key=('__unmapped__',str(r.get('recommendation_id') or r.get('candidate_id') or len(grouped)))
        grouped.setdefault(key,[]).append(r)
    used: set[tuple[str,str]] = set()
    result=[]
    for g in geometry_rows:
        pair=str(g.get('stage12_pair_index') or '').strip()
        x=_number(g.get('actual_fraction_b'))
        key=(pair,f'{x:.8f}') if pair and x is not None else None
        if key is not None:
            if key in used: raise ValueError(f'duplicate stage12_pair_index + fraction mapping: {key}')
            members=grouped.get(key,[])
            used.add(key)
        else:
            # Only permit exact candidate_id/recommendation_id when no pair map.
            members=[r for r in rows if str(r.get('recommendation_id') or r.get('candidate_id') or '')==str(g.get('candidate_id'))]
        source=dict(members[0]) if members else {}
        if len({(_number(r.get('gap_a_eV')),_number(r.get('gap_b_eV'))) for r in members})>1:
            source.update(gap_a_eV=None,gap_b_eV=None,endpoint_gap_conflict=True)
        source.update({
            'recommendation_id':g.get('candidate_id'),
            'pair_index':pair or source.get('pair_index',''),
            'actual_fraction_b':g.get('actual_fraction_b'),
            'comp_a':g.get('comp_a') or source.get('comp_a',''),
            'comp_b':g.get('comp_b') or source.get('comp_b',''),
        })
        result.append(assess_candidate(source,target_um,g,data_origin=data_origin))
    for key,members in grouped.items():
        if key in used:continue
        source=dict(members[0])
        if len({(_number(r.get('gap_a_eV')),_number(r.get('gap_b_eV'))) for r in members})>1:
            source.update(gap_a_eV=None,gap_b_eV=None,endpoint_gap_conflict=True)
        # Do not claim two valid configurations merely because two rows exist;
        # the required expected_structure_ids / QC / SHA come from manifests.
        assessed=assess_candidate(source,target_um,data_origin=data_origin)
        assessed['caution']+=f' Stage12同组记录数：{len(members)}；尚需完整构型身份与QC核验。'
        result.append(assessed)
    return result


def format_assessment_rows(rows, top_matches_by_candidate):
    """Add composition labels and substrate summaries used in the GUI and CSV."""
    for row in rows:
        comp_a=str(row.get('comp_a') or '')
        comp_b=str(row.get('comp_b') or '')
        x=row.get('fraction_b')
        subscript=str.maketrans('0123456789.-','₀₁₂₃₄₅₆₇₈₉.₋')
        if comp_a and comp_b and x is not None:
            prefix=os.path.commonprefix([comp_a,comp_b])
            xa=f'{1-float(x):g}'.translate(subscript)
            xb=f'{float(x):g}'.translate(subscript)
            row['candidate_material']=f'{prefix}{comp_a[len(prefix):]}{xa}{comp_b[len(prefix):]}{xb}'
        else:
            row['candidate_material']=str(row.get('candidate_id') or '未命名候选')
        row['gap_candidate_status']=(
            '满足带隙候选' if row.get('band_match')=='端元范围覆盖' else '次优'
        )
        matches=top_matches_by_candidate.get(str(row.get('candidate_id') or ''),[])[:3]
        formatted=[]
        for rank,match in enumerate(matches,1):
            substrate=match.get('substrate_id') or '未命名衬底'
            try:
                strains=ast.literal_eval(match.get('principal_strains') or '[]')
                strain_text=' / '.join(f'{float(value)*100:+.4f}' for value in strains)
            except (ValueError,TypeError,SyntaxError):
                try:
                    strain_text='±'+f"{float(match.get('max_abs_principal_strain'))*100:.2f}"
                except (ValueError,TypeError):
                    strain_text='应变缺失'
            formatted.append(f'{rank}. {substrate}：{strain_text}%')
        if not formatted and row.get('substrate_id') and row.get('substrate_principal_strain_pct') is not None:
            formatted.append(f"{row['substrate_id']}：最大绝对应变 {float(row['substrate_principal_strain_pct']):.4f}%（汇总）")
        row['substrate_recommendations']='\n'.join(formatted) if formatted else '—'


def export_rows(path: Path, rows: list[dict[str,object]]) -> None:
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=OUTPUT_COLUMNS,extrasaction='ignore')
        writer.writeheader();writer.writerows(rows)


DEMO_ROWS: tuple[dict[str,str],...]=(
    {'recommendation_id':'DEMO-001','pair_index':'1','comp_a':'演示端元A','comp_b':'演示端元B','gap_a_eV':'0.38','gap_b_eV':'0.72','target_fraction_b':'0.5'},
    {'recommendation_id':'DEMO-002','pair_index':'2','comp_a':'演示端元C','comp_b':'演示端元D','gap_a_eV':'0.13','gap_b_eV':'0.23','target_fraction_b':'0.3'},
    {'recommendation_id':'DEMO-003','pair_index':'3','comp_a':'演示端元E','comp_b':'演示端元F','gap_a_eV':'1.6','gap_b_eV':'2.0','target_fraction_b':'0.7'},
)
