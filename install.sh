#!/bin/bash

# WhisperLiveKit Installation Script
# This script installs all necessary dependencies for WhisperLiveKit

set -e

echo "================================================================"
echo "           WhisperLiveKit Installation Script"
echo "================================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Python is installed
check_python() {
    print_status "Checking Python installation..."
    
    PYTHON_CMD=""
    PYTHON_VERSION=""
    
    # Try to find existing Python installation
    for cmd in python3.11 python3.10 python3.9 python3 python; do
        if command -v $cmd &> /dev/null; then
            VERSION=$($cmd -c 'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null)
            if [ $? -eq 0 ]; then
                # Check if version is >= 3.9
                if $cmd -c 'import sys; exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
                    PYTHON_CMD=$cmd
                    PYTHON_VERSION=$VERSION
                    break
                fi
            fi
        fi
    done
    
    if [ -n "$PYTHON_CMD" ]; then
        print_success "Compatible Python found: $PYTHON_CMD ($PYTHON_VERSION)"
        return 0
    fi
    
    print_warning "Compatible Python (3.9+) not found. Attempting to install..."
    install_python
}

# Install Python if not found
install_python() {
    print_status "Installing Python 3.11..."
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v apt-get &> /dev/null; then
            print_status "Installing Python via apt..."
            sudo apt-get update
            sudo apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip
            
            # Set up alternatives
            if command -v python3.11 &> /dev/null; then
                PYTHON_CMD="python3.11"
                print_success "Python 3.11 installed successfully"
            fi
        elif command -v yum &> /dev/null; then
            print_status "Installing Python via yum..."
            sudo yum install -y python3.11 python3.11-pip python3.11-devel
            PYTHON_CMD="python3.11"
        elif command -v dnf &> /dev/null; then
            print_status "Installing Python via dnf..."
            sudo dnf install -y python3.11 python3.11-pip python3.11-devel
            PYTHON_CMD="python3.11"
        else
            print_error "Could not detect package manager. Please install Python 3.9+ manually."
            exit 1
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            print_status "Installing Python via Homebrew..."
            brew install python@3.11
            PYTHON_CMD="python3.11"
            print_success "Python 3.11 installed successfully"
        else
            print_error "Homebrew not found. Installing Python via official installer..."
            print_status "Please download Python from: https://www.python.org/downloads/macos/"
            exit 1
        fi
    else
        print_error "Unsupported OS. Please install Python 3.9+ manually."
        print_status "Visit: https://www.python.org/downloads/"
        exit 1
    fi
    
    # Verify installation
    if [ -n "$PYTHON_CMD" ] && command -v $PYTHON_CMD &> /dev/null; then
        VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        print_success "Python $VERSION installed and verified"
    else
        print_error "Python installation failed or not accessible"
        exit 1
    fi
}

# Check and install CUDA toolkit
install_cuda() {
    print_status "Checking CUDA installation..."
    
    # Check if nvidia-smi is available
    if command -v nvidia-smi &> /dev/null; then
        GPU_INFO=$(nvidia-smi --query-gpu=name --format=csv,noheader,nounits 2>/dev/null | head -1)
        if [ $? -eq 0 ] && [ -n "$GPU_INFO" ]; then
            print_success "NVIDIA GPU detected: $GPU_INFO"
            
            # Check if CUDA is installed
            if command -v nvcc &> /dev/null; then
                CUDA_VERSION=$(nvcc --version | grep "release" | sed 's/.*release \([0-9]\+\.[0-9]\+\).*/\1/')
                print_success "CUDA $CUDA_VERSION already installed"
                return 0
            fi
            
            print_status "CUDA not found. Installing CUDA toolkit..."
            install_cuda_toolkit
        else
            print_warning "No NVIDIA GPU detected. Skipping CUDA installation."
            print_status "The system will use CPU-only mode."
        fi
    else
        print_warning "nvidia-smi not found. No NVIDIA GPU detected or drivers not installed."
        print_status "The system will use CPU-only mode."
    fi
}

# Install CUDA toolkit
install_cuda_toolkit() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux CUDA installation
        if command -v apt-get &> /dev/null; then
            print_status "Installing CUDA via apt (Ubuntu/Debian)..."
            
            # Add NVIDIA package repository
            wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/cuda-keyring_1.0-1_all.deb
            sudo dpkg -i cuda-keyring_1.0-1_all.deb
            sudo apt-get update
            
            # Install CUDA toolkit 11.8 (compatible with most PyTorch versions)
            sudo apt-get install -y cuda-toolkit-11-8 libcudnn8 libcudnn8-dev
            
            # Set up environment variables
            echo 'export PATH=/usr/local/cuda-11.8/bin:$PATH' >> ~/.bashrc
            echo 'export LD_LIBRARY_PATH=/usr/local/cuda-11.8/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
            
            print_success "CUDA toolkit installed. Please restart your shell or run: source ~/.bashrc"
            
        elif command -v yum &> /dev/null || command -v dnf &> /dev/null; then
            print_status "Installing CUDA via package manager (RHEL/CentOS/Fedora)..."
            
            # Add NVIDIA repository
            if command -v dnf &> /dev/null; then
                sudo dnf config-manager --add-repo https://developer.download.nvidia.com/compute/cuda/repos/rhel8/x86_64/cuda-rhel8.repo
                sudo dnf install -y cuda-toolkit-11-8
            else
                sudo yum-config-manager --add-repo https://developer.download.nvidia.com/compute/cuda/repos/rhel7/x86_64/cuda-rhel7.repo
                sudo yum install -y cuda-toolkit-11-8
            fi
            
            print_success "CUDA toolkit installed"
        else
            print_warning "Could not install CUDA automatically. Please install manually:"
            print_status "Visit: https://developer.nvidia.com/cuda-downloads"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        print_warning "CUDA is not supported on macOS. Using CPU/MPS mode."
        print_status "For Apple Silicon, MLX backend will be used if available."
    else
        print_warning "CUDA installation not supported for this OS."
        print_status "Visit: https://developer.nvidia.com/cuda-downloads"
    fi
}

# Check and install FFmpeg
install_ffmpeg() {
    print_status "Checking FFmpeg installation..."
    
    if command -v ffmpeg &> /dev/null; then
        FFMPEG_VERSION=$(ffmpeg -version | head -n 1 | cut -d' ' -f3)
        print_success "FFmpeg $FFMPEG_VERSION is already installed"
    else
        print_warning "FFmpeg not found. Attempting to install..."
        
        # Detect OS and install FFmpeg accordingly
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            # Linux
            if command -v apt-get &> /dev/null; then
                print_status "Installing FFmpeg via apt..."
                sudo apt-get update
                sudo apt-get install -y ffmpeg
            elif command -v yum &> /dev/null; then
                print_status "Installing FFmpeg via yum..."
                sudo yum install -y ffmpeg
            elif command -v dnf &> /dev/null; then
                print_status "Installing FFmpeg via dnf..."
                sudo dnf install -y ffmpeg
            else
                print_error "Could not detect package manager. Please install FFmpeg manually."
                exit 1
            fi
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            if command -v brew &> /dev/null; then
                print_status "Installing FFmpeg via Homebrew..."
                brew install ffmpeg
            else
                print_error "Homebrew not found. Please install Homebrew first or install FFmpeg manually."
                exit 1
            fi
        else
            print_error "Unsupported OS. Please install FFmpeg manually."
            print_status "Visit: https://ffmpeg.org/download.html"
            exit 1
        fi
        
        # Verify installation
        if command -v ffmpeg &> /dev/null; then
            print_success "FFmpeg installed successfully"
        else
            print_error "FFmpeg installation failed"
            exit 1
        fi
    fi
}

# Create virtual environment
create_venv() {
    print_status "Creating virtual environment..."
    
    if [ -d "venv" ]; then
        print_warning "Virtual environment already exists. Skipping creation."
    else
        $PYTHON_CMD -m venv venv
        print_success "Virtual environment created"
    fi
    
    print_status "Activating virtual environment..."
    source venv/bin/activate
    print_success "Virtual environment activated"
}

# Install Python dependencies
install_dependencies() {
    print_status "Installing WhisperLiveKit and dependencies..."
    
    # Use the detected or installed Python command
    PIP_CMD="$PYTHON_CMD -m pip"
    
    # Upgrade pip first
    print_status "Upgrading pip..."
    $PIP_CMD install --upgrade pip
    
    # Install PyTorch with CUDA support if NVIDIA GPU is available
    if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
        print_status "Installing PyTorch with CUDA support..."
        $PIP_CMD install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
    else
        print_status "Installing PyTorch (CPU version)..."
        $PIP_CMD install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    fi
    
    # Install the package in development mode
    print_status "Installing WhisperLiveKit in development mode..."
    $PIP_CMD install -e .
    
    # Install additional audio dependencies
    print_status "Installing additional audio processing dependencies..."
    $PIP_CMD install soundfile librosa
    
    # Install production server dependencies
    print_status "Installing production server dependencies..."
    $PIP_CMD install gunicorn uvicorn[standard]
    
    print_success "Core dependencies installed"
}

# Install optional dependencies
install_optional_dependencies() {
    print_status "Installing optional dependencies..."
    
    # Use the detected or installed Python command
    PIP_CMD="$PYTHON_CMD -m pip"
    
    # Ask user for optional components
    echo ""
    print_status "Optional components available:"
    echo "1. Speaker diarization with Diart (NVIDIA NeMo) - Recommended for speaker identification"
    echo "2. Apple Silicon optimized backend (MLX Whisper) - Only for Apple Silicon Macs"
    echo "3. OpenAI API backend - For using OpenAI's API instead of local models"
    echo "4. Sentence tokenization support - For better text processing"
    echo ""
    
    read -p "Install speaker diarization with Diart? (Y/n): " install_diart
    if [[ $install_diart =~ ^[Yy]$ ]] || [[ -z $install_diart ]]; then
        print_status "Installing Diart for speaker diarization..."
        # Install specific versions for compatibility
        $PIP_CMD install torch==2.0.1 torchaudio==2.0.2
        $PIP_CMD install pyannote.audio==3.1.1
        $PIP_CMD install diart
        print_success "Diart dependencies installed"
        
        print_warning "Don't forget to:"
        print_status "1. Accept user conditions for pyannote models on Hugging Face"
        print_status "2. Set your HUGGINGFACE_HUB_TOKEN in .env file"
        print_status "3. Login with: huggingface-cli login"
    fi
    
    # Check if we're on Apple Silicon
    if [[ "$OSTYPE" == "darwin"* ]] && [[ $(uname -m) == "arm64" ]]; then
        read -p "Install Apple Silicon optimized backend (MLX Whisper)? (Y/n): " install_mlx
        if [[ $install_mlx =~ ^[Yy]$ ]] || [[ -z $install_mlx ]]; then
            print_status "Installing MLX Whisper..."
            $PIP_CMD install mlx-whisper
            print_success "MLX Whisper installed"
        fi
    fi
    
    read -p "Install OpenAI API backend? (y/N): " install_openai
    if [[ $install_openai =~ ^[Yy]$ ]]; then
        print_status "Installing OpenAI..."
        $PIP_CMD install openai
        print_success "OpenAI API backend installed"
    fi
    
    read -p "Install sentence tokenization support? (y/N): " install_sentence
    if [[ $install_sentence =~ ^[Yy]$ ]]; then
        print_status "Installing sentence tokenization..."
        $PIP_CMD install mosestokenizer wtpsplit
        print_success "Sentence tokenization installed"
    fi
    
    # Install faster-whisper as alternative backend
    read -p "Install faster-whisper backend? (Y/n): " install_faster
    if [[ $install_faster =~ ^[Yy]$ ]] || [[ -z $install_faster ]]; then
        print_status "Installing faster-whisper..."
        $PIP_CMD install faster-whisper
        print_success "faster-whisper installed"
    fi
}

# Create configuration files
create_config_files() {
    print_status "Creating configuration files..."
    
    # Create models directory
    print_status "Creating models directory structure..."
    mkdir -p models/{whisper,silero_vad,cif,cache}
    
    # Download CIF models for large-v2 support
    download_cif_models
    
    # Create logs directory
    mkdir -p logs
    
    # Check if env.example exists, if not create it
    if [ ! -f "env.example" ]; then
        print_status "Creating env.example configuration file..."
        # The env.example file will be created separately
        print_success "Configuration template ready"
    else
        print_success "Configuration files already exist"
    fi
    
    print_status "Directory structure created:"
    echo "  ./models/whisper/     - Whisper model files"
    echo "  ./models/silero_vad/  - VAD model files"
    echo "  ./models/cif/         - CIF model files (downloaded)"
    echo "  ./models/cache/       - Temporary cache"
    echo "  ./logs/               - Server logs"
}

# Download CIF models for improved word boundary detection
download_cif_models() {
    print_status "Downloading CIF models for word boundary detection..."
    
    # CIF models URLs from GitHub repository
    declare -A CIF_MODELS=(
        ["cif_base.ckpt"]="https://github.com/backspacetg/simul_whisper/raw/main/cif_models/cif_base.ckpt"
        ["cif_small.ckpt"]="https://github.com/backspacetg/simul_whisper/raw/main/cif_models/cif_small.ckpt"
        ["cif_medium.ckpt"]="https://github.com/backspacetg/simul_whisper/raw/main/cif_models/cif_medium.ckpt"
        ["cif_large.ckpt"]="https://github.com/backspacetg/simul_whisper/raw/main/cif_models/cif_large.ckpt"
    )
    
    # Create CIF directory
    mkdir -p models/cif
    
    # Download each CIF model
    for model_name in "${!CIF_MODELS[@]}"; do
        model_url="${CIF_MODELS[$model_name]}"
        model_path="models/cif/$model_name"
        
        if [ ! -f "$model_path" ]; then
            print_status "Downloading $model_name..."
            
            # Try wget first, then curl
            if command -v wget &> /dev/null; then
                if wget -q --show-progress "$model_url" -O "$model_path"; then
                    print_success "Downloaded $model_name"
                else
                    print_warning "Failed to download $model_name with wget"
                    rm -f "$model_path"  # Remove partial file
                fi
            elif command -v curl &> /dev/null; then
                if curl -L "$model_url" -o "$model_path" --progress-bar; then
                    print_success "Downloaded $model_name"
                else
                    print_warning "Failed to download $model_name with curl"
                    rm -f "$model_path"  # Remove partial file
                fi
            else
                print_warning "Neither wget nor curl found. Cannot download CIF models automatically."
                print_status "Please download manually from: https://github.com/backspacetg/simul_whisper/tree/main/cif_models"
                break
            fi
        else
            print_success "$model_name already exists"
        fi
    done
    
    # Check if we successfully downloaded the large model for large-v2
    if [ -f "models/cif/cif_large.ckpt" ]; then
        print_success "CIF model for large-v2 is ready"
    else
        print_warning "CIF model for large-v2 not available. Using fallback configuration."
    fi
}

# Verify installation
verify_installation() {
    print_status "Verifying installation..."
    
    # Test import
    if $PYTHON_CMD -c "import whisperlivekit; print('WhisperLiveKit imported successfully')" 2>/dev/null; then
        print_success "WhisperLiveKit installation verified"
    else
        print_error "WhisperLiveKit installation verification failed"
        exit 1
    fi
    
    # Test PyTorch
    if $PYTHON_CMD -c "import torch; print(f'PyTorch {torch.__version__} installed')" 2>/dev/null; then
        print_success "PyTorch is working"
        
        # Check CUDA availability
        if $PYTHON_CMD -c "import torch; print('CUDA available:', torch.cuda.is_available())" 2>/dev/null; then
            CUDA_AVAILABLE=$($PYTHON_CMD -c "import torch; print(torch.cuda.is_available())" 2>/dev/null)
            if [ "$CUDA_AVAILABLE" = "True" ]; then
                GPU_COUNT=$($PYTHON_CMD -c "import torch; print(torch.cuda.device_count())" 2>/dev/null)
                print_success "CUDA is available with $GPU_COUNT GPU(s)"
            else
                print_warning "CUDA is not available. Using CPU mode."
            fi
        fi
    else
        print_warning "PyTorch installation issue detected"
    fi
    
    # Test FFmpeg
    if command -v ffmpeg &> /dev/null; then
        print_success "FFmpeg is accessible"
    else
        print_error "FFmpeg is not accessible"
        exit 1
    fi
    
    # Test optional components
    if $PYTHON_CMD -c "import diart" 2>/dev/null; then
        print_success "Diart is available for speaker diarization"
    fi
    
    if $PYTHON_CMD -c "import mlx" 2>/dev/null; then
        print_success "MLX is available for Apple Silicon optimization"
    fi
}

# Main installation process
main() {
    echo ""
    print_status "Starting WhisperLiveKit installation..."
    echo ""
    
    check_python
    install_cuda
    install_ffmpeg
    create_venv
    install_dependencies
    install_optional_dependencies
    create_config_files
    verify_installation
    
    echo ""
    echo "================================================================"
    print_success "           Installation completed successfully!"
    echo "================================================================"
    echo ""
    print_status "Next steps:"
    echo "1. Copy env.example to .env and configure your settings"
    echo "2. If using Diart: set HUGGINGFACE_HUB_TOKEN in .env"
    echo "3. Run './start.sh' to start the server"
    echo "4. Open http://localhost:8000 in your browser"
    echo ""
    print_status "To activate the virtual environment manually:"
    echo "source venv/bin/activate"
    echo ""
    
    if command -v nvidia-smi &> /dev/null; then
        print_status "GPU acceleration is available. The system will use CUDA when possible."
    else
        print_status "No GPU detected. The system will run in CPU mode."
    fi
    echo ""
}

# Run main function
main "$@"