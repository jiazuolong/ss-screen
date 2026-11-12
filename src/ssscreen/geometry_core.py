"""Numerically auditable lattice and epitaxial in-plane engineering strains.

Row-lattice convention throughout: lattice/surface vectors are stored as rows.
For real structures, geometry_pipeline uses pymatgen for atom mappings and ZSL.
This module contains no file or GUI dependencies, and is analytically testable.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Thresholds:
    lattice_preferred: float = 0.03
    lattice_alternative: float = 0.05
    angle_deg: float = 1.0
    substrate_preferred: float = 0.01
    substrate_alternative: float = 0.03

    def __post_init__(self) -> None:
        vals = (self.lattice_preferred, self.lattice_alternative, self.angle_deg,
                self.substrate_preferred, self.substrate_alternative)
        if not all(math.isfinite(x) and x >= 0 for x in vals):
            raise ValueError('Thresholds must be non-negative and finite')
        if self.lattice_preferred > self.lattice_alternative:
            raise ValueError('Lattice preferred must not exceed alternative')
        if self.substrate_preferred > self.substrate_alternative:
            raise ValueError('Substrate preferred must not exceed alternative')


def _valid_matrix(data: object, shape: tuple[int, int]) -> np.ndarray:
    a = np.asarray(data, dtype=float)
    if a.shape != shape or not np.isfinite(a).all():
        raise ValueError(f'Expected finite {shape} matrix')
    if shape == (3, 3) and abs(np.linalg.det(a)) < 1e-10:
        raise ValueError('Singular three-dimensional lattice')
    if shape == (2, 3) and np.linalg.norm(np.cross(a[0], a[1])) < 1e-10:
        raise ValueError('Degenerate surface basis')
    return a


def lattice_parameters(lattice: object) -> tuple[np.ndarray, np.ndarray]:
    m = _valid_matrix(lattice, (3, 3))
    a, b, c = m
    lengths = np.linalg.norm(m, axis=1)
    def angle(u: np.ndarray, v: np.ndarray) -> float:
        cosine = np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v))
        return float(np.degrees(np.arccos(np.clip(cosine, -1, 1))))
    return lengths, np.array([angle(b,c), angle(a,c), angle(a,b)])


def principal_stretches_3d(lattice_a: object, lattice_b: object) -> np.ndarray:
    a, b = _valid_matrix(lattice_a, (3,3)), _valid_matrix(lattice_b, (3,3))
    F = np.linalg.solve(a, b).T  # F @ a.T == b.T, rotation invariant
    return np.linalg.svd(F, compute_uv=False)


def lattice_diagnostics(lattice_a: object, lattice_b: object) -> dict[str, object]:
    la, aa = lattice_parameters(lattice_a)
    lb, ab = lattice_parameters(lattice_b)
    mismatch = 2 * np.abs(la - lb) / (la + lb)
    stretch = principal_stretches_3d(lattice_a, lattice_b)
    # Symmetric stretch diagnostic includes shear and is not a replacement
    # for corresponding a/b/c length mismatch.
    sym_stretch = 2 * np.abs(stretch - 1) / (stretch + 1)
    return {
        'length_mismatch': mismatch.tolist(),
        'max_length_mismatch': float(max(mismatch)),
        'angle_difference_deg': np.abs(aa-ab).tolist(),
        'max_angle_difference_deg': float(max(np.abs(aa-ab))),
        'symmetric_principal_mismatch': float(max(sym_stretch)),
        'principal_stretches': stretch.tolist(),
        'volume_ratio': float(abs(np.linalg.det(lattice_b)/np.linalg.det(lattice_a))),
        'F_3d': np.linalg.solve(np.asarray(lattice_a, float), np.asarray(lattice_b, float)).T.tolist(),
    }


def lattice_grade(d: dict[str, object], thresholds: Thresholds = Thresholds()) -> str:
    length = float(d['max_length_mismatch'])
    principal = float(d['symmetric_principal_mismatch'])
    angle = float(d['max_angle_difference_deg'])
    # Full-deformation grading must be consistent with length grading.
    def bracket(x: float) -> int:
        return 0 if x <= thresholds.lattice_preferred else 1 if x <= thresholds.lattice_alternative else 2
    if angle > thresholds.angle_deg or bracket(length) != bracket(principal):
        return '待核验'
    return ('优先', '备选', '较大失配风险')[bracket(length)]


def _orthonormal_plane(surface: object) -> np.ndarray:
    v = _valid_matrix(surface, (2, 3))
    e1 = v[0] / np.linalg.norm(v[0])
    normal = np.cross(v[0], v[1])
    normal /= np.linalg.norm(normal)
    e2 = np.cross(normal, e1)
    B = np.array([[np.dot(v[0], e1), np.dot(v[0], e2)],
                  [np.dot(v[1], e1), np.dot(v[1], e2)]])
    return B


def inplane_principal_strain(film_vectors: object, substrate_vectors: object) -> dict[str, object]:
    film = _valid_matrix(film_vectors, (2,3))
    sub = _valid_matrix(substrate_vectors, (2,3))
    Bf, Bs = _orthonormal_plane(film), _orthonormal_plane(sub)
    F = np.linalg.solve(Bf, Bs).T
    stretches = np.linalg.svd(F, compute_uv=False)
    engineering = stretches - 1.0
    # Independent generalized Gram check: Gs u = lambda^2 Gf u.
    Gf, Gs = film @ film.T, sub @ sub.T
    C = np.linalg.cholesky(Gf)
    eigvals = np.linalg.eigvalsh(np.linalg.solve(C, Gs) @ np.linalg.inv(C.T))
    if not np.allclose(np.sort(stretches ** 2), np.sort(eigvals), rtol=1e-8, atol=1e-10):
        raise ValueError('Gram / SVD strain verification conflict')
    return {
        'principal_strains': engineering.tolist(),
        'principal_stretches': stretches.tolist(),
        'max_abs_principal_strain': float(max(abs(engineering))),
        'film_area_A2': float(np.linalg.norm(np.cross(film[0], film[1]))),
        'substrate_area_A2': float(np.linalg.norm(np.cross(sub[0], sub[1]))),
        'F_2d': F.tolist(),
        'gram_eigenvalues': eigvals.tolist(),
    }


def substrate_grade(strain: float | None, thresholds: Thresholds = Thresholds()) -> str:
    if strain is None:
        return '待补充'
    if not math.isfinite(strain) or strain < 0:
        raise ValueError('Strain must be finite and non-negative')
    if strain <= thresholds.substrate_preferred:
        return '优先'
    if strain <= thresholds.substrate_alternative:
        return '备选'
    return '较高应变'


def miller_indices(max_index: int) -> list[tuple[int,int,int]]:
    if not 1 <= max_index <= 3:
        raise ValueError('Miller range must be between 1 and 3')
    millers = set()
    for triple in itertools.product(range(-max_index,max_index+1), repeat=3):
        if triple == (0,0,0) or math.gcd(*triple) != 1:
            continue
        first = next(x for x in triple if x)
        adjusted = tuple(-x for x in triple) if first < 0 else triple
        millers.add(adjusted)
    return sorted(millers)


def select_consistent_match(matches: list[dict[str, object]]) -> dict[str, object] | None:
    """Choose ONE match by minimum maximum absolute principal strain.

    Never combine the area of one match with the strain of another.
    """
    if not matches:
        return None
    def key(m: dict[str, object]) -> tuple:
        strain = float(m['max_abs_principal_strain'])
        return (strain, float(m['film_area_A2']), str(m['match_id']))
    return min(matches, key=key)


def representative_matches(matches: list[dict[str, object]], preferred: float = 0.01,
                           alternative: float = 0.03) -> dict[str, dict[str, object] | None]:
    def small_area(rows: list[dict[str, object]]) -> dict[str, object] | None:
        return min(rows, key=lambda m: (float(m['film_area_A2']), float(m['max_abs_principal_strain']),str(m['match_id']))) if rows else None
    return {
        'min_area': small_area(matches),
        'min_strain': min(matches, key=lambda m: (float(m['max_abs_principal_strain']), float(m['film_area_A2']), str(m['match_id']))) if matches else None,
        'min_area_le_1pct': small_area([m for m in matches if float(m['max_abs_principal_strain']) <= preferred]),
        'min_area_le_3pct': small_area([m for m in matches if float(m['max_abs_principal_strain']) <= alternative]),
    }
