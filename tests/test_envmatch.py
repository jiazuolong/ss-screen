"""Tests for the envmatch core (ported from pair-screening/envmatch.py)."""

from __future__ import annotations

from ssscreen.pair.envmatch import (
    StructureGroup,
    find_unique_envs,
    group_similar_structures,
    swap_elem_by_X,
)


# ---------------------------------------------------------------------------
# swap_elem_by_X
# ---------------------------------------------------------------------------
def test_swap_elem_by_X_basic():
    """The function swaps the named element for the placeholder X.

    The exact formula formatting (element ordering, explicit ``1`` counts)
    depends on pymatgen's ``Composition.formula``, so we assert on content,
    not string equality.
    """
    from pymatgen.core import Composition

    out = swap_elem_by_X("CoCa3", "Ca")
    out_comp = Composition(out)
    assert out_comp["X"] == 3
    assert out_comp["Co"] == 1
    assert "Ca" not in out_comp


def test_swap_elem_by_X_no_match_returns_unchanged():
    assert swap_elem_by_X("CoO3", "Ca") == "CoO3"


def test_swap_elem_by_X_single_element():
    # Swapping the only element leaves a pure-X formula.
    out = swap_elem_by_X("Ca3", "Ca")
    assert "X" in out and "Ca" not in out


# ---------------------------------------------------------------------------
# find_unique_envs
# ---------------------------------------------------------------------------
def test_find_unique_envs_none_entry():
    out = find_unique_envs([None])
    assert out == [[None, None]]


def test_find_unique_envs_real(cese2_condensed):
    """Two CeSe2 polymorphs should expose Ce and Se environments."""
    dicts = [cese2_condensed["mp-1080296"], cese2_condensed["mp-1080351"]]
    envs = find_unique_envs(dicts)
    assert len(envs) == 2
    for formula, env in envs:
        assert formula == "CeSe2"
        assert set(env.keys()) == {"Ce", "Se"}
        # Each environment is a set of (poly_formula, geometry) tuples.
        for entries in env.values():
            assert isinstance(entries, set)


def test_find_unique_envs_strips_oxidation_suffix(cese2_condensed):
    """Element 'Ce4+' must be reduced to 'Ce' in the env keys."""
    envs = find_unique_envs([cese2_condensed["mp-1080265"]])
    _, env = envs[0]
    assert "Ce4+" not in env
    assert "Ce" in env


# ---------------------------------------------------------------------------
# group_similar_structures
# ---------------------------------------------------------------------------
def test_group_collapses_matching_polymorphs(cese2_condensed):
    """mp-1080296 and mp-1080351 share an identical environment (CeSe4
    tetrahedron + linear Se) -> one group of size 2. mp-1080265 has a different
    Se geometry (bent 120°), and mp-1080248 is wholly different, so neither
    joins the group.
    """
    dicts = [
        cese2_condensed["mp-1080296"],
        cese2_condensed["mp-1080351"],
        cese2_condensed["mp-1080265"],
        cese2_condensed["mp-1080248"],
    ]
    mp_ids = ["mp-1080296", "mp-1080351", "mp-1080265", "mp-1080248"]
    envs = find_unique_envs(dicts)
    groups = group_similar_structures(envs, "CeX2", mp_ids)

    # Exactly one multi-member group (the two identical polymorphs).
    assert len(groups) == 1
    g = groups[0]
    assert g.group_size == 2
    assert set(g.mp_ids) == {"mp-1080296", "mp-1080351"}
    # The variable element is Se (the X) for both members.
    assert all(x == "Se" for x in g.X_element)
    # Spectator element is Ce.
    assert g.A_elements[0] == ["Ce"]


def test_group_requires_more_than_one_member(cese2_condensed):
    """A unique environment with a single member yields no group."""
    envs = find_unique_envs([cese2_condensed["mp-1080248"]])
    groups = group_similar_structures(envs, "CeX2", ["mp-1080248"])
    assert groups == []


def test_group_missing_env_never_matches(cese2_condensed):
    """A missing condensed dict gets a random descriptor -> never groups."""
    dicts = [cese2_condensed["mp-1080265"], None]
    envs = find_unique_envs(dicts)
    groups = group_similar_structures(envs, "CeX2", ["mp-1080265", "mp-missing"])
    assert groups == []


def test_spectator_fingerprint_is_sorted_after_variable_substitution():
    """Equivalent environments must match despite opposite iteration order."""
    envs = [
        [
            "CaS",
            {"Ca": [("S4", "tetrahedral"), ("S6", "octahedral")], "S": {("Ca6", "octahedral")}},
        ],
        [
            "CaSe",
            {"Ca": [("Se6", "octahedral"), ("Se4", "tetrahedral")], "Se": {("Ca6", "octahedral")}},
        ],
    ]
    groups = group_similar_structures(envs, "CaX", ["a", "b"])
    assert len(groups) == 1
    assert groups[0].mp_ids == ["a", "b"]
    assert groups[0].X_element == ["S", "Se"]


# ---------------------------------------------------------------------------
# StructureGroup dataclass
# ---------------------------------------------------------------------------
def test_structure_group_getitem_works():
    """Regression for the upstream ``__getitem___`` typo (3 trailing underscores)."""
    g = StructureGroup(
        entry_idx=[0, 1],
        A_elements=[["Ca"]],
        compositions=["CaS", "CaSe"],
        group_size=2,
        X_element=["S", "Se"],
        mp_ids=["mp-1", "mp-2"],
        group_repr="...",
        band_gaps=[0.0, 0.3],
    )
    assert g["group_size"] == 2
    assert g["mp_ids"] == ["mp-1", "mp-2"]


def test_structure_group_to_dict_roundtrip():
    g = StructureGroup(
        entry_idx=[0],
        A_elements=[["Ca"]],
        compositions=["CaS"],
        group_size=1,
        X_element=["S"],
        mp_ids=["mp-1"],
        group_repr="x",
    )
    d = g.to_dict()
    assert d["group_size"] == 1
    assert "group_repr" not in d
    assert d["band_gaps"] == []
