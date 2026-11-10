$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host 'Installing build dependencies...'
python -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Could not install dependencies.' }

Write-Host 'Building TierListMaker.exe...'
python -m PyInstaller --noconfirm --clean --windowed --onefile `
  --name TierListMaker `
  --icon assets\tierlist-icon.ico `
  --add-data "assets\tierlist-icon.png;." `
  --collect-all PySide6 `
  --collect-all shiboken6 `
  main.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

Write-Host "Done: $ProjectRoot\dist\TierListMaker.exe" -ForegroundColor Green