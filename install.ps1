# WhisperLiveKit Installation Script for Windows PowerShell
# This script installs all necessary dependencies for WhisperLiveKit on Windows

param(
    [switch]$Help,
    [switch]$SkipFFmpeg,
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
    Write-Host "WhisperLiveKit Installation Script for Windows" -ForegroundColor $colors.Blue
    Write-Host ""
    Write-Host "Usage: .\install.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Help         Show this help message"
    Write-Host "  -SkipFFmpeg   Skip FFmpeg installation check"
    Write-Host "  -NoVenv       Skip virtual environment creation"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\install.ps1                    # Full installation"
    Write-Host "  .\install.ps1 -SkipFFmpeg        # Skip FFmpeg check"
    Write-Host "  .\install.ps1 -NoVenv            # Install without virtual environment"
    Write-Host ""
}

function Test-Python {
    Write-Status "Checking Python installation..."
    
    $pythonCmd = $null
    $pythonVersion = $null
    
    # Try to find existing compatible Python installation
    foreach ($cmd in @("python", "python3", "py")) {
        try {
            $version = & $cmd --version 2>$null
            if ($LASTEXITCODE -eq 0) {
                # Extract version number
                $versionMatch = [regex]::Match($version, "Python (\d+\.\d+)")
                if ($versionMatch.Success) {
                    $versionNum = [version]$versionMatch.Groups[1].Value
                    if ($versionNum -ge [version]"3.9") {
                        $pythonCmd = $cmd
                        $pythonVersion = $version
                        break
                    }
                }
            }
        }
        catch {
            continue
        }
    }
    
    if ($pythonCmd) {
        Write-Success "Compatible Python found: $pythonVersion"
        return $pythonCmd
    }
    
    Write-Warning "Compatible Python (3.9+) not found. Attempting to install..."
    Install-Python
    
    # Try again after installation
    foreach ($cmd in @("python", "python3", "py")) {
        try {
            $version = & $cmd --version 2>$null
            if ($LASTEXITCODE -eq 0) {
                $versionMatch = [regex]::Match($version, "Python (\d+\.\d+)")
                if ($versionMatch.Success) {
                    $versionNum = [version]$versionMatch.Groups[1].Value
                    if ($versionNum -ge [version]"3.9") {
                        return $cmd
                    }
                }
            }
        }
        catch {
            continue
        }
    }
    
    Write-Error "Failed to install or find compatible Python version"
    exit 1
}

function Install-Python {
    Write-Status "Installing Python 3.11..."
    
    # Check if we can use winget
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Status "Installing Python via winget..."
        try {
            & winget install Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Python 3.11 installed via winget"
                # Refresh PATH
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
                return
            }
        }
        catch {
            Write-Warning "winget installation failed, trying manual download"
        }
    }
    
    # Manual download and installation
    Write-Status "Downloading Python 3.11 installer..."
    $pythonUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $installerPath = "$env:TEMP\python-3.11.9-installer.exe"
    
    try {
        Invoke-WebRequest -Uri $pythonUrl -OutFile $installerPath -UseBasicParsing
        
        Write-Status "Installing Python 3.11..."
        $arguments = @(
            "/quiet",
            "InstallAllUsers=1",
            "PrependPath=1",
            "Include_test=0",
            "Include_doc=0",
            "Include_dev=1",
            "Include_debug=0",
            "Include_launcher=1",
            "InstallLauncherAllUsers=1"
        )
        
        Start-Process -FilePath $installerPath -ArgumentList $arguments -Wait -NoNewWindow
        
        # Clean up
        Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
        
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        
        Write-Success "Python 3.11 installation completed"
    }
    catch {
        Write-Error "Failed to download or install Python: $_"
        Write-Status "Please download and install Python manually from: https://www.python.org/downloads/"
        exit 1
    }
}

function Install-CUDA {
    Write-Status "Checking CUDA installation..."
    
    # Check if NVIDIA GPU is present
    try {
        $nvidiaSmi = & nvidia-smi --query-gpu=name --format=csv,noheader,nounits 2>$null
        if ($LASTEXITCODE -eq 0 -and $nvidiaSmi) {
            Write-Success "NVIDIA GPU detected: $($nvidiaSmi -join ', ')"
            
            # Check if CUDA is already installed
            if (Get-Command nvcc -ErrorAction SilentlyContinue) {
                $cudaVersion = & nvcc --version 2>$null | Select-String "release (\d+\.\d+)" | ForEach-Object { $_.Matches[0].Groups[1].Value }
                if ($cudaVersion) {
                    Write-Success "CUDA $cudaVersion already installed"
                    return
                }
            }
            
            Write-Status "CUDA not found. Installing CUDA toolkit..."
            Install-CUDAToolkit
        }
        else {
            Write-Warning "No NVIDIA GPU detected. Skipping CUDA installation."
            Write-Status "The system will use CPU-only mode."
        }
    }
    catch {
        Write-Warning "Could not detect NVIDIA GPU. Skipping CUDA installation."
        Write-Status "The system will use CPU-only mode."
    }
}

function Install-CUDAToolkit {
    Write-Status "Installing CUDA Toolkit 11.8..."
    
    # Try winget first
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        try {
            & winget install Nvidia.CUDA --silent --accept-source-agreements --accept-package-agreements
            if ($LASTEXITCODE -eq 0) {
                Write-Success "CUDA Toolkit installed via winget"
                return
            }
        }
        catch {
            Write-Warning "winget CUDA installation failed, trying manual download"
        }
    }
    
    # Manual installation
    Write-Warning "Automatic CUDA installation not available."
    Write-Status "Please install CUDA manually:"
    Write-Status "1. Visit: https://developer.nvidia.com/cuda-downloads"
    Write-Status "2. Download CUDA Toolkit 11.8 for Windows"
    Write-Status "3. Run the installer with default settings"
    Write-Status "4. Restart PowerShell after installation"
    
    $continue = Read-Host "Continue installation without CUDA? (y/N)"
    if ($continue -notmatch "^[Yy]$") {
        Write-Status "Installation cancelled. Please install CUDA first."
        exit 1
    }
}

function Install-FFmpeg {
    if ($SkipFFmpeg) {
        Write-Warning "Skipping FFmpeg installation check as requested"
        return
    }
    
    Write-Status "Checking FFmpeg installation..."
    
    try {
        $ffmpegVersion = & ffmpeg -version 2>$null | Select-Object -First 1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "FFmpeg is already installed: $($ffmpegVersion -split ' ' | Select-Object -First 3 -Last 1)"
            return
        }
    }
    catch {
        # FFmpeg not found
    }
    
    Write-Warning "FFmpeg not found in PATH"
    Write-Status "FFmpeg is required for WhisperLiveKit to work properly"
    Write-Status ""
    Write-Status "To install FFmpeg on Windows:"
    Write-Status "1. Download from: https://ffmpeg.org/download.html#build-windows"
    Write-Status "2. Extract the archive"
    Write-Status "3. Add the 'bin' folder to your PATH environment variable"
    Write-Status "4. Restart PowerShell/Command Prompt"
    Write-Status ""
    
    $continue = Read-Host "Continue installation without FFmpeg? (y/N)"
    if ($continue -notmatch "^[Yy]$") {
        Write-Status "Installation cancelled. Please install FFmpeg first."
        exit 1
    }
}

function New-VirtualEnvironment {
    param([string]$PythonCmd)
    
    if ($NoVenv) {
        Write-Warning "Skipping virtual environment creation as requested"
        return $PythonCmd
    }
    
    Write-Status "Creating virtual environment..."
    
    if (Test-Path "venv") {
        Write-Warning "Virtual environment already exists. Skipping creation."
    }
    else {
        try {
            & $PythonCmd -m venv venv
            if ($LASTEXITCODE -ne 0) {
                throw "Virtual environment creation failed"
            }
            Write-Success "Virtual environment created"
        }
        catch {
            Write-Error "Failed to create virtual environment: $_"
            exit 1
        }
    }
    
    Write-Status "Activating virtual environment..."
    
    $venvScript = ".\venv\Scripts\Activate.ps1"
    if (Test-Path $venvScript) {
        try {
            & $venvScript
            Write-Success "Virtual environment activated"
            return "python"  # Use python after activation
        }
        catch {
            Write-Warning "Could not activate virtual environment: $_"
            Write-Status "Continuing with system Python..."
            return $PythonCmd
        }
    }
    else {
        Write-Warning "Virtual environment activation script not found"
        Write-Status "Continuing with system Python..."
        return $PythonCmd
    }
}

function Install-Dependencies {
    param([string]$PythonCmd)
    
    Write-Status "Installing WhisperLiveKit and dependencies..."
    
    try {
        # Upgrade pip first
        Write-Status "Upgrading pip..."
        & $PythonCmd -m pip install --upgrade pip
        
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to upgrade pip"
        }
        
        # Install PyTorch with CUDA support if NVIDIA GPU is available
        try {
            $nvidiaSmi = & nvidia-smi --query-gpu=name --format=csv,noheader,nounits 2>$null
            if ($LASTEXITCODE -eq 0 -and $nvidiaSmi) {
                Write-Status "Installing PyTorch with CUDA support..."
                & $PythonCmd -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
            }
            else {
                Write-Status "Installing PyTorch (CPU version)..."
                & $PythonCmd -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
            }
        }
        catch {
            Write-Status "Installing PyTorch (CPU version)..."
            & $PythonCmd -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
        }
        
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install PyTorch"
        }
        
        # Install the package in development mode
        Write-Status "Installing WhisperLiveKit in development mode..."
        & $PythonCmd -m pip install -e .
        
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install WhisperLiveKit"
        }
        
        # Install additional audio dependencies
        Write-Status "Installing additional audio processing dependencies..."
        & $PythonCmd -m pip install soundfile librosa
        
        # Install production server dependencies
        Write-Status "Installing production server dependencies..."
        & $PythonCmd -m pip install gunicorn uvicorn[standard]
        
        Write-Success "Core dependencies installed"
    }
    catch {
        Write-Error "Failed to install dependencies: $_"
        exit 1
    }
}

function Install-OptionalDependencies {
    param([string]$PythonCmd)
    
    Write-Status "Installing optional dependencies..."
    Write-Host ""
    Write-Status "Optional components available:"
    Write-Host "1. Speaker diarization with Diart - Recommended for speaker identification"
    Write-Host "2. OpenAI API backend - For using OpenAI's API instead of local models"
    Write-Host "3. Sentence tokenization support - For better text processing"
    Write-Host ""
    
    $installDiart = Read-Host "Install speaker diarization with Diart? (Y/n)"
    if ($installDiart -match "^[Yy]$" -or $installDiart -eq "") {
        Write-Status "Installing Diart for speaker diarization..."
        try {
            # Install specific versions for compatibility
            & $PythonCmd -m pip install torch==2.0.1 torchaudio==2.0.2
            & $PythonCmd -m pip install pyannote.audio==3.1.1
            & $PythonCmd -m pip install diart
            Write-Success "Diart dependencies installed"
            
            Write-Warning "Don't forget to:"
            Write-Status "1. Accept user conditions for pyannote models on Hugging Face"
            Write-Status "2. Set your HUGGINGFACE_HUB_TOKEN in .env file"
            Write-Status "3. Login with: huggingface-cli login"
        }
        catch {
            Write-Warning "Failed to install Diart dependencies: $_"
        }
    }
    
    $installOpenAI = Read-Host "Install OpenAI API backend? (y/N)"
    if ($installOpenAI -match "^[Yy]$") {
        Write-Status "Installing OpenAI..."
        try {
            & $PythonCmd -m pip install openai
            Write-Success "OpenAI API backend installed"
        }
        catch {
            Write-Warning "Failed to install OpenAI: $_"
        }
    }
    
    $installSentence = Read-Host "Install sentence tokenization support? (y/N)"
    if ($installSentence -match "^[Yy]$") {
        Write-Status "Installing sentence tokenization..."
        try {
            & $PythonCmd -m pip install mosestokenizer wtpsplit
            Write-Success "Sentence tokenization installed"
        }
        catch {
            Write-Warning "Failed to install sentence tokenization: $_"
        }
    }
    
    # Install faster-whisper as alternative backend
    $installFaster = Read-Host "Install faster-whisper backend? (Y/n)"
    if ($installFaster -match "^[Yy]$" -or $installFaster -eq "") {
        Write-Status "Installing faster-whisper..."
        try {
            & $PythonCmd -m pip install faster-whisper
            Write-Success "faster-whisper installed"
        }
        catch {
            Write-Warning "Failed to install faster-whisper: $_"
        }
    }
}

function New-ConfigurationFiles {
    Write-Status "Creating configuration files..."
    
    # Create models directory
    Write-Status "Creating models directory structure..."
    @("models\whisper", "models\silero_vad", "models\cif", "models\cache", "logs") | ForEach-Object {
        if (-not (Test-Path $_)) {
            New-Item -ItemType Directory -Path $_ -Force | Out-Null
        }
    }
    
    # Download CIF models for large-v2 support
    Get-CifModels
    
    if (-not (Test-Path "env.example")) {
        Write-Status "env.example configuration file should be created separately"
    }
    else {
        Write-Success "Configuration files are ready"
    }
    
    Write-Status "Directory structure created:"
    Write-Host "  .\models\whisper\     - Whisper model files"
    Write-Host "  .\models\silero_vad\  - VAD model files"
    Write-Host "  .\models\cif\         - CIF model files (downloaded)"
    Write-Host "  .\models\cache\       - Temporary cache"
    Write-Host "  .\logs\               - Server logs"
}

# Download CIF models for improved word boundary detection
function Get-CifModels {
    Write-Status "Downloading CIF models for word boundary detection..."
    
    # CIF models URLs from GitHub repository
    $cifModels = @{
        "cif_base.ckpt" = "https://github.com/backspacetg/simul_whisper/raw/main/cif_models/cif_base.ckpt"
        "cif_small.ckpt" = "https://github.com/backspacetg/simul_whisper/raw/main/cif_models/cif_small.ckpt"
        "cif_medium.ckpt" = "https://github.com/backspacetg/simul_whisper/raw/main/cif_models/cif_medium.ckpt"
        "cif_large.ckpt" = "https://github.com/backspacetg/simul_whisper/raw/main/cif_models/cif_large.ckpt"
    }
    
    # Create CIF directory
    New-Item -ItemType Directory -Path "models\cif" -Force | Out-Null
    
    # Download each CIF model
    foreach ($modelName in $cifModels.Keys) {
        $modelUrl = $cifModels[$modelName]
        $modelPath = "models\cif\$modelName"
        
        if (-not (Test-Path $modelPath)) {
            Write-Status "Downloading $modelName..."
            
            try {
                # Use Invoke-WebRequest to download
                Invoke-WebRequest -Uri $modelUrl -OutFile $modelPath -UseBasicParsing
                Write-Success "Downloaded $modelName"
            }
            catch {
                Write-Warning "Failed to download $modelName : $_"
                # Remove partial file if it exists
                if (Test-Path $modelPath) {
                    Remove-Item $modelPath -Force
                }
            }
        }
        else {
            Write-Success "$modelName already exists"
        }
    }
    
    # Check if we successfully downloaded the large model for large-v2
    if (Test-Path "models\cif\cif_large.ckpt") {
        Write-Success "CIF model for large-v2 is ready"
    }
    else {
        Write-Warning "CIF model for large-v2 not available. Using fallback configuration."
        Write-Status "You can download manually from: https://github.com/backspacetg/simul_whisper/tree/main/cif_models"
    }
}

function Test-Installation {
    param([string]$PythonCmd)
    
    Write-Status "Verifying installation..."
    
    try {
        $importTest = & $PythonCmd -c "import whisperlivekit; print('WhisperLiveKit imported successfully')" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "WhisperLiveKit installation verified"
        }
        else {
            throw "Import test failed"
        }
    }
    catch {
        Write-Error "WhisperLiveKit installation verification failed: $_"
        exit 1
    }
    
    # Test PyTorch
    try {
        $torchTest = & $PythonCmd -c "import torch; print(f'PyTorch {torch.__version__} installed')" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "PyTorch is working"
            
            # Check CUDA availability
            $cudaTest = & $PythonCmd -c "import torch; print('CUDA available:', torch.cuda.is_available())" 2>$null
            if ($cudaTest -match "True") {
                $gpuCount = & $PythonCmd -c "import torch; print(torch.cuda.device_count())" 2>$null
                Write-Success "CUDA is available with $gpuCount GPU(s)"
            }
            else {
                Write-Warning "CUDA is not available. Using CPU mode."
            }
        }
    }
    catch {
        Write-Warning "PyTorch installation issue detected"
    }
    
    # Test FFmpeg only if not skipped
    if (-not $SkipFFmpeg) {
        try {
            & ffmpeg -version 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Success "FFmpeg is accessible"
            }
            else {
                Write-Warning "FFmpeg is not accessible but installation continues"
            }
        }
        catch {
            Write-Warning "FFmpeg is not accessible but installation continues"
        }
    }
    
    # Test optional components
    try {
        & $PythonCmd -c "import diart" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Diart is available for speaker diarization"
        }
    }
    catch {}
}

function Main {
    if ($Help) {
        Show-Help
        return
    }
    
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor $colors.Blue
    Write-Host "           WhisperLiveKit Installation Script" -ForegroundColor $colors.Blue
    Write-Host "================================================================" -ForegroundColor $colors.Blue
    Write-Host ""
    
    Write-Status "Starting WhisperLiveKit installation..."
    Write-Host ""
    
    $pythonCmd = Test-Python
    Install-CUDA
    Install-FFmpeg
    $pythonCmd = New-VirtualEnvironment -PythonCmd $pythonCmd
    Install-Dependencies -PythonCmd $pythonCmd
    Install-OptionalDependencies -PythonCmd $pythonCmd
    New-ConfigurationFiles
    Test-Installation -PythonCmd $pythonCmd
    
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor $colors.Green
    Write-Host "           Installation completed successfully!" -ForegroundColor $colors.Green
    Write-Host "================================================================" -ForegroundColor $colors.Green
    Write-Host ""
    Write-Status "Next steps:"
    Write-Host "1. Copy env.example to .env and configure your settings"
    Write-Host "2. If using Diart: set HUGGINGFACE_HUB_TOKEN in .env"
    Write-Host "3. Run '.\start.ps1' to start the server"
    Write-Host "4. Open http://localhost:8000 in your browser"
    Write-Host ""
    
    if (-not $NoVenv) {
        Write-Status "To activate the virtual environment manually:"
        Write-Host ".\venv\Scripts\Activate.ps1"
        Write-Host ""
    }
    
    try {
        $nvidiaSmi = & nvidia-smi --query-gpu=name --format=csv,noheader,nounits 2>$null
        if ($LASTEXITCODE -eq 0 -and $nvidiaSmi) {
            Write-Status "GPU acceleration is available. The system will use CUDA when possible."
        }
        else {
            Write-Status "No GPU detected. The system will run in CPU mode."
        }
    }
    catch {
        Write-Status "No GPU detected. The system will run in CPU mode."
    }
    Write-Host ""
}

# Run main function
Main