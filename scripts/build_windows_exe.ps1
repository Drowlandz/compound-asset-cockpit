param(
    [string]$AppName = "长期复利资产驾驶舱",
    [string]$ExeName = "CompoundAssetDashboard",
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Step($msg) {
    Write-Host "[build] $msg" -ForegroundColor Cyan
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = Get-Date -Format "yyyyMMdd_HHmmss"
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$BuildRoot = Join-Path $RepoRoot "release\windows"
$WorkRoot = Join-Path $RepoRoot "build\windows"
$VenvDir = Join-Path $RepoRoot ".venv-build-win"
$DistDir = Join-Path $WorkRoot "dist"
$SpecDir = Join-Path $WorkRoot "spec"
$BuildDir = Join-Path $WorkRoot "pyi-build"
$OutputDir = Join-Path $BuildRoot "${ExeName}_${Version}"
$ZipPath = Join-Path $BuildRoot "${ExeName}_${Version}.zip"

Step "RepoRoot = $RepoRoot"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python not found. Please install Python 3.9+ and add it to PATH."
}

Step "Preparing folders"
New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null

if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }
if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
if (Test-Path $SpecDir) { Remove-Item -Recurse -Force $SpecDir }
if (Test-Path $OutputDir) { Remove-Item -Recurse -Force $OutputDir }
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }

if (-not (Test-Path $VenvDir)) {
    Step "Creating build virtualenv"
    python -m venv $VenvDir
}

$Py = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $Py)) {
    throw "Virtualenv python not found: $Py"
}

Step "Installing dependencies (requirements + pyinstaller)"
& $Py -m pip install --upgrade pip
& $Py -m pip install -r (Join-Path $RepoRoot "requirements.txt")
& $Py -m pip install pyinstaller

Step "Running PyInstaller"
Push-Location $RepoRoot
try {
    & $Py -m PyInstaller `
        --noconfirm `
        --clean `
        --onedir `
        --name $ExeName `
        --distpath $DistDir `
        --workpath $BuildDir `
        --specpath $SpecDir `
        --collect-all streamlit `
        --collect-all streamlit_echarts `
        --add-data "app.py;." `
        --add-data "assets;assets" `
        --add-data "services;services" `
        --add-data "alerts;alerts" `
        run_app.py
}
finally {
    Pop-Location
}

$BuiltDir = Join-Path $DistDir $ExeName
if (-not (Test-Path $BuiltDir)) {
    throw "PyInstaller output missing: $BuiltDir"
}

Step "Preparing release folder"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
Copy-Item -Recurse -Force "$BuiltDir\*" $OutputDir

$ReadmePath = Join-Path $OutputDir "README-Windows.txt"
@"
$AppName (Windows)

1) Double click $ExeName.exe to start the app.
2) Browser should open automatically. If not, visit: http://localhost:8501
3) The app data file (investments.db) is created in the same folder as the EXE on first run.
"@ | Out-File -FilePath $ReadmePath -Encoding utf8

Step "Creating zip package"
Compress-Archive -Path "$OutputDir\*" -DestinationPath $ZipPath -Force

Step "Done"
Write-Host "Output folder: $OutputDir" -ForegroundColor Green
Write-Host "Output zip:    $ZipPath" -ForegroundColor Green
