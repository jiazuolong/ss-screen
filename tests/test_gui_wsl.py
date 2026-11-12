"""Execute the GUI shell contract without requiring Qt or scientific calculations."""

import os
import subprocess

import pytest

from ssscreen.gui.wsl import build_wsl_command

pytestmark = pytest.mark.skipif(os.name == "nt", reason="Run shell contracts in WSL/Linux")


@pytest.mark.parametrize("activate", [".venv/bin/activate", ".venv-mlp/bin/activate"])
@pytest.mark.parametrize("same_directory", [False, True])
def test_runtime_and_relative_data_paths(tmp_path, activate, same_directory):
    code = tmp_path / "code 中文's space"
    project = code if same_directory else tmp_path / "data 中文's space"
    code.mkdir()
    project.mkdir(exist_ok=True)
    (code / activate).parent.mkdir(parents=True)
    # A shell stand-in checks cwd, input/output resolution and selected environment.
    (code / activate).write_text(
        f"export SELECTED_ENV={activate}\n"
        'ss-screen() { test "$1" = probe && test "$2" = \'literal $value\' '
        '&& cat 01_dataset/mp.df > result.txt && printf "%s" "$SELECTED_ENV" > env.txt; }\n'
    )
    (project / "01_dataset").mkdir()
    (project / "01_dataset/mp.df").write_text("new project data")
    command = build_wsl_command(str(code), str(project), activate, ["probe", "literal $value"])
    result = subprocess.run(["bash", "-c", command], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (project / "result.txt").read_text() == "new project data"
    assert (project / "env.txt").read_text() == activate
    if not same_directory:
        assert not (code / "result.txt").exists()


def test_missing_environment_does_not_execute_cli(tmp_path):
    command = build_wsl_command(str(tmp_path), str(tmp_path), "missing/activate", ["probe"])
    result = subprocess.run(
        ["bash", "-c", "ss-screen() { touch wrongly-ran; }; " + command],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert not (tmp_path / "wrongly-ran").exists()
