#!/usr/bin/env pwsh

# WhisperLiveKit Startup Script for Windows PowerShell
# This script starts the WhisperLiveKit adaptive server with configuration from environment

param(
    [string]$Host = "localhost",
    [int]$Port = 8000,
    [string]$Model = "tiny", 
    [string]$Language = "auto",
    [string]$Backend = "faster-whisper",
    [switch]$Help
)

# Colors for output (PowerShell compatible)
function Write-Status {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

if ($Help) {
    Write-Host @"
WhisperLiveKit Adaptive Server Startup Script

Usage: .\start.ps1 [OPTIONS]

Options:
  -Host <string>       Server host (default: localhost)
  -Port <int>          Server port (default: 8000)
  -Model <string>      Whisper model size (default: tiny)
  -Language <string>   Language for transcription (default: auto)
  -Backend <string>    Backend to use (default: faster-whisper)
  -Help               Show this help message

Examples:
  .\start.ps1
  .\start.ps1 -Host "0.0.0.0" -Port 8080 -Model "base"
  .\start.ps1 -Language "ru" -Model "small"
"@
    exit 0
}

# Print startup banner
Write-Host @"

╔══════════════════════════════════════════════════════════════╗
║                    WhisperLiveKit                             ║
║              Адаптивный Сервер Транскрипции                  ║
║                с Контекстной Коррекцией                      ║
╚══════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan

Write-Status "Проверка зависимостей..."

# Check if Python is available
try {
    $pythonVersion = python --version 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Python найден: $pythonVersion"
    } else {
        throw "Python не найден"
    }
} catch {
    Write-Error "Python не установлен или недоступен в PATH"
    Write-Warning "Пожалуйста, установите Python 3.8+ и добавьте его в PATH"
    exit 1
}

# Check if whisperlivekit module is available
try {
    python -c "import whisperlivekit" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Success "WhisperLiveKit модуль найден"
    } else {
        throw "WhisperLiveKit не найден"
    }
} catch {
    Write-Error "WhisperLiveKit модуль не найден"
    Write-Warning "Запустите: pip install -e ."
    exit 1
}

# Load environment variables from .env file if it exists
if (Test-Path ".env") {
    Write-Status "Загрузка переменных окружения из .env..."
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^\s*([^#\s]+)\s*=\s*(.+)\s*$") {
            $name = $matches[1]
            $value = $matches[2]
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

# Build command arguments
$args = @()
$args += "--host", $Host
$args += "--port", $Port
$args += "--model", $Model
$args += "--lan", $Language
$args += "--backend", $Backend

Write-Status "Настройки сервера:"
Write-Host "  Host: $Host" -ForegroundColor Gray
Write-Host "  Port: $Port" -ForegroundColor Gray  
Write-Host "  Model: $Model" -ForegroundColor Gray
Write-Host "  Language: $Language" -ForegroundColor Gray
Write-Host "  Backend: $Backend" -ForegroundColor Gray
Write-Host ""

Write-Status "Запуск WhisperLiveKit адаптивного сервера..."
Write-Status "URL: http://$Host`:$Port"
Write-Status "WebSocket: ws://$Host`:$Port/asr"
Write-Host ""

Write-Success "Сервер запускается с контекстной коррекцией в реальном времени!"
Write-Host ""

# Start the adaptive server
try {
    python -m whisperlivekit.adaptive_basic_server @args
} catch {
    Write-Error "Ошибка при запуске сервера: $_"
    exit 1
}
