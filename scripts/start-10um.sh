#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
exec powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w "$script_dir/start-10um.ps1")" -WorkDir "$(wslpath -w "$PWD")" -Distribution "${WSL_DISTRO_NAME:?Run this script inside WSL}"
