[CmdletBinding()]
param(
    [switch]$SkipBackendRebuild,
    [switch]$SkipFrontendBuild,
    [switch]$SkipTauriBuild
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$VenvPython = Join-Path $ProjectRoot "venv\Scripts\python.exe"
$PyInstaller = Join-Path $ProjectRoot "venv\Scripts\pyinstaller.exe"
$SpecFile = Join-Path $ProjectRoot "agentic-backend.spec"
$BuiltSidecar = Join-Path $ProjectRoot "dist\agentic-backend.exe"
$TauriBinaryDirectory = Join-Path $FrontendRoot "src-tauri\binaries"
$TauriSidecar = Join-Path $TauriBinaryDirectory "agentic-backend-v2-x86_64-pc-windows-msvc.exe"
$TauriCli = Join-Path $FrontendRoot "node_modules\.bin\tauri.cmd"
$Npm = (Get-Command npm.cmd -ErrorAction Stop).Source
$CargoDirectory = Join-Path $env:USERPROFILE ".cargo\bin"
if (Test-Path -LiteralPath (Join-Path $CargoDirectory "cargo.exe")) {
    $env:Path = "$CargoDirectory;$env:Path"
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$Step
    )

    Write-Host "[DESKTOP PACKAGE] $Step" -ForegroundColor Cyan
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Project venv was not found: $VenvPython"
}
if (-not (Test-Path -LiteralPath (Join-Path $FrontendRoot "node_modules"))) {
    throw "Frontend dependencies were not found. Run npm ci in $FrontendRoot first."
}
if (-not (Test-Path -LiteralPath $TauriCli)) {
    throw "Tauri CLI was not found: $TauriCli"
}
if (-not (Get-Command cargo.exe -ErrorAction SilentlyContinue)) {
    throw "Cargo was not found. Install Rust or add %USERPROFILE%\\.cargo\\bin to PATH."
}

if (-not $SkipBackendRebuild) {
    Invoke-Checked $PyInstaller @($SpecFile, "--clean", "--noconfirm") "Rebuilding backend sidecar"
    if (-not (Test-Path -LiteralPath $BuiltSidecar)) {
        throw "PyInstaller did not produce $BuiltSidecar"
    }
    New-Item -ItemType Directory -Force -Path $TauriBinaryDirectory | Out-Null
    Copy-Item -LiteralPath $BuiltSidecar -Destination $TauriSidecar -Force
    Write-Host "[DESKTOP PACKAGE] Sidecar staged: $TauriSidecar" -ForegroundColor Green
}

if (-not $SkipFrontendBuild) {
    Push-Location $FrontendRoot
    try {
        Invoke-Checked $Npm @("run", "build") "Building frontend"
    }
    finally {
        Pop-Location
    }
}

if (-not $SkipTauriBuild) {
    Push-Location $FrontendRoot
    try {
        Invoke-Checked $TauriCli @("build", "--bundles", "nsis,msi") "Building Tauri installer"
    }
    finally {
        Pop-Location
    }
}

$BundleRoot = Join-Path $FrontendRoot "src-tauri\target\release\bundle"
Write-Host "[DESKTOP PACKAGE] Completed." -ForegroundColor Green
Write-Host "[DESKTOP PACKAGE] Installer output: $BundleRoot"
