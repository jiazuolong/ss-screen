"""Bootstrap regressions without network, GUI launches, or scientific computation."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def launcher():
    spec = importlib.util.spec_from_file_location("start_10um", REPO / "scripts/start_10um.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_create_gui_uses_running_bootstrap_python(launcher, tmp_path, monkeypatch):
    probe = Mock(side_effect=[False, True])
    run = Mock()
    monkeypatch.setattr(launcher, "windows_python_ready", probe)
    monkeypatch.setattr(launcher.subprocess, "run", run)
    result = launcher.ensure_windows_environment(tmp_path)
    assert result == tmp_path / ".venv-gui/Scripts/python.exe"
    run.assert_called_once_with(
        [tmp_path / "tools/uv.exe", "venv", "--python", sys.executable, tmp_path / ".venv-gui"],
        check=True,
    )


def test_reuse_gui_does_not_recreate(launcher, tmp_path, monkeypatch):
    run = Mock()
    monkeypatch.setattr(launcher, "windows_python_ready", lambda path: True)
    monkeypatch.setattr(launcher.subprocess, "run", run)
    launcher.ensure_windows_environment(tmp_path)
    run.assert_not_called()


def test_broken_gui_is_preserved_and_replaced(launcher, tmp_path, monkeypatch):
    (tmp_path / ".ss-screen-launcher-v1").touch()
    gui = tmp_path / ".venv-gui"
    gui.mkdir()
    (gui / "original.txt").write_text("keep failed installation")
    monkeypatch.setattr(launcher, "windows_python_ready", Mock(side_effect=[False, True]))

    def create_environment(argv, **kwargs):
        assert not gui.exists()
        gui.mkdir()

    monkeypatch.setattr(launcher.subprocess, "run", create_environment)
    launcher.ensure_windows_environment(tmp_path)
    backups = list(tmp_path.glob(".venv-gui.unusable-*"))
    assert len(backups) == 1
    assert (backups[0] / "original.txt").read_text() == "keep failed installation"
    assert gui.is_dir()


def test_foreign_environment_is_not_moved(launcher, tmp_path, monkeypatch):
    gui = tmp_path / ".venv-gui"
    gui.mkdir()
    monkeypatch.setattr(launcher, "windows_python_ready", lambda path: False)
    with pytest.raises(RuntimeError, match="outside a launcher workspace"):
        launcher.ensure_windows_environment(tmp_path)
    assert gui.is_dir()
    assert not list(tmp_path.glob(".venv-gui.unusable-*"))


@pytest.mark.parametrize("failure", [OSError(4551, "blocked"), subprocess.TimeoutExpired("py", 15)])
def test_existing_exe_must_actually_run(launcher, tmp_path, monkeypatch, failure):
    python = tmp_path / "python.exe"
    python.touch()
    monkeypatch.setattr(launcher.subprocess, "run", Mock(side_effect=failure))
    assert not launcher.windows_python_ready(python)


def test_wrong_python_is_rejected(launcher, tmp_path, monkeypatch):
    python = tmp_path / "python.exe"
    python.touch()
    run = Mock(return_value=subprocess.CompletedProcess([], 1, "", "AssertionError"))
    monkeypatch.setattr(launcher.subprocess, "run", run)
    assert not launcher.windows_python_ready(python)
    assert run.call_args.kwargs["timeout"] == launcher.PYTHON_PROBE_TIMEOUT


def test_blocked_new_runtime_stops_before_data_download(launcher, tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "windows_python_ready", lambda path: False)
    monkeypatch.setattr(launcher.subprocess, "run", Mock())
    download = Mock()
    monkeypatch.setattr(launcher, "download", download)
    with pytest.raises(RuntimeError, match="4551"):
        launcher.launch(tmp_path)
    download.assert_not_called()


def test_windows_bootstrap_contracts(tmp_path):
    """Exercise PowerShell selection/download logic with Pester on Windows via WSL interop."""
    powershell = shutil.which("powershell.exe")
    if not powershell:
        pytest.skip("PowerShell/Pester requires Windows or WSL interoperability")

    def windows_path(path):
        if os.name == "nt":
            return str(path)
        return subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()

    # Keep Pester's generated fixtures inside pytest's explicitly configured workspace temp.
    code = (
        "$ErrorActionPreference = 'Stop'; "
        f"$env:TEMP = '{windows_path(tmp_path).replace(chr(39), chr(39) * 2)}'; "
        "$env:TMP = $env:TEMP; "
        f"Invoke-Pester -Script '{windows_path(REPO / 'tests/test_windows_python.ps1')}' -EnableExit"
    )
    result = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", code],
        capture_output=True,
        timeout=120,
    )
    assert result.returncode == 0, (result.stdout + result.stderr).decode("utf-8", errors="replace")
