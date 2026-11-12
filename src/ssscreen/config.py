"""Central configuration: numerical thresholds and element-exclusion lists.

All magic numbers that were scattered as inline literals across the source
notebooks live here as named, documented attributes of :class:`Thresholds`.
This is the single place to audit or tune the screening criteria.

Default values reproduce the research workspace defaults
(``pair-screening/screening-binary.ipynb`` and ``pairing_mbj_gaps_binary.ipynb``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace

# ---------------------------------------------------------------------------
# Element exclusion
# ---------------------------------------------------------------------------
# Default excluded elements: radioactive/toxic, common transition metals that
# rarely form the target narrow-gap semiconductors, and the lanthanide +
# actinide series (f-electron complexity, magnetism).
# Source: pair-screening/screening-binary.ipynb cell 29.
_DEFAULT_EXCLUDED = [
    # radioactive / toxic
    "U",
    "Th",
    "Po",
    "Tl",
    "Hg",
    "Np",
    "Pu",
    "Pa",
    "Pr",
    # transition metals (excluded in the binary screen)
    "Ti",
    "Fe",
    "Co",
    "Ni",
    "Mn",
    "Cr",
    "V",
    # non-metals that distort the chemistry
    "H",
    # lanthanides
    "La",
    "Ce",
    "Nd",
    "Pm",
    "Sm",
    "Eu",
    "Gd",
    "Tb",
    "Dy",
    "Ho",
    "Er",
    "Tm",
    "Yb",
    "Lu",
]

#: Frozen set used by :func:`ssscreen.pair.filters.apply_element_exclusion`.
DEFAULT_EXCLUDED_ELEMENTS: frozenset[str] = frozenset(_DEFAULT_EXCLUDED)

# Live Materials Project requests include full crystal structures and can exceed
# mp-api's 20-second default on shared networks. Keep these operational limits
# named and auditable alongside the scientific thresholds.
MP_API_REQUEST_TIMEOUT_SECONDS = 120
MP_API_CHUNK_SIZE = 500
MP_API_PAGE_RETRIES = 3
MP_API_RETRY_BACKOFF_SECONDS = 2.0

# Preserve the existing Stage 05 export scope when the GUI bundles its outputs.
GAP_EXPORT_MAX_ATOMS = 30
GAP_PENDING_METHOD = "external-method-pending-v1"


# ---------------------------------------------------------------------------
# Permutation indices for composition-template grouping
# ---------------------------------------------------------------------------
# For a reduced composition with ``nelems`` elements, the orderings in which
# each element is treated as the variable `X` site. Mirrors
# screening-binary.ipynb cell 15 ([[0,1],[1,0]]) and
# screening-tenary.ipynb cell 5 ([[0,1,2],[0,2,1],[1,2,0]]).
_PERMUTATIONS: dict[int, list[list[int]]] = {
    2: [[0, 1], [1, 0]],
    3: [[0, 1, 2], [0, 2, 1], [1, 2, 0]],
}


def composition_permutations(nelems: int) -> list[list[int]]:
    """Return the per-element-as-X permutations for a reduced composition.

    The last index in each permutation is the variable element; the leading
    indices are the fixed (spectator) elements.
    """
    if nelems not in _PERMUTATIONS:
        raise ValueError(
            f"Composition-template grouping only supports nelems in {sorted(_PERMUTATIONS)}; "
            f"got nelems={nelems}."
        )
    return [list(p) for p in _PERMUTATIONS[nelems]]


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SelectionThresholds:
    """Thresholds for the initial data selection (stage 1).

    Attributes mirror the filters in ``screening-binary.ipynb`` cells 9-12.
    """

    #: Number of elements in the reduced composition (2=binary, 3=ternary).
    nelems: int = 2
    #: Maximum PBE band gap (eV) to keep a material. Default 1.0 (cell 12).
    max_bandgap: float = 1.0
    #: Maximum energy above hull (eV/atom). Use a small negative value to keep
    #: only on-hull structures (``e_hull <= 0``), matching cell 12's ``<= 0.0``;
    #: use ``0.01`` to mirror ``MPOffline``'s query predicate.
    max_e_hull: float = 0.0


@dataclass(frozen=True)
class GroupThresholds:
    """Thresholds applied to environment groups (stages 3-4).

    Mirrors ``screening-binary.ipynb`` cells 26-29.
    """

    #: Minimum number of distinct X elements required in a group after
    #: environment matching (cell 26: ``len(np.unique(group.X_element)) > 1``).
    min_x_diversity: int = 2
    #: Require at least one zero-gap member (cell 29: ``any(x == 0 ...)``).
    require_zero_gap_member: bool = True


@dataclass(frozen=True)
class PairThresholds:
    """Thresholds for the pair-enumeration stage (stage 5).

    Mirrors ``pairing_mbj_gaps_binary.ipynb`` cells 6 and 8. Two distinct sets:
    the *group validity* rule (``gaps_valid``) and the *pair* rule.
    """

    # --- gaps_valid (cell 6): group must contain both kinds of member ---
    #: A "low" member has gap below this (eV). Default 0.15.
    low_gap: float = 0.15
    #: A "direct small-gap" member has gap in (direct_min, direct_max) eV.
    direct_min: float = 0.15
    direct_max: float = 1.5

    # --- pair enumeration (cell 8) ---
    #: A pair is kept if some member is below this (eV). Default 0.3.
    pair_any_below: float = 0.3
    #: ...and some member is above this (eV). Default 0.2.
    pair_any_above: float = 0.2
    #: ...and neither member exceeds this (eV). Default 0.8.
    pair_both_below: float = 0.8


@dataclass(frozen=True)
class MLPRelaxationSettings:
    """Numerical settings and quality-control bounds for Stage 7 MLP relaxation."""

    #: Atomic-force convergence tolerance in eV/Angstrom.
    force_tolerance: float = 0.03
    #: Maximum number of geometry-optimization steps.
    max_steps: int = 500
    #: Warn when the final volume is less than this fraction of the initial volume.
    min_volume_ratio: float = 0.5
    #: Warn when the final volume exceeds this multiple of the initial volume.
    max_volume_ratio: float = 2.0
    #: Warn when distinct atoms are closer than this distance in Angstrom.
    min_distance: float = 0.5


@dataclass(frozen=True)
class PhononSettings:
    """Numerical defaults for Stage 9 finite-displacement phonons."""

    #: Cartesian displacement amplitude in Angstrom.
    displacement_distance: float = 0.01
    #: Phonopy symmetry tolerance.
    symmetry_tolerance: float = 1e-5
    #: Automatic diagonal supercells target at least this lattice-vector length.
    min_supercell_length: float = 10.0
    #: Refuse automatically or explicitly generated supercells above this size.
    max_supercell_atoms: int = 300
    #: Gamma-centered q-point mesh used for the dynamical-stability screen.
    mesh: tuple[int, int, int] = (20, 20, 20)
    #: Number of q points per high-symmetry path segment.
    band_points: int = 101
    #: Frequencies below minus this tolerance are significant imaginary modes.
    imaginary_tolerance_thz: float = 0.1
    #: Maximum accepted Stage 7 residual force before phonon generation.
    max_input_force: float = 0.02


@dataclass(frozen=True)
class CompetingPhaseSettings:
    """Defaults for Stage 10 MP competing-phase and convex-hull screening."""

    #: Materials Project thermo scheme used only to select source structures.
    thermo_type: str = "GGA_GGA+U_R2SCAN"
    #: Fetch MP structures no farther than this from the selected MP hull (eV/atom).
    max_mp_energy_above_hull: float = 0.1
    #: Refuse a primitive competing-phase structure above this atom count.
    max_competing_phase_atoms: int = 200
    #: Candidate energies at or below this MLP hull distance remain screening candidates.
    screening_cutoff_ev_per_atom: float = 0.1
    #: Numerical tolerance used to distinguish an on-hull candidate from metastability.
    numerical_tolerance_ev_per_atom: float = 1e-6
    #: Current Materials Project helper supports at most nine elements per parent system.
    max_query_elements: int = 9
    #: Per-request and per-chemical-system wall-clock timeout for MP API calls.
    api_timeout_seconds: float = 30.0


@dataclass(frozen=True)
class RecommendationSettings:
    """Conservative Stage 11 decision-support thresholds.

    These values are triage defaults rather than universal stability criteria.
    Stage 11 records them in every summary and exposes them as CLI options.
    """

    #: Mixing enthalpies at or below this remain a positive screening signal.
    promising_max_mixing_enthalpy_mev_per_atom: float = 25.0
    #: Mixing enthalpies above this are an explicit low-priority signal.
    low_priority_mixing_enthalpy_mev_per_atom: float = 50.0
    #: Same-MLIP hull distances at or below this remain a positive signal.
    promising_max_hull_ev_per_atom: float = 0.025
    #: Hull distances above this are an explicit low-priority signal.
    low_priority_hull_ev_per_atom: float = 0.1
    #: Tolerance for checking pair-table gaps against normalized gap results.
    gap_consistency_tolerance_ev: float = 1e-6


@dataclass(frozen=True)
class Thresholds:
    """Aggregate of all screening thresholds.

    Build with :meth:`default` for the research defaults, or :meth:`with_nelems`
    to switch binary <-> ternary while keeping the rest.
    """

    selection: SelectionThresholds = field(default_factory=SelectionThresholds)
    group: GroupThresholds = field(default_factory=GroupThresholds)
    pair: PairThresholds = field(default_factory=PairThresholds)
    #: Maximum number of atoms in the primitive cell kept for DFT (cell 36/41:
    #: binary uses 30, ternary uses 45).
    max_natoms: int = 30
    #: Elements to exclude from A-positions and the X-position.
    excluded_elements: frozenset[str] = DEFAULT_EXCLUDED_ELEMENTS

    @staticmethod
    def default(nelems: int = 2) -> Thresholds:
        """Research defaults for the given element count."""
        max_natoms = 30 if nelems == 2 else 45
        return Thresholds(
            selection=SelectionThresholds(nelems=nelems),
            max_natoms=max_natoms,
        )

    def with_nelems(self, nelems: int) -> Thresholds:
        """Return a copy with ``nelems`` (and the matching natoms cap) set."""
        return replace(
            self,
            selection=replace(self.selection, nelems=nelems),
            max_natoms=30 if nelems == 2 else 45,
        )

    @property
    def excluded(self) -> set[str]:
        """The excluded-element set as a plain ``set`` (for easy membership tests)."""
        return set(self.excluded_elements)


def coerce_excluded(extra: Sequence[str] | None) -> frozenset[str]:
    """Helper for the CLI: merge user-supplied extras into the default set."""
    base = set(DEFAULT_EXCLUDED_ELEMENTS)
    if extra:
        base.update(extra)
    return frozenset(base)
