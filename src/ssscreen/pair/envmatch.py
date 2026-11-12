"""Group materials by robocrystallographer local-environment fingerprints.

This is the scientific core of the pipeline. Structures that share a
composition template (``AxByX``) are further grouped by their local bonding
environment: each crystallographic site is described by the polyhedral formula
and geometry type reported by ``robocrys``. The variable (alloyed) element is
relabeled to a placeholder ``X`` in the descriptor, so that chemically distinct
but structurally identical prototypes collapse into one group.

Ported (faithfully, with fixes) from ``pair-screening/envmatch.py``.

Fixes vs. upstream:
  * ``StructureGroup.__getitem___`` (3 trailing underscores) was a no-op dunder;
    renamed to a working ``__getitem__``.
  * Added ``band_gaps`` as a first-class field (upstream bolted it on after
    construction, which made the dataclass incomplete).
  * Added type hints and docstrings; ``group_similar_structures`` now accepts
    the array-like ``mp_ids`` it always read.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import numpy as np
from pymatgen.core import Composition, Species


def find_unique_envs(condense_dicts: Iterable[dict | None]) -> list[list]:
    """Extract the local environments of each structure's centre atoms.

    Parameters
    ----------
    condense_dicts
        Iterable of ``robocrys`` condensed-structure dicts (or ``None`` where
        condensation failed). Each dict's ``sites`` maps a site index to a
        record with ``element``, ``poly_formula`` and ``geometry.type``.

    Returns
    -------
    list of ``[formula, env]`` pairs (or ``[None, None]`` for missing dicts),
    where ``env`` maps element symbol -> set of ``(poly_formula, geometry_type)``
    tuples. The element string is stripped of any oxidation-state suffix
    (e.g. ``Hf1.5+`` -> ``Hf``).

    Mirrors ``pair-screening/envmatch.py:8-25``.
    """
    envs: list[list] = []
    for cs in condense_dicts:
        if cs is None:
            envs.append([None, None])
            continue
        comp = Composition(cs["formula"])
        env: dict[str, set[tuple[str, str]]] = {str(key): set() for key in comp}
        for site in cs["sites"].values():
            pform = site["poly_formula"]
            ptype = site["geometry"]["type"]
            # Strip oxidation-state suffix such as "Hf1.5+" -> "Hf".
            elem = re.match(r"[A-Z][a-z]?", site["element"]).group(0)
            env[Species(elem).symbol].add((str(pform), ptype))
        envs.append([cs["formula"], env])
    return envs


def swap_elem_by_X(name: str, elem: str) -> str:
    """Replace ``elem`` by the placeholder ``X`` in a polyhedral formula.

    Example: ``"CoCa3"`` with ``elem="Ca"`` -> ``"CoX3"``. If ``elem`` is not
    present, the formula is returned unchanged.

    Mirrors ``pair-screening/envmatch.py:27-35``.
    """
    temp_comp = {key.symbol: value for key, value in Composition(name).items()}
    if elem in temp_comp:
        temp_comp["X"] = temp_comp[elem]
        temp_comp.pop(elem)
        name = Composition(temp_comp).formula
    return name


def group_similar_structures(
    envs: Sequence[Sequence],
    comp_template: str,
    mp_ids: Sequence[str],
) -> list[StructureGroup]:
    """Collapse a set of structures into environment-fingerprint groups.

    Parameters
    ----------
    envs
        Output of :func:`find_unique_envs`: a list of ``[formula, env]`` pairs.
    comp_template
        Composition template like ``"CaX3"`` — the spectator elements are read
        from it (everything except ``X``).
    mp_ids
        Material identifiers parallel to ``envs`` (e.g. ``mp-1234``,
        ``wbm-5678``).

    Returns
    -------
    list of :class:`StructureGroup`, one per unique environment with more than
    one member. Each group records the member indices, the (constant) spectator
    A-elements, the per-member variable X-elements, formulas, mp_ids, band gaps
    (empty until :func:`~ssscreen.pair.grouping.attach_band_gaps` fills them),
    and the descriptor string.

    Mirrors ``pair-screening/envmatch.py:37-108``.
    """
    reprs: list[str] = []
    aelems: list = []
    comps: list = []
    xelems: list = []

    spectator_elements = [x.symbol for x in Composition(comp_template).keys() if x.symbol != "X"]

    for comp, item in envs:
        # Missing condensed info: assign a unique random descriptor so this
        # structure never matches any other (mirrors upstream behaviour).
        if item is None:
            reprs.append(str(np.random.rand()))
            aelems.append("MISSING")
            comps.append("MISSING")
            xelems.append("MISSING")
            continue

        # The variable element is the one not among the spectators.
        x_candidate = list(filter(lambda x: x not in spectator_elements, item))
        assert len(x_candidate) == 1, (
            f"Expected exactly one variable element in template {comp_template!r}, "
            f"got {x_candidate} from env keys {list(item)}"
        )
        elem = x_candidate[0]

        # Descriptor: the X-site's own environment, then each spectator's
        # environment with X substituted back into poly_formula names.
        repr = str(sorted(list(item[elem]))) + "|"
        rest: list[str] = []
        for x in spectator_elements:
            rest.append(x)
            normalized_environments = []
            for name, geo_type in item[x]:
                if name != "None":
                    name = swap_elem_by_X(name, elem)
                normalized_environments.append(name + "," + geo_type)
            # Ported from the audited 2026-09-23 envmatch_canonical snapshot:
            # set iteration (and pre-substitution order) is not a fingerprint.
            rest.extend(sorted(normalized_environments))
        repr = repr + "|".join(rest)

        reprs.append(repr)
        aelems.append(sorted(spectator_elements))
        xelems.append(elem)
        comps.append(comp)

    aelems_arr = np.array(aelems, dtype=object)
    comps_arr = np.array(comps, dtype=object)
    xelems_arr = np.array(xelems, dtype=object)

    _, unique_idx, labels = np.unique(reprs, return_index=True, return_inverse=True)

    valid_groups: list[StructureGroup] = []
    for idx in unique_idx:
        group_id = labels[idx]
        mask = labels == group_id
        nin_group = int(sum(mask))
        if nin_group > 1:
            valid_groups.append(
                StructureGroup(
                    entry_idx=np.where(mask)[0].tolist(),
                    A_elements=aelems_arr[mask].tolist(),
                    compositions=comps_arr[mask].tolist(),
                    group_size=nin_group,
                    X_element=xelems_arr[mask].tolist(),
                    mp_ids=list(np.array(mp_ids)[mask]),
                    group_repr=reprs[idx],
                )
            )
    return valid_groups


@dataclass
class StructureGroup:
    """A group of structures sharing an environment fingerprint.

    Attributes:
        entry_idx: indices of members within the input ``envs`` list.
        A_elements: spectator elements common to all members
            (e.g. ``["Ca"]``); constant within a group.
        compositions: per-member chemical formulas.
        group_size: number of members.
        X_element: per-member variable element symbol (the alloyed site).
        mp_ids: per-member material identifiers.
        group_repr: the environment-descriptor string shared by all members.
        band_gaps: per-member band gaps (eV); filled in later by
            :func:`~ssscreen.pair.grouping.attach_band_gaps`.
    """

    entry_idx: list[int]
    A_elements: list
    compositions: list
    group_size: int
    X_element: list
    mp_ids: list
    group_repr: str
    band_gaps: list = field(default_factory=list)

    def __getitem__(self, key: str):
        # NOTE: upstream had ``__getitem___`` (3 trailing underscores) which
        # silently did nothing; this is the corrected version.
        return getattr(self, key)

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict (dropping the descriptor)."""
        return {
            "entry_idx": self.entry_idx,
            "A_elements": self.A_elements,
            "compositions": self.compositions,
            "X_element": self.X_element,
            "mp_ids": self.mp_ids,
            "band_gaps": self.band_gaps,
            "group_size": self.group_size,
        }
