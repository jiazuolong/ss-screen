"""Input integrity and structure correspondence for the dated MP replay route."""

import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from click.testing import CliRunner
from pymatgen.core import Lattice, Structure

from ssscreen.cli.app import cli
from ssscreen.mbj_replay import verify_manifest_files
from ssscreen.mp_reproduction import (
    DATABASE_SHA,
    PROFILE,
    checked_members,
    extract_database,
    geometry_agrees,
    input_structure_hash,
    load_descriptor_cache,
)


def test_mp_zip_extracts_verified_database(tmp_path):
    archive = tmp_path / "mp.zip"
    raw = b"tiny SQLite stand-in for extraction integrity only"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("mp/default.db", raw)
    dest = tmp_path / "new/default.db"
    extract_database(
        archive, dest, expected_sha=hashlib.sha256(raw).hexdigest(), expected_size=len(raw)
    )
    assert dest.read_bytes() == raw
    with pytest.raises(ValueError, match="already exists"):
        extract_database(archive, dest)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/absolute", "mp\\file"])
def test_zip_unsafe_names_rejected(tmp_path, name):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(name, "no")
    with zipfile.ZipFile(archive) as z, pytest.raises(ValueError, match="Unsafe"):
        checked_members(z)


def test_database_wrong_sha_rejected(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("mp/default.db", "bad")
    with pytest.raises(ValueError, match="SHA differs"):
        extract_database(archive, tmp_path / "db", expected_size=3, expected_sha="0" * 64)


def make_cache(path: Path, structure: Structure, raw: bytes = b"{}") -> None:
    manifest = {
        "profile": PROFILE,
        "database_sha256": DATABASE_SHA,
        "materials": {
            "mp-test": {
                "input_structure_sha256": input_structure_hash(structure),
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        },
    }
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("cache_manifest.json", json.dumps(manifest))
        z.writestr("condensed/mp-test.json", raw)


def test_cache_requires_same_input_structure(tmp_path):
    structure = Structure(Lattice.cubic(3), ["Si"], [[0, 0, 0]])
    archive = tmp_path / "cache.zip"
    make_cache(archive, structure)
    assert load_descriptor_cache(archive, {"mp-test": structure}, tmp_path / "valid") == 1
    changed = Structure(Lattice.cubic(4), ["Si"], [[0, 0, 0]])
    with pytest.raises(ValueError, match="input structure differs"):
        load_descriptor_cache(archive, {"mp-test": changed}, tmp_path / "wrong")


def test_cache_rejects_changed_descriptor_bytes(tmp_path):
    structure = Structure(Lattice.cubic(3), ["Si"], [[0, 0, 0]])
    archive = tmp_path / "cache.zip"
    make_cache(archive, structure)
    with zipfile.ZipFile(archive) as z:
        manifest = z.read("cache_manifest.json")
    broken = tmp_path / "changed.zip"
    with zipfile.ZipFile(broken, "w") as z:
        z.writestr("cache_manifest.json", manifest)
        z.writestr("condensed/mp-test.json", '{"changed":true}')
    with pytest.raises(ValueError, match="descriptor differs"):
        load_descriptor_cache(broken, {"mp-test": structure}, tmp_path / "wrong")


def test_geometry_accepts_representation_not_rescaling_or_site_property_changes():
    local = Structure(Lattice.cubic(3), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
    assert geometry_agrees(local.as_dict(), local.as_dict()) == "primary_fields_equal"
    translated = local.copy()
    translated.translate_sites([0, 1], [0.25, 0.25, 0.25])
    assert geometry_agrees(local.as_dict(), translated.as_dict()).startswith("strict_periodic")
    changed = Structure(Lattice.cubic(4), ["Na", "Cl"], [[0, 0, 0], [0.5, 0.5, 0.5]])
    with pytest.raises(ValueError, match="geometry differs"):
        geometry_agrees(local.as_dict(), changed.as_dict())
    changed = local.copy()
    changed.add_site_property("magmom", [1, 0])
    with pytest.raises(ValueError, match="site attributes differ"):
        geometry_agrees(local.as_dict(), changed.as_dict())


def test_cli_requires_external_mbj_results(tmp_path):
    archive = tmp_path / "mp.zip"
    archive.write_bytes(b"not extracted")
    result = CliRunner().invoke(
        cli, ["mp-reproduce", "--mp-zip", str(archive), "--output-dir", str(tmp_path / "out")]
    )
    assert result.exit_code != 0
    assert "--mbj-bundle" in result.output
    assert not (tmp_path / "out").exists()


def test_geometry_checks_original_labels_despite_supercell_generated_suffixes():
    local = Structure(
        Lattice.cubic(3),
        ["Na", "Na", "Cl", "Cl"],
        [[0, 0, 0], [0.5, 0.5, 0], [0.5, 0, 0.5], [0, 0.5, 0.5]],
    )
    shifted = local.copy()
    shifted.translate_sites(range(4), [0.1, 0.2, 0.3])
    assert geometry_agrees(local.as_dict(), shifted.as_dict()).startswith("strict_periodic")
    changed = shifted.as_dict()
    changed["sites"][0]["label"] = "changed-input-label"
    with pytest.raises(ValueError, match="site attributes differ"):
        geometry_agrees(local.as_dict(), changed)


def test_parallel_manifest_verification_rejects_tampering_and_escape(tmp_path):
    original = b"original scientific input"
    (tmp_path / "input.json").write_bytes(original)
    entry = {"sha256": hashlib.sha256(original).hexdigest(), "size": len(original)}
    verify_manifest_files(tmp_path, {"input.json": entry})
    (tmp_path / "input.json").write_bytes(b"changed scientific input!")
    with pytest.raises(ValueError, match="File verification failed"):
        verify_manifest_files(tmp_path, {"input.json": entry})
    with pytest.raises(ValueError, match="Unsafe manifest path"):
        verify_manifest_files(tmp_path, {"../outside.json": entry})


def test_geometry_preserves_site_property_arrangement_not_just_its_multiset():
    local = Structure(
        Lattice([[3, 0, 0], [0.2, 4, 0], [0.1, 0.3, 5]]),
        ["Na"] * 4,
        [[0, 0, 0], [0.1, 0.2, 0.3], [0.22, 0.4, 0.71], [0.42, 0.11, 0.16]],
        site_properties={"magmom": [0, 1, 0, 1]},
    )
    shifted = local.copy()
    shifted.translate_sites(range(4), [0.1, 0.2, 0.3])
    assert geometry_agrees(local.as_dict(), shifted.as_dict()).startswith("strict_periodic")
    changed = shifted.as_dict()
    changed["sites"][0]["properties"]["magmom"] = 1
    changed["sites"][1]["properties"]["magmom"] = 0
    with pytest.raises(ValueError, match="geometry differs"):
        geometry_agrees(local.as_dict(), changed)
