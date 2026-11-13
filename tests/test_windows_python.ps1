# Invoked by test_start_10um.py through WSL -> Windows PowerShell; no real downloads.
. (Join-Path (Split-Path $PSScriptRoot -Parent) 'scripts/windows-python.ps1')

Describe 'Windows Python bootstrap' {
    BeforeEach {
        $script:PreviousOverride = $env:SSSCREEN_WINDOWS_PYTHON
        $env:SSSCREEN_WINDOWS_PYTHON = $null
        $script:Workspace = Join-Path $TestDrive ([Guid]::NewGuid().ToString('N'))
        [IO.Directory]::CreateDirectory((Join-Path $script:Workspace 'tools')) | Out-Null
    }
    AfterEach { $env:SSSCREEN_WINDOWS_PYTHON = $script:PreviousOverride }

    It 'reuses a runnable GUI environment without discovering or downloading Python' {
        Mock Test-LauncherPython { $true }
        Mock Find-InstalledWindowsPython { throw 'Must not discover' }
        Mock Install-PrivateWindowsPython { throw 'Must not download' }
        Resolve-LauncherPython 'uv.exe' $script:Workspace X64 |
            Should Be (Join-Path $script:Workspace '.venv-gui/Scripts/python.exe')
    }

    It 'uses a working installed interpreter even when py.exe is unavailable' {
        Mock Test-LauncherPython { $Python -eq 'C:\installed\python.exe' }
        Mock Find-InstalledWindowsPython { 'C:\installed\python.exe' }
        Mock Install-PrivateWindowsPython { throw 'Must not download' }
        Resolve-LauncherPython 'uv.exe' $script:Workspace X64 | Should Be 'C:\installed\python.exe'
    }

    It 'automatically prepares official Python when installed Python is blocked' {
        Mock Test-LauncherPython { $false }
        Mock Find-InstalledWindowsPython { 'C:\blocked\python.exe' }
        Mock Install-PrivateWindowsPython { 'C:\private\python.exe' }
        Resolve-LauncherPython 'uv.exe' $script:Workspace X64 | Should Be 'C:\private\python.exe'
        Assert-MockCalled Install-PrivateWindowsPython -Times 1 -Exactly
    }

    It 'automatically prepares official Python when no interpreter exists' {
        Mock Test-LauncherPython { $false }
        Mock Find-InstalledWindowsPython { $null }
        Mock Install-PrivateWindowsPython { 'C:\private\python.exe' }
        Resolve-LauncherPython 'uv.exe' $script:Workspace X64 | Should Be 'C:\private\python.exe'
    }

    It 'rejects a broken explicit override without silently selecting another interpreter' {
        $env:SSSCREEN_WINDOWS_PYTHON = Join-Path $script:Workspace 'override.exe'
        [IO.File]::WriteAllText($env:SSSCREEN_WINDOWS_PYTHON, 'fixture')
        Mock Test-LauncherPython { $false }
        Mock Install-PrivateWindowsPython { throw 'Must not download' }
        { Resolve-LauncherPython 'uv.exe' $script:Workspace X64 } |
            Should Throw 'SSSCREEN_WINDOWS_PYTHON'
    }

    It 'reuses a checksum-valid archive without accessing the network' {
        $archive = Join-Path $script:Workspace 'cached.zip'
        [IO.File]::WriteAllText($archive, 'cached fixture')
        Mock curl.exe { throw 'Must not download' }
        Save-LauncherDownload 'https://example.invalid' $archive (Get-LauncherSha256 $archive)
        [IO.File]::ReadAllText($archive) | Should Be 'cached fixture'
    }

    It 'rejects a corrupt download and preserves the previous file' {
        $archive = Join-Path $script:Workspace 'cached.zip'
        [IO.File]::WriteAllText($archive, 'previous file')
        Mock curl.exe {
            $outputIndex = [Array]::IndexOf($args, '--output')
            [IO.File]::WriteAllText($args[$outputIndex + 1], 'corrupt download')
            $global:LASTEXITCODE = 0
        }
        { Save-LauncherDownload 'https://example.invalid' $archive ('0' * 64) } |
            Should Throw 'SHA-256'
        [IO.File]::ReadAllText($archive) | Should Be 'previous file'
    }

    It 'does not accept a partial download after a connection failure' {
        $archive = Join-Path $script:Workspace 'interrupted.zip'
        Mock curl.exe { $global:LASTEXITCODE = 56 }
        { Save-LauncherDownload 'https://example.invalid' $archive ('0' * 64) } |
            Should Throw 'Download failed'
        Test-Path -LiteralPath $archive | Should Be $false
    }

    It 'rejects unsigned Python binaries before executing them' {
        Mock Get-AuthenticodeSignature {
            [PSCustomObject]@{ Status = 'NotSigned'; SignerCertificate = $null }
        }
        { Assert-OfficialPythonSignature $script:Workspace } | Should Throw 'signature'
    }

    It 'rejects a signed binary from a different publisher' {
        Mock Get-AuthenticodeSignature {
            [PSCustomObject]@{
                Status = 'Valid'
                SignerCertificate = [PSCustomObject]@{ Subject = 'CN=Unrelated, O=Unrelated' }
            }
        }
        { Assert-OfficialPythonSignature $script:Workspace } | Should Throw 'signature'
    }

}

Describe 'Private runtime ownership' {
    It 'does not replace an unowned runtime directory' {
        $tools = Join-Path $TestDrive 'tools'
        $runtime = Join-Path $tools "python-$script:LauncherPythonVersion-X64"
        [IO.Directory]::CreateDirectory($runtime) | Out-Null
        { Install-PrivateWindowsPython $tools X64 } | Should Throw 'not owned'
        Test-Path -LiteralPath $runtime | Should Be $true
    }
}
