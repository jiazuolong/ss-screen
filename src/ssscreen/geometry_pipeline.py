"""Stage 13 optional, offline, structure-backed geometry evaluation.

Canonical identity: candidate_id + actual_fraction_b + reference_set_id; each
structure is bound to structure_id + SHA256.  No inferred substitutions, no
seed101 -> seed202 fallback, and no fabricated material/device properties.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .material_assessment import (
    EVALUATION_TABLE_MD, MINIMUM_GAP_CONFIGURATIONS, assess_endpoint_gap_range,
    summarize_material_evidence,
)

from .geometry_core import (
    Thresholds, inplane_principal_strain, lattice_diagnostics, lattice_grade,
    miller_indices, representative_matches, select_consistent_match, substrate_grade,
)

DEFAULT_CONFIG = {
    'schema_version': 2,
    'gap_target_eV': None,
    'detector_context': {
        'mechanism':'interband_photodetection',
        'target_wavelength_um':None,'operating_temperature_K':None,
        'film_thickness_um':None,'illumination_geometry':'unspecified',
    },
    'lattice': {
        'preferred_max_length_mismatch':0.03,
        'alternative_max_length_mismatch':0.05,
        'max_angle_difference_deg':1.0,
        'mapping_length_tol':0.2,
        'mapping_angle_tol_deg':5.0,
        'mapping_site_tol':0.3,
        'symprec_A':0.01,
    },
    'substrate': {
        'film_lattice_model':'relaxed_sqs',
        'selection_mode':'single_representative',
        'representative_seed':101,
        'selected_structure_ids':{},
        'allow_automatic_seed_fallback':False,
        'film_max_miller':1,
        'substrate_max_miller':1,
        'max_area_A2':800.0,
        'max_length_tol':0.03,
        'max_angle_tol':0.01,
        'max_area_ratio_tol':0.09,
        'bidirectional':False,
        'symprec_A':0.01,
        'preferred_max_principal_strain':0.01,
        'alternative_max_principal_strain':0.03,
        'top_n':3,
    },
    'existing_property_thresholds': {
        'imaginary_frequency_tolerance_THz':0.1,
        'preferred_max_mixing_meV_atom':25.0,
        'high_mixing_meV_atom':50.0,
        'preferred_max_hull_meV_atom':25.0,
        'high_hull_meV_atom':100.0,
    },
    'execution': {'workers':1,'resume':True,'compress_details':True},
}


MAIN_COLUMNS = (
    'candidate_id', 'pair_id', 'stage12_pair_index', 'comp_a', 'comp_b', 'actual_fraction_b', 'reference_set_id',
    'gap_a_eV','gap_b_eV','endpoint_gap_min_eV','endpoint_gap_max_eV','endpoint_gap_range_eV',
    'target_um','target_gap_eV','band_match','gap_rule','endpoint_gap_origin',
    'gap_eV', 'gap_range_eV', 'gap_status', 'gap_target_status',
    'gap_valid_configuration_count', 'expected_configuration_count',
    'lattice_mismatch_pct', 'lattice_angle_difference_deg', 'lattice_status',
    'phonon_min_THz', 'phonon_status', 'mixing_enthalpy_meV_atom', 'mixing_range_meV_atom',
    'mixing_status', 'energy_above_hull_meV_atom', 'hull_status',
    'substrate_principal_strain_pct', 'substrate_status', 'substrate_id',
    'film_miller', 'substrate_miller', 'match_area_A2', 'match_id',
    'selected_seed', 'selected_structure_id', 'selected_structure_sha256',
    'selection_status', 'available_configurations', 'substrate_configurations_evaluated',
    'geometry_grade', 'candidate_grade', 'evidence_completeness', 'recommendation_reason',
)


def _read_csv(path: Path, *, required: tuple[str, ...] = ()) -> list[dict[str, str]]:
    if not path.is_file():
        if not required:
            return []
        raise FileNotFoundError(f'Missing required manifest: {path}')
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        missing = set(required) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f'{path.name} missing: {sorted(missing)}')
        return list(reader)


def _string(row: Mapping[str, Any], key: str) -> str:
    return str(row.get(key) or '').strip()


def _number(value: Any) -> float | None:
    try:
        x = float(str(value).strip())
        return x if math.isfinite(x) else None
    except (ValueError, TypeError):
        return None


def _positive_status(row: Mapping[str, Any]) -> bool:
    return _string(row, 'status').lower() in ('success', 'completed', 'ok', 'valid') and _string(row, 'qc_status').lower() in ('pass','passed','success','ok','valid')


def _relative(base: Path, text: str) -> Path:
    p = Path(text).expanduser()
    return p if p.is_absolute() else base / p


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as fh:
        for block in iter(lambda: fh.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _load_structure(row: Mapping[str, str], base: Path) -> Any:
    from pymatgen.core import Structure
    path = _relative(base, _string(row, 'structure_file'))
    expected = _string(row, 'sha256').lower()
    if not path.is_file() or not expected or _sha256(path) != expected:
        raise ValueError(f'structure missing or SHA mismatch: {path}')
    structure = Structure.from_file(str(path))
    if abs(np.linalg.det(structure.lattice.matrix)) < 1e-10:
        raise ValueError('invalid structure lattice')
    return structure


def _config(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, dict):
        raise ValueError('config must be an object')
    unknown = set(raw) - set(DEFAULT_CONFIG)
    if unknown:
        raise ValueError(f'unknown config fields: {sorted(unknown)}')
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    for category in ('lattice', 'substrate', 'existing_property_thresholds','execution','detector_context'):
        overrides = raw.get(category, {})
        if not isinstance(overrides, dict) or set(overrides) - set(config[category]):
            raise ValueError(f'unknown {category} configuration fields')
        config[category].update(overrides)
    config['gap_target_eV'] = raw.get('gap_target_eV')
    if raw.get('schema_version') != 2:
        raise ValueError('schema_version must be 2')
    lower_upper = config['gap_target_eV']
    if lower_upper is not None:
        if not isinstance(lower_upper, list) or len(lower_upper) != 2 or any(_number(x) is None or float(x) <= 0 for x in lower_upper) or lower_upper[0] > lower_upper[1]:
            raise ValueError('gap_target_eV must be null or [positive_min, positive_max]')
    lat, sub, other = config['lattice'], config['substrate'], config['existing_property_thresholds']
    Thresholds(lat['preferred_max_length_mismatch'], lat['alternative_max_length_mismatch'],lat['max_angle_difference_deg'],sub['preferred_max_principal_strain'],sub['alternative_max_principal_strain'])
    for group in (lat, sub, other):
        for key, value in group.items():
            if key in ('selected_structure_ids','allow_automatic_seed_fallback','bidirectional','film_lattice_model','selection_mode'):
                continue
            if _number(value) is None or float(value) < 0:
                raise ValueError(f'invalid config parameter: {key}')
    if sub['film_lattice_model'] != 'relaxed_sqs' or sub['selection_mode'] != 'single_representative':
        raise ValueError('Only relaxed_sqs / single_representative is supported')
    if raw.get('execution',{}).get('workers',1) != 1:
        raise ValueError('Parallel execution is not enabled in this initial implementation')
    if config['execution']['compress_details'] is not True:
        raise ValueError('match_details compression is mandatory')
    if not isinstance(config['execution']['resume'],bool):
        raise ValueError('execution.resume must be a boolean')
    context=config['detector_context']
    if context['mechanism'] != 'interband_photodetection':
        raise ValueError('Only interband photodetection context is supported')
    for key in ('target_wavelength_um','operating_temperature_K','film_thickness_um'):
        if context[key] is not None and (_number(context[key]) is None or float(context[key])<=0):
            raise ValueError(f'invalid detector_context.{key}')
    if sub['allow_automatic_seed_fallback'] is not False:
        raise ValueError('automatic seed fallback is forbidden')
    if not isinstance(sub['selected_structure_ids'], dict):
        raise ValueError('selected_structure_ids must be an object')
    if sub['bidirectional'] is not False:
        raise ValueError('bidirectional must be false in Stage 13 v1')
    if not 1 <= int(sub['film_max_miller']) <= 3 or not 1 <= int(sub['substrate_max_miller']) <= 3:
        raise ValueError('Miller limits out of range')
    if float(sub['max_area_A2']) <= 0 or int(sub['top_n']) <= 0:
        raise ValueError('invalid area/top_n')
    return config


def _replaceable_symbol(specie: Any, allowed: set[str]) -> str:
    name = getattr(specie, 'symbol', str(specie))
    return '__REPLACEABLE__' if name in allowed else name


def _can_match_sites(a: Any, b: Any, transform_b: np.ndarray,
                     allowed_a: set[str], allowed_b: set[str], tol_A: float) -> tuple[bool, list[int], float]:
    if len(a) != len(b) or len(a) == 0:
        return False, [], float('inf')
    A = a.frac_coords % 1.0
    B = (b.frac_coords @ np.linalg.inv(transform_b)) % 1.0
    species_a = [_replaceable_symbol(s, allowed_a) for s in a.species]
    species_b = [_replaceable_symbol(s, allowed_b) for s in b.species]
    if sorted(species_a) != sorted(species_b):
        return False, [], float('inf')
    candidates = [j for j, kind in enumerate(species_b) if kind == species_a[0]]
    for j0 in candidates:
        shift = A[0]-B[j0]
        occupied: set[int] = set()
        mapping: list[int] = []
        max_dist = 0.0
        for i, coord in enumerate(A):
            valid = []
            for j, bc in enumerate(B):
                if j in occupied or species_a[i] != species_b[j]:
                    continue
                delta = coord-bc-shift
                delta -= np.rint(delta)
                dist = float(np.linalg.norm(delta @ a.lattice.matrix))
                valid.append((dist,j))
            if not valid:
                break
            dist, j = min(valid)
            if dist > tol_A:
                break
            max_dist = max(max_dist, dist)
            mapping.append(j)
            occupied.add(j)
        if len(mapping) == len(a):
            return True, mapping, max_dist
    return False, [], float('inf')


def lattice_match(a: Any, b: Any, row: Mapping[str, str], config: dict[str, Any]) -> dict[str, Any]:
    """Strict equal-site, species-restricted signed-axis mapping; otherwise pending.

    Different primitive/conventional cell sizes are deliberately marked for
    review rather than equated or force volume-scaled.  No false match.
    """
    if len(a) != len(b):
        return {'lattice_status':'待核验', 'reason':'端元晶胞原子数不同，需明确原胞/常规胞对应关系'}
    allowed_a = set(_string(row, 'replaceable_a').replace(';',',').split(',')) - {''}
    allowed_b = set(_string(row, 'replaceable_b').replace(';',',').split(',')) - {''}
    if bool(allowed_a) != bool(allowed_b):
        return {'lattice_status':'待核验', 'reason':'仅指定了一端的可替换元素'}
    lat_cfg = config['lattice']
    th = Thresholds(lat_cfg['preferred_max_length_mismatch'], lat_cfg['alternative_max_length_mismatch'], lat_cfg['max_angle_difference_deg'])
    candidates: list[dict[str, Any]] = []
    for axes in itertools.permutations(range(3)):
        for signs in itertools.product((-1,1),repeat=3):
            M = np.zeros((3,3),dtype=int)
            for rowindex,(idx,sgn) in enumerate(zip(axes, signs)):
                M[rowindex,idx] = sgn
            if round(np.linalg.det(M)) != 1:
                continue
            match, mapping, residual = _can_match_sites(a,b,M,allowed_a,allowed_b,lat_cfg['mapping_site_tol'])
            if match:
                diag = lattice_diagnostics(a.lattice.matrix,M @ b.lattice.matrix)
                if (diag['max_length_mismatch'] > lat_cfg['mapping_length_tol'] or
                    diag['max_angle_difference_deg'] > lat_cfg['mapping_angle_tol_deg']):
                    continue
                diag.update(lattice_status=lattice_grade(diag, th), transform_b=M.tolist(), site_mapping=mapping, mapping_residual_A=residual)
                candidates.append(diag)
    if not candidates:
        return {'lattice_status':'待核验', 'reason':'未找到保留固定元素占位的可信晶轴/位点映射'}
    # Ambiguous grading must not be silently resolved in favor of a good match.
    grades = {m['lattice_status'] for m in candidates}
    best = min(candidates, key=lambda m: (m['max_length_mismatch'],m['max_angle_difference_deg'],m['mapping_residual_A'],str(m['transform_b'])))
    if len(grades) > 1:
        best = dict(best, lattice_status='待核验',reason=f'非等价映射等级冲突: {sorted(grades)}')
    else:
        best['reason'] = '已核验晶轴置换与允许位点映射（未进行体积缩放）'
    best['mapping_count'] = len(candidates)
    return best


def _plane_vectors(structure: Any, miller: tuple[int,int,int]) -> tuple[np.ndarray,np.ndarray]:
    from pymatgen.core.surface import SlabGenerator
    slab_gen = SlabGenerator(structure, miller, min_slab_size=1,
                             min_vacuum_size=1, primitive=False,
                             in_unit_planes=True,reorient_lattice=False)
    ouc = slab_gen.oriented_unit_cell
    vectors = np.asarray(ouc.lattice.matrix[:2],float)
    return vectors,np.asarray(slab_gen.slab_scale_factor,int)


def _effective_supercell_matrix(base_vectors: np.ndarray, matched_vectors: np.ndarray) -> np.ndarray:
    """Recover the integer basis after ZSL's in-plane vector reduction.

    ZSLMatch transformations describe the unreduced supercell construction;
    ``film_sl_vectors``/``substrate_sl_vectors`` may additionally swap vectors
    or add/subtract one basis vector.  Persist the effective transform that
    actually reconstructs the returned matched basis.
    """
    coefficients = np.asarray(matched_vectors, dtype=float) @ np.linalg.pinv(
        np.asarray(base_vectors, dtype=float)
    )
    integer = np.rint(coefficients).astype(int)
    if not np.allclose(integer @ base_vectors, matched_vectors, rtol=1e-8, atol=1e-5):
        raise ValueError("reduced ZSL vectors cannot be reconstructed from integer surface basis")
    if abs(round(float(np.linalg.det(integer)))) == 0:
        raise ValueError("reduced ZSL surface transform is singular")
    return integer


def substrate_matches(film: Any, substrate: Any, sub_cfg: Mapping[str, Any],
                      identity: str, substrate_id: str) -> list[dict[str, Any]]:
    from pymatgen.analysis.interfaces.zsl import ZSLGenerator
    from pymatgen.core.surface import get_symmetrically_distinct_miller_indices
    zsl = ZSLGenerator(max_area_ratio_tol=sub_cfg['max_area_ratio_tol'],
                       max_area=sub_cfg['max_area_A2'],
                       max_length_tol=sub_cfg['max_length_tol'],
                       max_angle_tol=sub_cfg['max_angle_tol'],
                       bidirectional=False)
    # Geometric plane families in each actual input lattice; the two sides
    # are enumerated independently, without requiring equal Miller indices.
    film_planes = get_symmetrically_distinct_miller_indices(
        film, int(sub_cfg['film_max_miller'])
    )
    substrate_planes = get_symmetrically_distinct_miller_indices(
        substrate, int(sub_cfg['substrate_max_miller'])
    )
    out: list[dict[str, Any]] = []
    for fm in film_planes:
        film_vecs, film_basis = _plane_vectors(film, fm)
        film_area = np.linalg.norm(np.cross(*film_vecs))
        if film_area >= sub_cfg['max_area_A2']:
            continue
        for sm in substrate_planes:
            sub_vecs, sub_basis = _plane_vectors(substrate, sm)
            if np.linalg.norm(np.cross(*sub_vecs)) >= sub_cfg['max_area_A2']:
                continue
            for match in zsl(film_vecs,sub_vecs,lowest=False):
                V_f = np.asarray(match.film_sl_vectors,float)
                V_s = np.asarray(match.substrate_sl_vectors,float)
                d = inplane_principal_strain(V_f,V_s)
                if d['film_area_A2'] >= sub_cfg['max_area_A2'] or d['substrate_area_A2'] >= sub_cfg['max_area_A2']:
                    continue
                zsl_t_f = np.asarray(match.film_transformation,int)
                zsl_t_s = np.asarray(match.substrate_transformation,int)
                t_f = _effective_supercell_matrix(film_vecs, V_f)
                t_s = _effective_supercell_matrix(sub_vecs, V_s)
                metadata = f'{identity}|{substrate_id}|{fm}|{sm}|{t_f.tolist()}|{t_s.tolist()}'
                match_id = hashlib.sha256(metadata.encode()).hexdigest()[:20]
                out.append(dict(d,match_id=match_id,substrate_id=substrate_id,
                    film_miller=list(fm),substrate_miller=list(sm),
                    film_orientation_matrix=film_basis.tolist(),
                    substrate_orientation_matrix=sub_basis.tolist(),
                    film_supercell_matrix=t_f.tolist(),substrate_supercell_matrix=t_s.tolist(),
                    zsl_film_transformation=zsl_t_f.tolist(),zsl_substrate_transformation=zsl_t_s.tolist(),
                    film_supercell_vectors=V_f.tolist(),substrate_supercell_vectors=V_s.tolist(),
                    elastic_energy=None,film_lattice_model='relaxed_sqs',
                    strain_convention='fixed_substrate_deformed_film',
                    plane_enumeration='symmetrically_distinct_input_lattice'))
    return out


_PROPERTY_ALIASES = {
    'band_gap_eV': ('band_gap_eV', 'alloy_gap_eV', 'gap_eV'),
    'minimum_mesh_frequency_THz': ('minimum_mesh_frequency_THz', 'phonon_min_THz'),
    'mixing_enthalpy_meV_per_atom': ('mixing_enthalpy_meV_per_atom', 'mixing_enthalpy_meV_atom'),
    'energy_above_hull_eV_per_atom': ('energy_above_hull_eV_per_atom',),
}


def _property_summary(candidate: Mapping[str,str], rows: list[dict[str,str]], cfg: dict[str,Any], alloy_records: list[dict[str,str]]) -> dict[str,Any]:
    cid = candidate['candidate_id']
    expected = set(_string(candidate,'expected_structure_ids').replace(',',';').split(';'))-{''}
    props = [r for r in rows if _string(r,'candidate_id') == cid]
    identity_sha={r['structure_id']:_string(r,'sha256').lower() for r in alloy_records if r['candidate_id']==cid and r['reference_set_id']==candidate['reference_set_id'] and _number(r.get('actual_fraction_b'))==_number(candidate.get('actual_fraction_b')) and _positive_status(r)}
    # Expect distinct, structure-SHA-bound entries. Duplicated identity is invalid.
    valid_by_structure: dict[str, dict[str, Any]] = {}
    for r in props:
        sid = _string(r,'structure_id')
        if expected and sid not in expected:
            continue
        if not sid:
            continue
        if (not _positive_status(r) or not _string(r,'structure_sha256')
            or _string(r,'structure_sha256').lower()!=identity_sha.get(sid)
            or (_string(r,'reference_set_id') and _string(r,'reference_set_id')!=candidate['reference_set_id'])):
            continue
        aggregate = valid_by_structure.setdefault(sid, {'structure_id': sid})
        if _string(r, 'property'):
            # Documented properties.csv exchange format is long-form:
            # one candidate/structure/property/value row per measurement.
            key = _string(r, 'property')
            target = next((name for name, aliases in _PROPERTY_ALIASES.items() if key in aliases), None)
            if target is None:
                continue
            if target == 'energy_above_hull_eV_per_atom' and _string(r,'competing_set_complete').lower() in ('false','0','no'):
                continue
            if target in aggregate:
                raise ValueError(f'duplicate {target} in properties for {cid}/{sid}')
            aggregate[target] = r.get('value')
        else:
            # Also accept a wide row for compatibility with existing manifests.
            for target, aliases in _PROPERTY_ALIASES.items():
                if target == 'energy_above_hull_eV_per_atom' and _string(r,'competing_set_complete').lower() in ('false','0','no'):
                    continue
                value = next((_string(r, key) for key in aliases if _string(r, key)), '')
                if not value:
                    continue
                if target in aggregate:
                    raise ValueError(f'duplicate {target} in properties for {cid}/{sid}')
                aggregate[target] = value
    valid = list(valid_by_structure.values())
    expected_count = len(expected)
    coverage = expected_count > 0 and {r['structure_id'] for r in valid} == expected
    def col(key: str, require_nonnegative: bool=False) -> list[float]:
        values = [_number(r.get(key)) for r in valid]
        return [v for v in values if v is not None and (not require_nonnegative or v>=0)]
    gaps = col('band_gap_eV',True)
    freqs = col('minimum_mesh_frequency_THz')
    mixes = col('mixing_enthalpy_meV_per_atom')
    hulls = [_number(r.get('energy_above_hull_eV_per_atom')) for r in valid]
    hulls = [v for v in hulls if v is not None and v>=0]
    par = cfg['existing_property_thresholds']
    def fmt_range(vals: list[float]) -> str:
        return f'{min(vals):.8g}～{max(vals):.8g}' if vals else ''
    result = {
        'gap_eV': max(gaps) if gaps else None, 'gap_range_eV':fmt_range(gaps),
        'gap_status':('有效' if coverage and len(gaps)==expected_count and len(gaps)>=MINIMUM_GAP_CONFIGURATIONS
                      else '探索性计算' if gaps else '待补充'),
        'gap_valid_configuration_count':len(gaps),
        'expected_configuration_count':expected_count,
        'phonon_min_THz':min(freqs) if freqs else None,
        'phonon_status':'待补充' if not coverage or len(freqs)!=expected_count else ('显著虚频' if min(freqs)<-par['imaginary_frequency_tolerance_THz'] else '通过'),
        'mixing_enthalpy_meV_atom':max(mixes) if mixes else None,
        'mixing_range_meV_atom':fmt_range(mixes),
        'mixing_status':'待补充' if not coverage or len(mixes)!=expected_count else ('优先' if max(mixes)<=par['preferred_max_mixing_meV_atom'] else '备选' if max(mixes)<=par['high_mixing_meV_atom'] else '高风险'),
        'energy_above_hull_meV_atom':max(hulls)*1000 if hulls else None,
        'hull_status':'待补充' if not coverage or len(hulls)!=expected_count else ('优先' if max(hulls)*1000<=par['preferred_max_hull_meV_atom'] else '备选' if max(hulls)*1000<=par['high_hull_meV_atom'] else '高风险'),
    }
    return result


def _endpoint_gap_summary(candidate: Mapping[str,str], recommendations: list[dict[str,str]],
                          cfg: dict[str,Any]) -> dict[str,Any]:
    """Join pair-level endpoint gaps by identity, independent of alloy properties."""
    wavelength = cfg['detector_context']['target_wavelength_um']
    if all(_number(candidate.get(key)) is not None for key in ('gap_a_eV','gap_b_eV')):
        return assess_endpoint_gap_range(candidate['gap_a_eV'], candidate['gap_b_eV'], wavelength)
    fraction = _number(candidate.get('actual_fraction_b'))
    pair = _string(candidate,'stage12_pair_index')
    matched = [r for r in recommendations
               if pair and _string(r,'pair_index') == pair
               and fraction is not None and _number(r.get('actual_fraction_b')) is not None
               and abs(float(r['actual_fraction_b'])-fraction)<1e-6
               and all(not _string(candidate,key) or _string(r,key)==_string(candidate,key)
                       for key in ('comp_a','comp_b'))]
    gaps = {(_number(r.get('gap_a_eV')), _number(r.get('gap_b_eV'))) for r in matched}
    if len(gaps)==1:
        a,b = gaps.pop()
        return assess_endpoint_gap_range(a,b,wavelength)
    result = assess_endpoint_gap_range(None,None,wavelength)
    if len(gaps)>1:
        result.update(gap_target_status='待核验',band_match='端元带隙来源冲突')
    return result


def _write_csv(path: Path, rows: list[dict[str,Any]], fields: tuple[str,...] | list[str]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as fh:
        wr=csv.DictWriter(fh,fieldnames=fields,extrasaction='ignore')
        wr.writeheader();wr.writerows(rows)


def _safe_json(record: Any) -> str:
    return json.dumps(record,ensure_ascii=False,allow_nan=False,default=lambda x: x.tolist() if isinstance(x,np.ndarray) else str(x))


def _stage12_property_rows(candidates: list[dict[str,str]], alloys: list[dict[str,str]], recommendations: list[dict[str,str]]) -> list[dict[str,str]]:
    """Adapt identity-matched Stage 12 evidence without treating endpoint gaps as alloy gaps."""
    result: list[dict[str,str]] = []
    stage12_properties = (
        ('minimum_mesh_frequency_THz', 'minimum_mesh_frequency_THz', 'phonon_status', 'THz', False),
        ('mixing_enthalpy_meV_per_atom', 'mixing_enthalpy_meV_per_atom', 'mixing_status', 'meV/atom', False),
        ('energy_above_hull_eV_per_atom', 'energy_above_hull_eV_per_atom', 'phase_status', 'eV/atom', True),
    )
    for candidate in candidates:
        cid = _string(candidate, 'candidate_id')
        pair_index = _string(candidate, 'stage12_pair_index')
        fraction = _number(candidate.get('actual_fraction_b'))
        expected = set(_string(candidate, 'expected_structure_ids').replace(',', ';').split(';')) - {''}
        matched = [row for row in recommendations
                   if _string(row, 'pair_index') == pair_index
                   and _number(row.get('actual_fraction_b')) is not None
                   and fraction is not None
                   and abs(float(_number(row.get('actual_fraction_b'))) - fraction) < 1e-6
                   and _string(row, 'structure_id') in expected]
        if len({_string(row, 'structure_id') for row in matched}) != len(matched):
            raise ValueError(f'ambiguous Stage 12 rows for {cid}; duplicate structure identity')
        for source in matched:
            sid = _string(source, 'structure_id')
            alloy = [row for row in alloys
                     if _string(row, 'candidate_id') == cid
                     and _string(row, 'reference_set_id') == _string(candidate, 'reference_set_id')
                     and _string(row, 'structure_id') == sid
                     and _number(row.get('actual_fraction_b')) is not None
                     and fraction is not None
                     and abs(float(_number(row.get('actual_fraction_b'))) - fraction) < 1e-6]
            if len(alloy) != 1:
                continue
            identity = alloy[0]
            for property_name, source_key, status_key, unit, require_complete in stage12_properties:
                value = _string(source, source_key)
                status = _string(source, status_key).lower()
                if not value or status not in ('success', 'completed', 'valid', 'ok'):
                    continue
                if require_complete and _string(source, 'competing_set_complete').lower() not in ('true', '1', 'yes'):
                    continue
                result.append({
                    'candidate_id': cid, 'structure_id': sid,
                    'structure_sha256': _string(identity, 'sha256'),
                    'reference_set_id': _string(candidate, 'reference_set_id'),
                    'property': property_name, 'value': value, 'unit': unit,
                    'method': _string(source, 'model_sha256') or 'Stage 12 recommendation evidence',
                    'status': 'success', 'qc_status': 'pass',
                })
            # Only explicit direct alloy-gap fields are accepted. Stage 12's
            # gap_a_eV/gap_b_eV endpoints are deliberately not interpolated here.
            for source_key in ('alloy_gap_eV', 'band_gap_eV'):
                value = _string(source, source_key)
                if value and _string(source, 'gap_evidence_status').lower() in ('complete', 'success', 'valid'):
                    result.append({
                        'candidate_id': cid, 'structure_id': sid,
                        'structure_sha256': _string(identity, 'sha256'),
                        'reference_set_id': _string(candidate, 'reference_set_id'),
                        'property': 'band_gap_eV', 'value': value, 'unit': 'eV',
                        'method': _string(source, 'gap_method') or 'Stage 12 recommendation evidence',
                        'status': 'success', 'qc_status': 'pass',
                    })
                    break
    return result


def evaluate(input_dir: Path, config_path: Path, output_dir: Path,
             recommendations_path: Path | None = None, *, target_wavelength_um: float | None = None) -> dict[str,Any]:
    """Evaluate explicit identity manifests and write traceable Stage 13 artifacts.

    Requires pymatgen only when loading real structures / executing geometry.
    A single candidate failure produces an explicit status, never a fake zero.
    """
    input_dir, config_path, output_dir = Path(input_dir),Path(config_path),Path(output_dir)
    cfg=_config(config_path)
    if target_wavelength_um is not None:
        if _number(target_wavelength_um) is None or target_wavelength_um<=0:
            raise ValueError('target_wavelength_um must be positive and finite')
        cfg['detector_context']['target_wavelength_um']=float(target_wavelength_um)
    cands=_read_csv(input_dir/'candidates.csv',required=('candidate_id','pair_id','actual_fraction_b','reference_set_id','expected_structure_ids'))
    ends=_read_csv(input_dir/'endmembers.csv',required=('pair_id','role','reference_set_id','structure_file','sha256','status','qc_status'))
    alloys=_read_csv(input_dir/'alloy_structures.csv',required=('candidate_id','structure_id','seed','actual_fraction_b','reference_set_id','structure_file','sha256','status','qc_status'))
    props=_read_csv(input_dir/'properties.csv')
    recommendations = _read_csv(Path(recommendations_path)) if recommendations_path is not None else []
    if recommendations_path is not None:
        stage12_props = _stage12_property_rows(cands, alloys, recommendations)
        explicit = set()
        for row in props:
            if _string(row, 'property'):
                explicit.add((_string(row, 'candidate_id'), _string(row, 'structure_id'), _string(row, 'property')))
            else:
                for property_name, aliases in _PROPERTY_ALIASES.items():
                    if any(_string(row, key) for key in aliases):
                        explicit.add((_string(row, 'candidate_id'), _string(row, 'structure_id'), property_name))
        props.extend(row for row in stage12_props if
                     (_string(row, 'candidate_id'), _string(row, 'structure_id'), _string(row, 'property')) not in explicit)
    sub_json=input_dir/'substrates.json'
    subs=json.loads(sub_json.read_text(encoding='utf-8')) if sub_json.exists() else []
    if not isinstance(subs,list): raise ValueError('substrates.json must be a list')
    substrate_ids = [_string(s, 'substrate_id') for s in subs]
    if any(not sid for sid in substrate_ids) or len(set(substrate_ids)) != len(substrate_ids):
        raise ValueError('missing or duplicate substrate_id')
    if len({c['candidate_id'] for c in cands})!=len(cands):
        raise ValueError('duplicate candidate_id in candidates.csv')
    for c in cands:
        x=_number(c.get('actual_fraction_b'))
        if x is None or not 0 <= x <= 1:
            raise ValueError(f'invalid actual fraction in {c["candidate_id"]}')
    all_paths=[config_path]+[input_dir/f for f in ('candidates.csv','endmembers.csv','alloy_structures.csv','properties.csv','substrates.json') if (input_dir/f).is_file()]
    if recommendations_path is not None:
        all_paths.append(Path(recommendations_path))
    fp=hashlib.sha256()
    for p in sorted(all_paths): fp.update(str(p.name).encode()+_sha256(p).encode())
    fp.update(b'ssscreen_geometry_v2_distinct_planes')
    fp.update(_safe_json({'gap_rule':'endpoint_range_covers_photon_energy',
                        'target_wavelength_um':cfg['detector_context']['target_wavelength_um']}).encode())
    fingerprint=fp.hexdigest()
    output_dir.mkdir(parents=True,exist_ok=True)
    main=[]; lattice=[]; top=[]; structure_matches=[]; failures=[]; all_matches=[]
    sub_cfg=cfg['substrate']
    for c in sorted(cands,key=lambda r:(r['candidate_id'],r['actual_fraction_b'],r['reference_set_id'])):
        cid=c['candidate_id']; pair=c['pair_id']; ref=c['reference_set_id']
        row={name:None for name in MAIN_COLUMNS}
        row.update(candidate_id=cid,pair_id=pair,stage12_pair_index=c.get('stage12_pair_index',''),comp_a=c.get('comp_a',''),comp_b=c.get('comp_b',''),
                   actual_fraction_b=float(c['actual_fraction_b']),reference_set_id=ref)
        row.update(_property_summary(c,props,cfg,alloys))
        row.update(_endpoint_gap_summary(c,recommendations,cfg))
        lat_result={'lattice_status':'数据缺失'}
        endpoint_rows=[r for r in ends if r['pair_id']==pair and r['reference_set_id']==ref]
        if len([r for r in endpoint_rows if r['role']=='A']) == 1 and len([r for r in endpoint_rows if r['role']=='B'])==1:
            A=next(r for r in endpoint_rows if r['role']=='A')
            B=next(r for r in endpoint_rows if r['role']=='B')
            if not _string(A,'method') or not _string(B,'method'):
                lat_result={'lattice_status':'待核验','reason':'端元参考计算方法缺失'}
            elif _string(A,'method')!=_string(B,'method'):
                lat_result={'lattice_status':'待核验','reason':'端元参考计算方法不一致'}
            elif _positive_status(A) and _positive_status(B):
                try:
                    sa=_load_structure(A,input_dir); sb=_load_structure(B,input_dir)
                    lat_result=lattice_match(sa,sb,c,cfg)
                except (ValueError,OSError,ImportError,TypeError) as exc:
                    lat_result={'lattice_status':'计算失败','reason':str(exc)}
            else:
                lat_result={'lattice_status':'待核验','reason':'端元弛豫或QC未通过'}
        lattice.append(dict(candidate_id=cid,pair_id=pair,reference_set_id=ref,**lat_result))
        row['lattice_status']=lat_result['lattice_status']
        if lat_result.get('max_length_mismatch') is not None:
            row['lattice_mismatch_pct']=100*lat_result['max_length_mismatch']
            row['lattice_angle_difference_deg']=lat_result['max_angle_difference_deg']

        configs=[r for r in alloys if r['candidate_id']==cid and r['reference_set_id']==ref and _number(r['actual_fraction_b']) is not None and abs(float(r['actual_fraction_b'])-float(c['actual_fraction_b']))<1e-6]
        row['available_configurations']=len(configs)
        explicit=sub_cfg['selected_structure_ids'].get(cid)
        selected=[r for r in configs if r['structure_id']==explicit] if explicit else [r for r in configs if _string(r,'seed')==str(sub_cfg['representative_seed'])]
        row.update(selected_seed=sub_cfg['representative_seed'] if not explicit else None,substrate_configurations_evaluated=0)
        if not selected:
            row['selection_status']='representative_missing'
            row['substrate_status']='待补充'
        elif len(selected)>1:
            row['selection_status']='representative_ambiguous'
            row['substrate_status']='待补充'
        else:
            chosen=selected[0]
            row.update(selected_seed=chosen['seed'],selected_structure_id=chosen['structure_id'],selected_structure_sha256=chosen['sha256'])
            if not _positive_status(chosen):
                row['selection_status']='representative_invalid'
                row['substrate_status']='待补充'
            else:
                try:
                    film=_load_structure(chosen,input_dir)
                    row['selection_status']='selected'
                    row['substrate_configurations_evaluated']=1
                    relevant=[]; any_failed=False; any_too_large=False
                    for substrate in sorted(subs,key=lambda x:x.get('substrate_id','')):
                        sid=substrate.get('substrate_id','')
                        if not sid: raise ValueError('substrate_id missing')
                        try:
                            s=_load_structure(substrate,input_dir)
                            from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
                            s=SpacegroupAnalyzer(s, symprec=sub_cfg['symprec_A']).get_conventional_standard_structure()
                            matches=substrate_matches(film,s,sub_cfg, f'{cid}|{chosen["structure_id"]}|{chosen["sha256"]}',sid)
                            for m in matches:
                                m.update(search_config=dict(sub_cfg),candidate_id=cid,structure_id=chosen['structure_id'],structure_sha256=chosen['sha256'],substrate_sha256=substrate['sha256'])
                            all_matches.extend(matches)
                            representative=representative_matches(matches,sub_cfg['preferred_max_principal_strain'],sub_cfg['alternative_max_principal_strain'])
                            for role,match in representative.items():
                                if match: structure_matches.append(dict(candidate_id=cid,substrate_id=sid,role=role,match_id=match['match_id'],film_area_A2=match['film_area_A2'],max_abs_principal_strain=match['max_abs_principal_strain']))
                            if matches:
                                chosen_match=select_consistent_match(matches)
                                if chosen_match: relevant.append(chosen_match)
                            else:
                                # A large SQS surface cell is a scope limitation, not proof of no epitaxy.
                                any_too_large |= min(np.linalg.norm(np.cross(*_plane_vectors(film,h)[0])) for h in miller_indices(sub_cfg['film_max_miller'])) >= sub_cfg['max_area_A2']
                        except (ValueError,OSError,ImportError,TypeError) as exc:
                            any_failed=True
                            failures.append(dict(candidate_id=cid,substrate_id=sid,error=str(exc)))
                    relevant.sort(key=lambda m:(m['max_abs_principal_strain'],m['film_area_A2'],m['substrate_id'],m['match_id']))
                    # Stage 13 presents three distinct substrate recommendations at most.
                    top.extend(relevant[:min(3, int(sub_cfg['top_n']))])
                    selected_match=relevant[0] if relevant else None
                    if selected_match:
                        row.update(substrate_principal_strain_pct=100*selected_match['max_abs_principal_strain'],substrate_status=substrate_grade(selected_match['max_abs_principal_strain'],Thresholds(substrate_preferred=sub_cfg['preferred_max_principal_strain'],substrate_alternative=sub_cfg['alternative_max_principal_strain'])),substrate_id=selected_match['substrate_id'],film_miller=str(selected_match['film_miller']),substrate_miller=str(selected_match['substrate_miller']),match_area_A2=selected_match['film_area_A2'],match_id=selected_match['match_id'])
                    else:
                        row['substrate_status']='待补充' if not subs else '计算失败' if any_failed else '表面原胞超面积上限' if any_too_large else '范围内未找到'
                except (ValueError,OSError,ImportError,TypeError) as exc:
                    row['selection_status']='representative_invalid';row['substrate_status']='待补充'
                    failures.append(dict(candidate_id=cid,error=str(exc)))
        geo_lat=row['lattice_status']; geo_sub=row['substrate_status']
        if geo_lat=='优先' and geo_sub=='优先': row['geometry_grade']='几何优先'
        elif geo_lat in ('优先','备选') and geo_sub in ('优先','备选'): row['geometry_grade']='几何备选'
        elif geo_lat in ('数据缺失','待核验','计算失败') or geo_sub in ('待补充','计算失败'): row['geometry_grade']='几何数据待补充'
        else: row['geometry_grade']='几何需复核'
        row.update(summarize_material_evidence(row))
        row['recommendation_reason']+='；衬底仅使用单代表构型，不证明可实际外延或器件性能'
        main.append(row)
    _write_csv(output_dir/'candidate_evaluation.csv',main,MAIN_COLUMNS)
    _write_csv(output_dir/'lattice_matches.csv',lattice,('candidate_id','pair_id','reference_set_id','lattice_status','reason','max_length_mismatch','max_angle_difference_deg','symmetric_principal_mismatch','transform_b','site_mapping','mapping_residual_A','mapping_count'))
    _write_csv(output_dir/'substrate_top_matches.csv',top,('candidate_id','substrate_id','match_id','structure_id','max_abs_principal_strain','film_area_A2','substrate_area_A2','film_miller','substrate_miller','principal_strains','film_supercell_matrix','substrate_supercell_matrix'))
    _write_csv(output_dir/'structure_matches.csv',structure_matches,('candidate_id','substrate_id','role','match_id','film_area_A2','max_abs_principal_strain'))
    with gzip.open(output_dir/'match_details.jsonl.gz','wt',encoding='utf-8') as fh:
        for match in all_matches:
            fh.write(_safe_json(match)+'\n')
    summary=dict(schema_version=2,config_fingerprint=fingerprint,candidate_count=len(main),matching_solutions=len(all_matches),failures=failures,algorithm='ssscreen_geometry_v2_distinct_planes',scope='single_representative_configuration')
    (output_dir/'summary.json').write_text(_safe_json(summary),encoding='utf-8')
    report=['# Stage 13固溶体候选评价','',
            f'候选数：{len(main)}；已找到几何匹配解：{len(all_matches)}。','',
            EVALUATION_TABLE_MD,'',
            '注：衬底仅评价配置的单代表seed，未计算器件性能、弹性能或真实外延能。',
            '结构及来源缺失不得以零代替。','']
    for r in main:
        report.extend((f"## {r['candidate_id']}",f"综合：{r['candidate_grade']}；几何：{r['geometry_grade']}",f"原因：{r['recommendation_reason']}",''))
    (output_dir/'report.md').write_text('\n'.join(report),encoding='utf-8')
    return summary
