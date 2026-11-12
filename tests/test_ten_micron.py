import hashlib
import json
from zipfile import ZipFile

import pytest

from ssscreen.ten_micron import DIRS, PROFILE, completed, create_workspace, pair_signature


def package(path, file_name, expected):
    with ZipFile(path, "w") as archive:
        archive.writestr(file_name, b"cached")
        archive.writestr(
            PROFILE, json.dumps({"profile": "10um-116-v1", "files": {file_name: expected}})
        )


def test_empty_workspace_starts_at_one_and_preserves_cached_evidence(tmp_path):
    archive = tmp_path / "template.zip"
    target = tmp_path / "run"
    name = "10_phonon/phonon_summary.csv"
    package(archive, name, hashlib.sha256(b"cached").hexdigest())
    create_workspace(archive, target)
    assert completed(target) == 0
    assert all((target / folder).is_dir() for folder in DIRS)
    assert (target / name).read_bytes() == b"cached"
    assert not list((target / DIRS[0]).iterdir())
    with pytest.raises(ValueError):
        create_workspace(archive, target)


@pytest.mark.parametrize("name", ["03_condensed/a.json", "03_condensed/../../escaped"])
def test_damaged_or_escaping_archive_is_not_published(tmp_path, name):
    archive = tmp_path / "template.zip"
    package(archive, name, "bad")
    with pytest.raises(ValueError):
        create_workspace(archive, tmp_path / "new")
    assert not (tmp_path / "new").exists()
    assert not (tmp_path / "escaped").exists()


def test_pair_signature_keeps_group_and_pair_identity_after_move(tmp_path):
    import csv

    path = tmp_path / "pairs.csv"

    def signature(directory, group):
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["mp_id_a", "mp_id_b", "source_groups"])
            writer.writerow(
                ["mp-1", "mp-2", json.dumps([{"file": directory + "/groups.json", "index": group}])]
            )
        return pair_signature(path)

    assert signature("old", 2) == signature("new", 2)
    assert signature("old", 2) != signature("new", 3)
