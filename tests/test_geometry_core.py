import numpy as np
import pytest
from ssscreen.geometry_core import (
  lattice_diagnostics,lattice_grade,inplane_principal_strain,miller_indices,
  substrate_grade,representative_matches,select_consistent_match,
)


def test_symmetric_lattice_mismatch_and_axes_rotation():
    a=np.diag([5.,5.,5.]);b=np.diag([5.1,5.,5.])
    v=lattice_diagnostics(a,b)
    assert v['max_length_mismatch']==pytest.approx(2*.1/10.1)
    assert lattice_grade(v)=='优先'
    assert lattice_diagnostics(b,a)['max_length_mismatch']==pytest.approx(v['max_length_mismatch'])
    # rigid rotation is stretch-free if the rows are rotated together
    angle=np.deg2rad(42)
    R=np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1]])
    rotated=lattice_diagnostics(a,a@R)
    assert rotated['symmetric_principal_mismatch']==pytest.approx(0,abs=1e-12)


def test_2d_eng_strain_and_rotation_invariance():
    film=np.array([[5.,0,0],[0,5.,0]])
    sub=np.array([[5.10,0,0],[0,4.9,0]])
    v=inplane_principal_strain(film,sub)
    assert sorted(v['principal_strains'])==pytest.approx([-.02,.02])
    assert substrate_grade(v['max_abs_principal_strain'])=='备选'
    theta=np.deg2rad(23)
    rot=np.array([[np.cos(theta),-np.sin(theta),0],[np.sin(theta),np.cos(theta),0],[0,0,1]])
    reoriented=inplane_principal_strain(film @ rot,sub @ rot)
    assert reoriented['max_abs_principal_strain']==pytest.approx(.02)


def test_shear_and_area_limit_choice():
    f=np.array([[5.,0,0],[0,5.,0]])
    s=np.array([[5.,1.,0],[0,5.,0]])
    diag=inplane_principal_strain(f,s)
    assert diag['max_abs_principal_strain'] > .03
    matches=[dict(match_id='large_area_small_strain',film_area_A2=60,max_abs_principal_strain=.003),
             dict(match_id='small_area_larger_strain',film_area_A2=20,max_abs_principal_strain=.008)]
    chosen=select_consistent_match(matches)
    assert chosen['match_id']=='large_area_small_strain'
    reps=representative_matches(matches)
    assert reps['min_strain']['match_id']=='large_area_small_strain'
    assert reps['min_area']['match_id']=='small_area_larger_strain'


def test_equal_strain_prefers_smaller_area():
    matches = [
        dict(match_id='large', film_area_A2=60, max_abs_principal_strain=.003),
        dict(match_id='small', film_area_A2=20, max_abs_principal_strain=.003),
    ]
    assert select_consistent_match(matches)['match_id'] == 'small'


def test_millers_and_thresholds():
    assert len(miller_indices(1))==13
    assert substrate_grade(.01)=='优先'
    assert substrate_grade(.03)=='备选'
    assert substrate_grade(.03000001)=='较高应变'
