param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

$VenvPython = ".\.venv\Scripts\python.exe"
$PythonExe = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

switch ($Command.ToLower()) {
    "install" {
        Write-Host "==> Installing dependencies..." -ForegroundColor Cyan
        & $PythonExe -m pip install --upgrade pip
        & $PythonExe -m pip install -r requirements-dev.txt
    }
    "test" {
        Write-Host "==> Running pytest test suite..." -ForegroundColor Cyan
        & $PythonExe -m pytest -v
    }
    "lint" {
        Write-Host "==> Running flake8 code linter..." -ForegroundColor Cyan
        & $PythonExe -m flake8 src tests --max-line-length=120
        if ($LASTEXITCODE -eq 0) { Write-Host "✓ Linting passed cleanly." -ForegroundColor Green }
    }
    "security" {
        Write-Host "==> Running Bandit security vulnerability scan..." -ForegroundColor Cyan
        & $PythonExe -m bandit -r src/
    }
    "run" {
        Write-Host "==> Starting OpsPulse Sentinel server locally on http://localhost:8000..." -ForegroundColor Cyan
        & $PythonExe -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
    }
    "docker-build" {
        Write-Host "==> Building Docker image 'opspulse-sentinel:latest'..." -ForegroundColor Cyan
        docker build -t opspulse-sentinel:latest .
    }
    "docker-up" {
        Write-Host "==> Starting Docker Compose stack..." -ForegroundColor Cyan
        docker compose up --build -d
    }
    "docker-down" {
        Write-Host "==> Stopping Docker Compose stack..." -ForegroundColor Cyan
        docker compose down
    }
    default {
        Write-Host "OpsPulse Task Helper - Available Commands:" -ForegroundColor Yellow
        Write-Host "  .\task.ps1 install       - Install Python dependencies"
        Write-Host "  .\task.ps1 test          - Run Pytest test suite"
        Write-Host "  .\task.ps1 lint          - Run Flake8 linter"
        Write-Host "  .\task.ps1 security      - Run Bandit security audit"
        Write-Host "  .\task.ps1 run           - Start local development server"
        Write-Host "  .\task.ps1 docker-build  - Build Docker container"
        Write-Host "  .\task.ps1 docker-up     - Start complete stack with Docker Compose"
        Write-Host "  .\task.ps1 docker-down   - Stop Docker Compose stack"
    }
}
