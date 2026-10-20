$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$petPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $petPython)) { throw 'Run setup.ps1 first.' }
$petWorkspace = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\') + '\'
foreach ($petRelative in @('build', 'dist\Desktopper')) {
    $petTarget = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $petRelative))
    if (-not $petTarget.StartsWith($petWorkspace, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Build output is outside the workspace: $petTarget"
    }
}
$env:PYINSTALLER_CONFIG_DIR = Join-Path $PSScriptRoot 'build\.pyinstaller-cache'
& $petPython -m pip install 'pyinstaller==6.22.3'
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller installation failed.' }
& $petPython main.py --check
if ($LASTEXITCODE -ne 0) { throw 'Asset validation failed.' }
& $petPython -m PyInstaller --noconfirm --clean --windowed --onedir --copy-metadata PySide6 --copy-metadata PySide6-Essentials --copy-metadata shiboken6 --name Desktopper main.py
if ($LASTEXITCODE -ne 0) { throw 'Packaging failed.' }
$petOutput = Join-Path $PSScriptRoot 'dist\Desktopper'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'assets') -Destination $petOutput -Recurse -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README.md') -Destination $petOutput -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'pets') -Destination $petOutput -Recurse -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'THIRD_PARTY_NOTICES.md') -Destination $petOutput -Force
Write-Host "Ready: $petOutput\Desktopper.exe"
