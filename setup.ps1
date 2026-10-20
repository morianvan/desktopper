$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$petPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $petPython)) {
    $petLauncher = Get-Command py -ErrorAction SilentlyContinue
    $petSystemPython = Get-Command python -ErrorAction SilentlyContinue
    $petBundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if ($petLauncher) {
        & $petLauncher.Source -3 -m venv .venv
    } elseif ($petSystemPython) {
        & $petSystemPython.Source -m venv .venv
    } elseif (Test-Path -LiteralPath $petBundledPython) {
        & $petBundledPython -m venv .venv
    } else {
        throw 'Install Python 3.10 or newer (64-bit), then run setup.ps1 again.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtual environment.' }
}
& $petPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $petPython main.py --check
if ($LASTEXITCODE -ne 0) { throw 'Asset validation failed.' }
Write-Host 'Ready. Double-click launch.bat.'
