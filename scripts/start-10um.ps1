param([string]$WorkDir = (Get-Location).Path)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$workspace = Join-Path (Resolve-Path -LiteralPath $WorkDir).Path 'ss-screen-10um'
$owner = Join-Path $workspace '.ss-screen-launcher-v1'
if ((Test-Path -LiteralPath $workspace) -and !(Test-Path -LiteralPath $owner) -and
    (Get-ChildItem -Force -LiteralPath $workspace | Select-Object -First 1)) {
    throw "Directory already in use: $workspace. Run from a different folder."
}
[IO.Directory]::CreateDirectory($workspace) | Out-Null
$lock = [IO.File]::Open($owner, 'OpenOrCreate', 'ReadWrite', 'None')
try {
    & wsl.exe --exec true
    if ($LASTEXITCODE) { throw 'Start an Ubuntu WSL distribution and make it the default before running this command.' }
    $arch = [Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
    $builds = @{
        X64 = @('x86_64', '28cbe5d30907a774bfe27a517a39b494ec6f7d3816bda8bbf6f9645490449182')
        Arm64 = @('aarch64', 'fadb43ba13091f44e1786fc3967e65c7786d86192aa205d718307c649927cfc2')
    }
    if (!$builds.ContainsKey($arch)) { throw "Unsupported Windows architecture: $arch" }
    $tools = Join-Path $workspace 'tools'
    [IO.Directory]::CreateDirectory($tools) | Out-Null
    $uv = Join-Path $tools 'uv.exe'
    if (!(Test-Path -LiteralPath $uv)) {
        $archive = Join-Path $tools 'uv-windows.zip'
        $platform, $hash = $builds[$arch]
        $url = "https://github.com/astral-sh/uv/releases/download/0.9.18/uv-$platform-pc-windows-msvc.zip"
        Write-Host 'Downloading Windows environment manager...'
        & curl.exe --fail --location --retry 3 --connect-timeout 30 --speed-time 120 --speed-limit 1024 --silent --show-error --output $archive $url
        if ($LASTEXITCODE) { throw 'Windows uv download failed.' }
        $sha = [Security.Cryptography.SHA256]::Create()
        $stream = [IO.File]::OpenRead($archive)
        try {
            $actual = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '')
        } finally { $stream.Dispose(); $sha.Dispose() }
        if ($actual -ne $hash) { throw 'Windows uv download failed verification.' }
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [IO.Compression.ZipFile]::OpenRead($archive)
        try {
            $entry = $zip.Entries | Where-Object Name -eq 'uv.exe' | Select-Object -First 1
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, "$uv.tmp", $true)
        } finally { $zip.Dispose() }
        Move-Item -LiteralPath "$uv.tmp" -Destination $uv
    }
    & $uv run --no-project --python 3.11 -- (Join-Path $PSScriptRoot 'start_10um.py') $workspace
    if ($LASTEXITCODE) { throw "Setup failed (exit $LASTEXITCODE). Retry the same command after resolving the error above." }
} finally { $lock.Dispose() }
