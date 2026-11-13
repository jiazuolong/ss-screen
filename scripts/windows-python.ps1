# Windows bootstrap helpers. Dot-sourcing this file does not install or launch anything.
# Official CPython NuGet distributions: https://docs.python.org/3.11/using/windows.html
# 3.11.9 is the last PSF Windows binary release for 3.11 and matches the demo GUI baseline.
$script:LauncherPythonVersion = '3.11.9'
$script:LauncherPythonPackages = @{
    X64 = @('python', '9283876d58c017e0e846f95b490da3bca0fc0a6ee1134b2870677cfb7eec3c67')
    Arm64 = @('pythonarm64', '2f5b3bee38850fdde1b44227a23b8130d329839558376d2eb11099ce2b2cc33c')
}
$script:LauncherProbeTimeoutMs = 15000

function Get-LauncherSha256([string]$Path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try {
        return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
    } finally { $stream.Dispose(); $sha.Dispose() }
}

function Save-LauncherDownload([string]$Url, [string]$Path, [string]$Sha256) {
    if ((Test-Path -LiteralPath $Path -PathType Leaf) -and
        (Get-LauncherSha256 $Path) -eq $Sha256) { return }
    $partial = "$Path.part"
    Write-Host "Downloading $([IO.Path]::GetFileName($Path)) ..."
    & curl.exe --fail --location --retry 3 --retry-all-errors --connect-timeout 30 --speed-time 120 `
        --speed-limit 1024 --progress-bar --output $partial $Url
    if ($LASTEXITCODE) { throw "Download failed: $Url. Run the launcher again to retry." }
    if ((Get-LauncherSha256 $partial) -ne $Sha256) {
        throw "SHA-256 verification failed: $partial. The file will not be used. Run the launcher again to retry."
    }
    Move-Item -LiteralPath $partial -Destination $Path -Force
}

function Test-LauncherPython([string]$Python, [string]$Architecture) {
    if (!(Test-Path -LiteralPath $Python -PathType Leaf -ErrorAction SilentlyContinue)) { return $false }
    $machine = if ($Architecture -eq 'Arm64') { 'ARM64' } else { 'AMD64' }
    # -I ignores inherited PYTHONPATH/user packages. Probe libraries needed by bootstrap/venv too.
    $probe = "import sys, struct, platform, ssl, venv; " +
        "assert sys.platform == 'win32' and sys.version_info[:2] == (3, 11); " +
        "assert struct.calcsize('P') == 8 and platform.machine().upper() == '$machine'; " +
        "print('ss-screen-python-ok')"
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $Python
    $info.Arguments = '-I -c "' + $probe + '"'
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $info
    try {
        [void]$process.Start()
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (!$process.WaitForExit($script:LauncherProbeTimeoutMs)) {
            $process.Kill()
            Write-Host "Python check timed out: $Python"
            return $false
        }
        $output = $stdout.GetAwaiter().GetResult().Trim()
        $detail = $stderr.GetAwaiter().GetResult().Trim()
        if ($process.ExitCode -eq 0 -and $output -eq 'ss-screen-python-ok') { return $true }
        Write-Host "Python check failed: $Python (exit $($process.ExitCode)) $detail"
    } catch {
        Write-Host "Cannot run Python: $Python. $($_.Exception.Message)"
    } finally { $process.Dispose() }
    return $false
}

function Find-InstalledWindowsPython([string]$Uv) {
    try {
        # Does not need py.exe, and never downloads or selects the blocked uv-managed build.
        $candidate = & $Uv python find --system --no-managed-python --no-python-downloads 3.11 2>$null
        if ($LASTEXITCODE -eq 0 -and $candidate) { return ($candidate | Select-Object -Last 1).Trim() }
    } catch { Write-Host 'No usable installed Windows Python 3.11 was found.' }
    return $null
}

function Assert-OfficialPythonSignature([string]$Directory) {
    foreach ($name in @('python.exe', 'pythonw.exe', 'python311.dll')) {
        $signature = Get-AuthenticodeSignature -LiteralPath (Join-Path $Directory $name)
        if ($signature.Status -ne 'Valid' -or
            $signature.SignerCertificate.Subject -notmatch '(?:^|,\s*)O=Python Software Foundation(?:,|$)') {
            throw "Official Python signature validation failed: $name ($($signature.Status)). The runtime will not be used."
        }
    }
}

function Install-PrivateWindowsPython([string]$Tools, [string]$Architecture) {
    if (!$script:LauncherPythonPackages.ContainsKey($Architecture)) {
        throw "Unsupported Windows architecture: $Architecture"
    }
    $package, $digest = $script:LauncherPythonPackages[$Architecture]
    $version = $script:LauncherPythonVersion
    $archive = Join-Path $Tools "$package.$version.nupkg"
    $destination = Join-Path $Tools "python-$version-$Architecture"
    $python = Join-Path $destination 'tools/python.exe'
    $markerName = '.ss-screen-python-runtime'
    if (Test-Path -LiteralPath $destination) {
        if (!(Test-Path -LiteralPath (Join-Path $destination $markerName))) {
            throw "Runtime directory is not owned by this launcher: $destination"
        }
        if (Test-LauncherPython $python $Architecture) { return $python }
        # Preserve the failed runtime; never recursively delete an existing environment.
        $backup = "$destination.unusable-$([Guid]::NewGuid().ToString('N'))"
        $root = [IO.Path]::GetFullPath($Tools).TrimEnd('\') + '\'
        if (![IO.Path]::GetFullPath($destination).StartsWith($root, [StringComparison]::OrdinalIgnoreCase) -or
            ![IO.Path]::GetFullPath($backup).StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Runtime backup must remain inside the launcher tools directory.'
        }
        Move-Item -LiteralPath $destination -Destination $backup
        Write-Host "Preserved unusable Python at $backup"
    }
    Save-LauncherDownload "https://api.nuget.org/v3-flatcontainer/$package/$version/$package.$version.nupkg" $archive $digest
    $staging = "$destination.staging-$([Guid]::NewGuid().ToString('N'))"
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::ExtractToDirectory($archive, $staging)
    Assert-OfficialPythonSignature (Join-Path $staging 'tools')
    [IO.File]::WriteAllText((Join-Path $staging $markerName), "$package $version $digest")
    Move-Item -LiteralPath $staging -Destination $destination
    if (!(Test-LauncherPython $python $Architecture)) {
        throw "Windows cannot run the verified official Python at $python. If error 4551 appears, an Application Control policy is blocking execution; this launcher cannot override it. Ask the device administrator to review that file's block event."
    }
    return $python
}

function Resolve-LauncherPython([string]$Uv, [string]$Workspace, [string]$Architecture) {
    if ($env:SSSCREEN_WINDOWS_PYTHON) {
        $override = (Resolve-Path -LiteralPath $env:SSSCREEN_WINDOWS_PYTHON).ProviderPath
        if (!(Test-LauncherPython $override $Architecture)) {
            throw 'SSSCREEN_WINDOWS_PYTHON must point to a runnable Windows Python 3.11 of the matching architecture.'
        }
        return $override
    }
    $existing = Join-Path $Workspace '.venv-gui/Scripts/python.exe'
    if (Test-LauncherPython $existing $Architecture) { return $existing }
    $installed = Find-InstalledWindowsPython $Uv
    if ($installed -and (Test-LauncherPython $installed $Architecture)) { return $installed }
    Write-Host 'Preparing a private, signed Windows Python runtime (no py.exe or PATH setup needed) ...'
    return Install-PrivateWindowsPython (Join-Path $Workspace 'tools') $Architecture
}
