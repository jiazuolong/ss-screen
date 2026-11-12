"""Shell commands for separate WSL runtime and GUI data directories."""

from __future__ import annotations

import shlex


def build_wsl_command(
    environment_root: str,
    project_root: str,
    activate: str,
    argv: list[str],
    *,
    api_key: str = "",
) -> str:
    """Activate the code environment, then resolve all CLI paths in the data project."""
    commands = [
        f"cd {shlex.quote(environment_root)}",
        f"source {shlex.quote(activate)}",
        f"cd {shlex.quote(project_root)}",
        "export PYTHONUNBUFFERED=1",
    ]
    if api_key:
        commands.append(f"export MP_API_KEY={shlex.quote(api_key)}")
    commands.append(shlex.join(["ss-screen", *argv]))
    return " && ".join(commands)
