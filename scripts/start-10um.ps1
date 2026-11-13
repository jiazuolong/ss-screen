param([string]$WorkDir = (Get-Location).Path, [string]$Distribution)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
. (Join-Path $PSScriptRoot 'windows-python.ps1')
$directory = (Resolve-Path -LiteralPath $WorkDir).ProviderPath
$workspace = [IO.Path]::Combine($directory, 'ss-screen-10um')
if (!$Distribution -and $directory -match '^\\\\(?:wsl\.localhost|wsl\$)\\([^\\]+)') {
    $Distribution = $Matches[1]
}
$wslArgs = @()
if ($Distribution) { $wslArgs = @('-d', $Distribution) }
$env:SSSCREEN_WSL_DISTRO = $Distribution
$owner = Join-Path $workspace '.ss-screen-launcher-v1'
if ((Test-Path -LiteralPath $workspace) -and !(Test-Path -LiteralPath $owner) -and
    (Get-ChildItem -Force -LiteralPath $workspace | Select-Object -First 1)) {
    throw "Directory already in use: $workspace. Run from a different folder."
}
[IO.Directory]::CreateDirectory($workspace) | Out-Null
$lock = [IO.File]::Open($owner, 'OpenOrCreate', 'ReadWrite', 'None')
$transcribing = $false
try {
    Start-Transcript -LiteralPath (Join-Path $workspace 'setup.log') -Append | Out-Null
    $transcribing = $true
    & wsl.exe @wslArgs --exec true
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
        Save-LauncherDownload $url $archive $hash
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [IO.Compression.ZipFile]::OpenRead($archive)
        try {
            $entry = $zip.Entries | Where-Object Name -eq 'uv.exe' | Select-Object -First 1
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, "$uv.tmp", $true)
        } finally { $zip.Dispose() }
        Move-Item -LiteralPath "$uv.tmp" -Destination $uv
    }
    $python = Resolve-LauncherPython $uv $workspace $arch
    Write-Host "Using Windows Python: $python"
    & $python (Join-Path $PSScriptRoot 'start_10um.py') $workspace
    if ($LASTEXITCODE) { throw "Setup failed (exit $LASTEXITCODE). Retry the same command after resolving the error above." }
} catch {
    Write-Host "Setup failed: $($_.Exception.Message)"
    Write-Host "Details: $(Join-Path $workspace 'setup.log')"
    throw
} finally {
    if ($transcribing) { Stop-Transcript | Out-Null }
    $lock.Dispose()
}
