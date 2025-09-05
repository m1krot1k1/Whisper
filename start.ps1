# WhisperLiveKit Startup Script for Windows PowerShell
# This script starts the WhisperLiveKit server with configuration from environment

param(
    [string]$Config = ".env",
    [switch]$Help,
    [switch]$Dev,
    [switch]$NoVenv
)

# Colors for output
$colors = @{
    Red = "Red"
    Green = "Green"
    Yellow = "Yellow"
    Blue = "Blue"
    White = "White"
}

function Write-Status {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor $colors.Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor $colors.Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor $colors.Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor $colors.Red
}

function Show-Help {
    Write-Host "WhisperLiveKit Startup Script for Windows" -ForegroundColor $colors.Blue
    Write-Host ""
    Write-Host "Usage: .\start.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Config FILE    Use specific configuration file (default: .env)"
    Write-Host "  -Help           Show this help message"
    Write-Host "  -Dev            Start in development mode with debug logging"
    Write-Host "  -NoVenv         Skip virtual environment activation"
    Write-Host ""
    Write-Host "Environment Variables:"
    Write-Host "  All WLK_* variables from .env file will be used as server configuration"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\start.ps1                          # Start with default configuration"
    Write-Host "  .\start.ps1 -Config production.env   # Start with specific config file"
    Write-Host "  .\start.ps1 -Dev                     # Start in development mode"
    Write-Host ""
}

function Import-EnvironmentFile {
    param([string]$FilePath)
    
    if (Test-Path $FilePath) {
        Write-Status "Loading configuration from $FilePath"
        
        Get-Content $FilePath | ForEach-Object {
            $line = $_.Trim()
            # Skip empty lines and comments
            if ($line -and -not $line.StartsWith("#")) {
                # Handle lines with = sign
                if ($line -match "^([^=]+)=(.*)$") {
                    $name = $matches[1].Trim()
                    $value = $matches[2].Trim()
                    
                    # Remove quotes if present
                    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or 
                        ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                        $value = $value.Substring(1, $value.Length - 2)
                    }
                    
                    # Set environment variable
                    [Environment]::SetEnvironmentVariable($name, $value, "Process")
                }
            }
        }
        
        # Special handling for Hugging Face token
        if ($env:HUGGINGFACE_HUB_TOKEN) {
            Write-Status "Hugging Face token loaded for Diart access"
        }
        
        Write-Success "Configuration loaded"
    }
    elseif (Test-Path "env.example") {
        Write-Warning "No $FilePath file found. Using env.example as template."
        Write-Status "Please copy env.example to .env and configure your settings."
        Write-Status "Using default configuration for now..."
        Import-EnvironmentFile "env.example"
    }
    else {
        Write-Warning "No configuration file found. Using default settings."
    }
}

function Enable-VirtualEnvironment {
    if ($NoVenv) {
        Write-Warning "Skipping virtual environment activation as requested"
        return "python"
    }
    
    if (Test-Path "venv") {
        Write-Status "Activating virtual environment..."
        $venvScript = ".\venv\Scripts\Activate.ps1"
        
        if (Test-Path $venvScript) {
            try {
                & $venvScript
                Write-Success "Virtual environment activated"
                return "python"
            }
            catch {
                Write-Warning "Could not activate virtual environment: $_"
                Write-Status "Continuing with system Python..."
            }
        }
        else {
            Write-Warning "Virtual environment activation script not found"
            Write-Status "Continuing with system Python..."
        }
    }
    else {
        Write-Warning "Virtual environment not found. Creating new virtual environment..."
        
        # Find Python command
        $pythonCmd = $null
        foreach ($cmd in @("python", "python3")) {
            try {
                & $cmd --version 2>$null | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    $pythonCmd = $cmd
                    break
                }
            }
            catch {
                continue
            }
        }
        
        if (-not $pythonCmd) {
            Write-Error "Python not found. Please install Python 3.9+ first."
            exit 1
        }
        
        # Create virtual environment
        Write-Status "Creating virtual environment with $pythonCmd..."
        & $pythonCmd -m venv venv
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Virtual environment created successfully"
            $venvScript = ".\venv\Scripts\Activate.ps1"
            
            if (Test-Path $venvScript) {
                & $venvScript
                Write-Success "Virtual environment activated"
                
                # Install the package in development mode
                Write-Status "Installing WhisperLiveKit in development mode..."
                & python -m pip install --upgrade pip
                & python -m pip install -e .
                
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "WhisperLiveKit installed successfully"
                }
                else {
                    Write-Warning "Failed to install WhisperLiveKit. You may need to run install.ps1 first."
                }
                
                return "python"
            }
            else {
                Write-Warning "Virtual environment activation script not found"
            }
        }
        else {
            Write-Error "Failed to create virtual environment"
            exit 1
        }
    }
    
    # Return appropriate Python command
    foreach ($cmd in @("python", "python3")) {
        try {
            & $cmd --version 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                return $cmd
            }
        }
        catch {
            continue
        }
    }
    
    Write-Error "No Python installation found"
    exit 1
}

function Test-Installation {
    param([string]$PythonCmd)
    
    Write-Status "Checking WhisperLiveKit installation..."
    
    try {
        & $PythonCmd -c "import whisperlivekit" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "WhisperLiveKit is installed"
        }
        else {
            throw "WhisperLiveKit import failed"
        }
    }
    catch {
        Write-Error "WhisperLiveKit is not installed. Please run install.ps1 first."
        exit 1
    }
    
    # Check FFmpeg
    try {
        & ffmpeg -version 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "FFmpeg is available"
        }
        else {
            Write-Warning "FFmpeg not found. Some features may not work properly."
        }
    }
    catch {
        Write-Warning "FFmpeg not found. Some features may not work properly."
    }
}

function Build-Arguments {
    $args = @()
    
    # Basic server settings
    if ($env:WLK_HOST) { $args += @("--host", $env:WLK_HOST) }
    if ($env:WLK_PORT) { $args += @("--port", $env:WLK_PORT) }
    
    # Model settings
    if ($env:WLK_MODEL) { $args += @("--model", $env:WLK_MODEL) }
    if ($env:WLK_LANGUAGE) { $args += @("--language", $env:WLK_LANGUAGE) }
    if ($env:WLK_TASK) { $args += @("--task", $env:WLK_TASK) }
    if ($env:WLK_BACKEND) { $args += @("--backend", $env:WLK_BACKEND) }
    
    # Audio processing settings
    if ($env:WLK_MIN_CHUNK_SIZE) { $args += @("--min-chunk-size", $env:WLK_MIN_CHUNK_SIZE) }
    if ($env:WLK_WARMUP_FILE) { $args += @("--warmup-file", $env:WLK_WARMUP_FILE) }
    
    # SSL settings
    if ($env:WLK_SSL_CERTFILE) { $args += @("--ssl-certfile", $env:WLK_SSL_CERTFILE) }
    if ($env:WLK_SSL_KEYFILE) { $args += @("--ssl-keyfile", $env:WLK_SSL_KEYFILE) }
    
    # Voice Activity Detection
    if ($env:WLK_NO_VAD -eq "true") { $args += "--no-vad" }
    if ($env:WLK_NO_VAC -eq "true") { $args += "--no-vac" }
    if ($env:WLK_VAC_CHUNK_SIZE) { $args += @("--vac-chunk-size", $env:WLK_VAC_CHUNK_SIZE) }
    
    # Diarization settings
    if ($env:WLK_DIARIZATION -eq "true") { $args += "--diarization" }
    if ($env:WLK_DIARIZATION_BACKEND) { $args += @("--diarization-backend", $env:WLK_DIARIZATION_BACKEND) }
    if ($env:WLK_SEGMENTATION_MODEL) { $args += @("--segmentation-model", $env:WLK_SEGMENTATION_MODEL) }
    if ($env:WLK_EMBEDDING_MODEL) { $args += @("--embedding-model", $env:WLK_EMBEDDING_MODEL) }
    if ($env:WLK_PUNCTUATION_SPLIT -eq "true") { $args += "--punctuation-split" }
    
    # SimulStreaming specific settings
    if ($env:WLK_DISABLE_FAST_ENCODER -eq "true") { $args += "--disable-fast-encoder" }
    if ($env:WLK_FRAME_THRESHOLD) { $args += @("--frame-threshold", $env:WLK_FRAME_THRESHOLD) }
    if ($env:WLK_BEAMS) { $args += @("--beams", $env:WLK_BEAMS) }
    if ($env:WLK_DECODER_TYPE) { $args += @("--decoder", $env:WLK_DECODER_TYPE) }
    if ($env:WLK_AUDIO_MAX_LEN) { $args += @("--audio-max-len", $env:WLK_AUDIO_MAX_LEN) }
    if ($env:WLK_AUDIO_MIN_LEN) { $args += @("--audio-min-len", $env:WLK_AUDIO_MIN_LEN) }
    if ($env:WLK_CIF_CKPT_PATH) { $args += @("--cif-ckpt-path", $env:WLK_CIF_CKPT_PATH) }
    if ($env:WLK_NEVER_FIRE -eq "true") { $args += "--never-fire" }
    if ($env:WLK_INIT_PROMPT) { $args += @("--init-prompt", $env:WLK_INIT_PROMPT) }
    if ($env:WLK_STATIC_INIT_PROMPT) { $args += @("--static-init-prompt", $env:WLK_STATIC_INIT_PROMPT) }
    if ($env:WLK_MAX_CONTEXT_TOKENS) { $args += @("--max-context-tokens", $env:WLK_MAX_CONTEXT_TOKENS) }
    if ($env:WLK_MODEL_PATH) { $args += @("--model-path", $env:WLK_MODEL_PATH) }
    if ($env:WLK_PRELOADED_MODEL_COUNT) { $args += @("--preloaded_model_count", $env:WLK_PRELOADED_MODEL_COUNT) }
    
    # Buffer settings
    if ($env:WLK_BUFFER_TRIMMING) { $args += @("--buffer_trimming", $env:WLK_BUFFER_TRIMMING) }
    if ($env:WLK_BUFFER_TRIMMING_SEC) { $args += @("--buffer_trimming_sec", $env:WLK_BUFFER_TRIMMING_SEC) }
    
    # Other settings
    if ($env:WLK_CONFIDENCE_VALIDATION -eq "true") { $args += "--confidence-validation" }
    if ($env:WLK_NO_TRANSCRIPTION -eq "true") { $args += "--no-transcription" }
    if ($env:WLK_LOG_LEVEL) { $args += @("--log-level", $env:WLK_LOG_LEVEL) }
    if ($env:WLK_MODEL_CACHE_DIR) { $args += @("--model_cache_dir", $env:WLK_MODEL_CACHE_DIR) }
    if ($env:WLK_MODEL_DIR) { $args += @("--model_dir", $env:WLK_MODEL_DIR) }
    
    return $args
}

function Show-StartupInfo {
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor $colors.Blue
    Write-Host "           WhisperLiveKit Server Starting" -ForegroundColor $colors.Blue
    Write-Host "================================================================" -ForegroundColor $colors.Blue
    Write-Host ""
    Write-Status "Configuration:"
    Write-Host "  Host: $($env:WLK_HOST ?? 'localhost')"
    Write-Host "  Port: $($env:WLK_PORT ?? '8000')"
    Write-Host "  Model: $($env:WLK_MODEL ?? 'small')"
    Write-Host "  Language: $($env:WLK_LANGUAGE ?? 'auto')"
    Write-Host "  Backend: $($env:WLK_BACKEND ?? 'simulstreaming')"
    Write-Host "  Diarization: $($env:WLK_DIARIZATION ?? 'false')"
    Write-Host ""
    
    $host = $env:WLK_HOST ?? 'localhost'
    $port = $env:WLK_PORT ?? '8000'
    
    if ($env:WLK_SSL_CERTFILE -and $env:WLK_SSL_KEYFILE) {
        Write-Status "Server will be available at: https://${host}:${port}"
    }
    else {
        Write-Status "Server will be available at: http://${host}:${port}"
    }
    Write-Host ""
}

function Start-Server {
    $arguments = Build-Arguments
    
    Write-Status "Starting WhisperLiveKit server..."
    
    if ($arguments.Count -gt 0) {
        $argString = $arguments -join " "
        Write-Status "Command: whisperlivekit-server $argString"
    }
    else {
        Write-Status "Command: whisperlivekit-server"
    }
    
    Write-Host ""
    
    try {
        if ($arguments.Count -gt 0) {
            & whisperlivekit-server @arguments
        }
        else {
            & whisperlivekit-server
        }
    }
    catch {
        Write-Error "Failed to start server: $_"
        exit 1
    }
}

function Main {
    if ($Help) {
        Show-Help
        return
    }
    
    # Load configuration
    Import-EnvironmentFile $Config
    
    # Activate virtual environment if requested
    $pythonCmd = Enable-VirtualEnvironment
    
    # Check installation
    Test-Installation $pythonCmd
    
    # Set development mode if requested
    if ($Dev) {
        Write-Status "Starting in development mode..."
        [Environment]::SetEnvironmentVariable("WLK_LOG_LEVEL", ($env:WLK_LOG_LEVEL ?? "DEBUG"), "Process")
    }
    
    # Show startup information
    Show-StartupInfo
    
    # Set up Ctrl+C handler
    $handler = {
        Write-Host ""
        Write-Status "Shutting down server..."
        Write-Success "Server stopped"
        exit 0
    }
    
    [Console]::CancelKeyPress += $handler
    
    # Start the server
    Start-Server
}

# Run main function
try {
    Main
}
catch {
    Write-Error "Unexpected error: $_"
    exit 1
}
finally {
    # Cleanup if needed
}