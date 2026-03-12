[CmdletBinding()]
param(
    [switch]$Dev
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Bootstraps Python installation if needed, then runs the E-CLI Python installer.

$ScriptDir = Split-Path -Parent $PSCommandPath
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$InstallerPath = Join-Path $RepoRoot "scripts/install_ecli.py"

function Resolve-PythonCommand {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return @("py", "-3")
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @($python.Source)
    }

    $python3 = Get-Command python3 -ErrorAction SilentlyContinue
    if ($python3) {
        return @($python3.Source)
    }

    return @()
}

function Invoke-WithPython {
    param(
        [string[]]$PythonArgs,
        [string[]]$ExtraArgs
    )

    $exe = $PythonArgs[0]
    $base = @()
    if ($PythonArgs.Count -gt 1) {
        $base = $PythonArgs[1..($PythonArgs.Count - 1)]
    }
    & $exe @base @ExtraArgs
}

function Install-PythonWindows {
    Write-Host "Python not found. Attempting Windows install..."

    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        & winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
        return
    }

    $choco = Get-Command choco -ErrorAction SilentlyContinue
    if ($choco) {
        & choco install -y python
        return
    }

    $scoop = Get-Command scoop -ErrorAction SilentlyContinue
    if ($scoop) {
        & scoop install python
        return
    }

    throw "Could not auto-install Python. Install Python 3.11+ manually from https://www.python.org/downloads/windows/"
}

if (-not (Test-Path $InstallerPath)) {
    throw "Installer not found: $InstallerPath"
}

$pythonArgs = Resolve-PythonCommand
if ($pythonArgs.Count -eq 0) {
    Install-PythonWindows
    $pythonArgs = Resolve-PythonCommand
    if ($pythonArgs.Count -eq 0) {
        throw "Python install was attempted but Python is still unavailable on PATH. Open a new terminal and retry."
    }
}

Write-Host "Using Python runtime: $($pythonArgs -join ' ')"
if ($Dev) {
    Invoke-WithPython -PythonArgs $pythonArgs -ExtraArgs @($InstallerPath, "--dev")
}
else {
    Invoke-WithPython -PythonArgs $pythonArgs -ExtraArgs @($InstallerPath)
}
