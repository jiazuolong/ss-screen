"""Prepare the published demo and launch the Windows workbench."""

import hashlib
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RELEASE = "https://github.com/jiazuolong/ss-screen/releases/download/demo-10um-20261112"
WHEEL = "mp_offline-0.1.0-py2.py3-none-any.whl"
FILES = {
    "project-10um.zip": "6848e496db2a9781c51047cb064208363ba5c90ce03757f09bfd5faf13fec863",
    "default.db.zip": "0f55530333f659021e58edfc599361eb42835ead63a43ce28c49147884046e40",
    WHEEL: "d68ad80a9997192074c0126338e1551f56e2997fbdcd1bcf84966258cfc4bf8f",
    "windows-constraints.txt": "4e7952b7b34b811b22bb41681de14f29bb7c9df29b32e813450bcdfb914e6eab",
    "wsl-constraints.txt": "a254b18beb923aa24919c279a12605d89fb8039e2cdb6c66fae999c3e98b56d4",
}
LINUX_UV = {
    "x86_64": "c2def3db178ade63933fa15ffc96e882c196ce53e06173dcee05b36c5f6f68f5",
    "aarch64": "f8e23ec786b18660ade6b033b6191b7e9c283c872eeb8c4531d56a873decf160",
}
PYTHON_PROBE_TIMEOUT = 15
GUI_STARTUP_TIMEOUT = 3


def windows_python_ready(python: Path) -> bool:
    """Check an existing environment by running it, not just by finding its exe."""
    if not python.is_file():
        return False
    probe = (
        "import sys, ssl, venv, platform; "
        "assert sys.platform == 'win32' and sys.version_info[:2] == (3, 11); "
        "assert sys.maxsize > 2**32; "
        f"assert platform.machine().upper() == {platform.machine().upper()!r}"
    )
    try:
        result = subprocess.run(
            [python, "-I", "-c", probe],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=PYTHON_PROBE_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"Cannot run GUI Python {python}: {exc}", flush=True)
        return False
    if result.returncode:
        print(f"GUI Python check failed: {python}\n{result.stderr}", flush=True)
        return False
    return True


def ensure_windows_environment(workspace: Path) -> Path:
    """Reuse the verified bootstrap interpreter, preserving any failed old environment."""
    gui = workspace / ".venv-gui"
    python = gui / "Scripts/python.exe"
    if windows_python_ready(python):
        return python
    if gui.exists():
        if not (workspace / ".ss-screen-launcher-v1").is_file():
            raise RuntimeError(
                f"Refusing to move an environment outside a launcher workspace: {gui}"
            )
        backup = workspace / f".venv-gui.unusable-{uuid.uuid4().hex}"
        # Both paths are direct children of the same verified workspace; no recursive deletion.
        gui.rename(backup)
        print(f"Preserved unusable GUI environment at {backup}", flush=True)
    print("Preparing the Windows GUI environment ...", flush=True)
    subprocess.run(
        [workspace / "tools/uv.exe", "venv", "--python", sys.executable, python.parent.parent],
        check=True,
    )
    if not windows_python_ready(python):
        raise RuntimeError(
            f"Windows could not run the new GUI interpreter: {python}. "
            "If Windows reports Application Control error 4551, ask the device administrator "
            "to review the blocked file. The launcher does not change Windows security policies."
        )
    return python


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url, path, expected):
    if path.is_file() and sha256(path) == expected:
        return
    print(f"Downloading {path.name} ...", flush=True)
    partial = path.with_suffix(path.suffix + ".part")
    subprocess.run(
        [
            "curl.exe",
            "-fsSL",
            "--retry",
            "3",
            "--retry-all-errors",
            "--connect-timeout",
            "30",
            "--speed-limit",
            "1024",
            "--speed-time",
            "120",
            "-o",
            partial,
            url,
        ],
        check=True,
    )
    if sha256(partial) != expected:
        raise ValueError(f"SHA-256 mismatch: {path.name}")
    partial.replace(path)


def wsl_command(*args):
    distro = os.environ.get("SSSCREEN_WSL_DISTRO")
    return ["wsl.exe", *(["-d", distro] if distro else []), "--exec", *args]


def wsl_text(*args):
    return subprocess.check_output(wsl_command(*args), encoding="utf-8").strip()


def wsl_path(path):
    return wsl_text("wslpath", "-a", str(path))


def prepare(workspace):
    from ssscreen.gui.project_file import inspect_project_file
    from ssscreen.gui.ten_micron_page import unpack_example

    project = workspace / "project"
    marker = project / ".ssscreen-project.json"
    cache = workspace / "downloads"
    if project.exists():
        if not marker.is_file() or not (project / "ten_micron.json").is_file():
            raise ValueError(f"Unrecognized project directory: {project}")
        if (
            sha256(project / "01_dataset/default.db")
            != json.loads((project / "ten_micron.json").read_text(encoding="utf-8"))[
                "database_sha256"
            ]
        ):
            raise ValueError("The existing project's default.db differs from the demo database.")
        return
    with tempfile.TemporaryDirectory(dir=workspace) as directory:
        staging = Path(directory)
        with zipfile.ZipFile(cache / "project-10um.zip") as archive:
            source = Path(archive.extract("10.0 μm演示.ssproject", staging))
        metadata, _ = inspect_project_file(source)
        settings = metadata["settings"].copy()
        profile = settings["ten_micron_profile"]
        staged = staging / "project"
        unpack_example(source, staged, profile)
        with zipfile.ZipFile(cache / "default.db.zip") as archive:
            database = Path(archive.extract("default.db", staged / "01_dataset"))
        if sha256(database) != profile["database_sha256"]:
            raise ValueError("Unpacked database failed SHA-256 verification.")
        settings["wsl_project_path"] = wsl_path(workspace)
        (staged / marker.name).write_text(
            json.dumps(
                {
                    "name": "10.0 μm演示",
                    "gui_settings": settings,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (staged / ".ssscreen/source.txt").write_text(str(cache / source.name), encoding="utf-8")
        source.replace(cache / source.name)
        staged.rename(project)


def launch(workspace):
    cache = workspace / "downloads"
    cache.mkdir(exist_ok=True)
    # Fail early on a blocked runtime, before downloading the large demo database.
    python = ensure_windows_environment(workspace)
    for name, digest in FILES.items():
        download(f"{RELEASE}/{name}", cache / name, digest)
    tools = workspace / "tools"
    arch = wsl_text("uname", "-m")
    bundle = f"uv-{arch}-unknown-linux-gnu"
    binary = tools / "uv-linux"
    if not binary.exists():
        archive = tools / f"{bundle}.tar.gz"
        download(
            f"https://github.com/astral-sh/uv/releases/download/0.9.18/{archive.name}",
            archive,
            LINUX_UV[arch],
        )
        partial = binary.with_suffix(".part")
        with tarfile.open(archive) as tar, partial.open("wb") as stream:
            with tar.extractfile(f"{bundle}/uv") as uv:
                shutil.copyfileobj(uv, stream)
        subprocess.run(wsl_command("chmod", "+x", wsl_path(partial)), check=True)
        partial.replace(binary)

    # The GUI and CLI have separate interpreters even when they share the checkout.
    win_uv = tools / "uv.exe"
    gui = workspace / ".venv-gui"
    subprocess.run(
        [
            win_uv,
            "--quiet",
            "pip",
            "install",
            "--python",
            python,
            "-c",
            cache / "windows-constraints.txt",
            f"{REPO}[gui]",
        ],
        check=True,
    )
    linux_uv = wsl_path(binary)
    linux_root = wsl_path(workspace)
    venv = linux_root + "/.venv"
    linux_cache = linux_root + "/downloads/"
    print("Preparing the WSL computation environment ...", flush=True)
    commands = [
        "test -x "
        + shlex.quote(venv + "/bin/python")
        + " || "
        + shlex.join([linux_uv, "venv", "--python", "3.11", venv]),
        shlex.join(
            [
                linux_uv,
                "--quiet",
                "pip",
                "install",
                "--link-mode",
                "copy",
                "--python",
                venv + "/bin/python",
                "-c",
                linux_cache + "wsl-constraints.txt",
                "-e",
                wsl_path(REPO) + "[mp]",
                linux_cache + WHEEL,
            ]
        ),
        shlex.join([venv + "/bin/python", "-c", "import ssscreen, mp_offline.client"]),
    ]
    subprocess.run(wsl_command("bash", "-lc", " && ".join(commands)), check=True)
    subprocess.run([python, __file__, workspace, "--prepare"], check=True)
    project = workspace / "project"
    print(f"Opening stage 01: {project}", flush=True)
    startup_log = workspace / "gui-startup.log"
    with startup_log.open("ab") as log:
        process = subprocess.Popen(
            [gui / "Scripts/pythonw.exe", "-m", "ssscreen.gui.app", project],
            cwd=REPO,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    try:
        code = process.wait(timeout=GUI_STARTUP_TIMEOUT)
    except subprocess.TimeoutExpired:
        return
    if code:
        raise RuntimeError(f"GUI exited with code {code}. See {startup_log}")


if __name__ == "__main__":
    work = Path(sys.argv[1]).resolve()
    if sys.argv[2:] == ["--prepare"]:
        prepare(work)
    else:
        launch(work)
