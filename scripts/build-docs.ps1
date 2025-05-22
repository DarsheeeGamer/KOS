<#
.SYNOPSIS
    Builds and serves the KOS documentation locally.
.DESCRIPTION
    This script sets up a Python virtual environment, installs documentation dependencies,
    and serves the MkDocs documentation site locally.
.PARAMETER BuildOnly
    If specified, only builds the documentation without serving it.
.PARAMETER InstallDeps
    If specified, installs dependencies without building or serving.
#>

param (
    [switch]$BuildOnly = $false,
    [switch]$InstallDeps = $false
)

$ErrorActionPreference = "Stop"

function Write-Info {
    param($Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param($Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param($Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param($Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 1
}

# Check if Python is installed
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
    if (-not $python) {
        Write-Error "Python is not installed. Please install Python 3.8 or higher and try again."
    }
}

# Get Python version
$pythonVersion = & $python.Source --version 2>&1 | Select-String -Pattern "Python (\d+\.\d+)" | ForEach-Object { $_.Matches.Groups[1].Value }
if (-not $pythonVersion) {
    Write-Error "Could not determine Python version. Please check your Python installation."
}

# Check Python version
if ([version]$pythonVersion -lt [version]"3.8") {
    Write-Error "Python 3.8 or higher is required. Found Python $pythonVersion"
}

# Set up virtual environment
$venvPath = ".venv"
$activateScript = "$venvPath\Scripts\Activate.ps1"

# Create virtual environment if it doesn't exist
if (-not (Test-Path $venvPath)) {
    Write-Info "Creating Python virtual environment..."
    & $python.Source -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create virtual environment"
    }
    $activateScript = "$venvPath\Scripts\Activate.ps1"
    if (-not (Test-Path $activateScript)) {
        Write-Error "Failed to find virtual environment activation script"
    }
    Write-Success "Virtual environment created successfully"
}

# Activate virtual environment
Write-Info "Activating virtual environment..."
. $activateScript
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to activate virtual environment"
}

# Upgrade pip
Write-Info "Upgrading pip..."
& $python.Source -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Failed to upgrade pip. Continuing anyway..."
}

# Install documentation dependencies
Write-Info "Installing documentation dependencies..."
& $python.Source -m pip install -r requirements-docs.txt
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install documentation dependencies"
}

if ($InstallDeps) {
    Write-Success "Dependencies installed successfully"
    exit 0
}

# Build documentation
Write-Info "Building documentation..."
& $python.Source -m mkdocs build --clean --strict
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to build documentation"
}

if ($BuildOnly) {
    Write-Success "Documentation built successfully in 'site/' directory"
    exit 0
}

# Serve documentation
Write-Info "Starting documentation server at http://127.0.0.1:8000"
Write-Info "Press Ctrl+C to stop the server"

& $python.Source -m mkdocs serve --dev-addr 127.0.0.1:8000

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to start documentation server"
}
