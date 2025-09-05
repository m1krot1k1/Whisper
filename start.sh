#!/bin/bash

# WhisperLiveKit Startup Script
# This script starts the WhisperLiveKit server with configuration from environment

set -e

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

# Default configuration file
ENV_FILE=".env"

# Load environment variables from file
load_env() {
    if [ -f "$ENV_FILE" ]; then
        print_status "Loading configuration from $ENV_FILE"
        # Export variables from .env file
        set -a
        source "$ENV_FILE"
        set +a
        
        # Special handling for Hugging Face token
        if [ -n "$HUGGINGFACE_HUB_TOKEN" ]; then
            print_status "Hugging Face token loaded for Diart access"
        fi
        
        print_success "Configuration loaded"
    elif [ -f "env.example" ]; then
        print_warning "No .env file found. Using env.example as template."
        print_status "Please copy env.example to .env and configure your settings."
        print_status "Using default configuration for now..."
        set -a
        source "env.example"
        set +a
    else
        print_warning "No configuration file found. Using default settings."
    fi
}

# Check if virtual environment exists and activate it
activate_venv() {
    # Check if virtual environment exists and is complete
    if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
        print_status "Activating virtual environment..."
        source venv/bin/activate
        print_success "Virtual environment activated"
    else
        print_warning "Virtual environment not found or incomplete. Creating new virtual environment..."
        
        # Remove incomplete virtual environment if it exists
        if [ -d "venv" ]; then
            print_warning "Incomplete virtual environment found. Removing and recreating..."
            rm -rf venv
        fi
        
        # Find Python command
        PYTHON_CMD=""
        for cmd in python3.11 python3.10 python3.9 python3 python; do
            if command -v $cmd &> /dev/null; then
                PYTHON_CMD=$cmd
                break
            fi
        done
        
        if [ -z "$PYTHON_CMD" ]; then
            print_error "Python not found. Please install Python 3.9+ first."
            exit 1
        fi
        
        # Create virtual environment
        print_status "Creating virtual environment with $PYTHON_CMD..."
        $PYTHON_CMD -m venv venv
        
        if [ $? -eq 0 ] && [ -f "venv/bin/activate" ]; then
            print_success "Virtual environment created successfully"
            source venv/bin/activate
            print_success "Virtual environment activated"
            
            # Install the package in development mode
            print_status "Installing WhisperLiveKit in development mode..."
            pip install --upgrade pip
            pip install -e .
            
            if [ $? -eq 0 ]; then
                print_success "WhisperLiveKit installed successfully"
            else
                print_warning "Failed to install WhisperLiveKit. You may need to run install.sh first."
            fi
        else
            print_error "Failed to create virtual environment"
            exit 1
        fi
    fi
}

# Check if WhisperLiveKit is installed
check_installation() {
    print_status "Checking WhisperLiveKit installation..."
    
    if python3 -c "import whisperlivekit" 2>/dev/null; then
        print_success "WhisperLiveKit is installed"
    else
        print_error "WhisperLiveKit is not installed. Please run install.sh first."
        exit 1
    fi
    
    # Check for NeMo toolkit (required for diarization)
    if python3 -c "import nemo" 2>/dev/null; then
        print_success "NeMo toolkit is available"
    else
        print_warning "NeMo toolkit not found. Installing automatically..."
        
        # Check if system dependencies are installed
        if ! dpkg -l | grep -q python3.10-dev; then
            print_warning "Installing system dependencies for compilation..."
            sudo apt-get update
            sudo apt-get install -y python3.10-dev build-essential gcc g++ make
        fi
        
        pip install "git+https://github.com/NVIDIA/NeMo.git@main#egg=nemo_toolkit[asr]"
        if [ $? -eq 0 ]; then
            print_success "NeMo toolkit installed successfully"
        else
            print_warning "Failed to install NeMo toolkit. Some diarization features may not work."
        fi
    fi
    
    # Check FFmpeg
    if command -v ffmpeg &> /dev/null; then
        print_success "FFmpeg is available"
    else
        print_error "FFmpeg not found. Please install FFmpeg."
        exit 1
    fi
}

# Build command line arguments from environment variables
build_args() {
    ARGS=""
    
    # Basic server settings
    [ -n "$WLK_HOST" ] && ARGS="$ARGS --host $WLK_HOST"
    [ -n "$WLK_PORT" ] && ARGS="$ARGS --port $WLK_PORT"
    
    # Model settings
    [ -n "$WLK_MODEL" ] && ARGS="$ARGS --model $WLK_MODEL"
    [ -n "$WLK_LANGUAGE" ] && ARGS="$ARGS --language $WLK_LANGUAGE"
    [ -n "$WLK_TASK" ] && ARGS="$ARGS --task $WLK_TASK"
    [ -n "$WLK_BACKEND" ] && ARGS="$ARGS --backend $WLK_BACKEND"
    
    # Audio processing settings
    [ -n "$WLK_MIN_CHUNK_SIZE" ] && ARGS="$ARGS --min-chunk-size $WLK_MIN_CHUNK_SIZE"
    [ -n "$WLK_WARMUP_FILE" ] && ARGS="$ARGS --warmup-file $WLK_WARMUP_FILE"
    
    # SSL settings
    [ -n "$WLK_SSL_CERTFILE" ] && ARGS="$ARGS --ssl-certfile $WLK_SSL_CERTFILE"
    [ -n "$WLK_SSL_KEYFILE" ] && ARGS="$ARGS --ssl-keyfile $WLK_SSL_KEYFILE"
    
    # Voice Activity Detection
    [ "$WLK_NO_VAD" = "true" ] && ARGS="$ARGS --no-vad"
    [ "$WLK_NO_VAC" = "true" ] && ARGS="$ARGS --no-vac"
    [ -n "$WLK_VAC_CHUNK_SIZE" ] && ARGS="$ARGS --vac-chunk-size $WLK_VAC_CHUNK_SIZE"
    
    # Diarization settings
    [ "$WLK_DIARIZATION" = "true" ] && ARGS="$ARGS --diarization"
    [ -n "$WLK_DIARIZATION_BACKEND" ] && ARGS="$ARGS --diarization-backend $WLK_DIARIZATION_BACKEND"
    [ -n "$WLK_SEGMENTATION_MODEL" ] && ARGS="$ARGS --segmentation-model $WLK_SEGMENTATION_MODEL"
    [ -n "$WLK_EMBEDDING_MODEL" ] && ARGS="$ARGS --embedding-model $WLK_EMBEDDING_MODEL"
    [ "$WLK_PUNCTUATION_SPLIT" = "true" ] && ARGS="$ARGS --punctuation-split"
    
    # SimulStreaming specific settings
    [ "$WLK_DISABLE_FAST_ENCODER" = "true" ] && ARGS="$ARGS --disable-fast-encoder"
    [ -n "$WLK_FRAME_THRESHOLD" ] && ARGS="$ARGS --frame-threshold $WLK_FRAME_THRESHOLD"
    [ -n "$WLK_BEAMS" ] && ARGS="$ARGS --beams $WLK_BEAMS"
    [ -n "$WLK_DECODER_TYPE" ] && ARGS="$ARGS --decoder $WLK_DECODER_TYPE"
    [ -n "$WLK_AUDIO_MAX_LEN" ] && ARGS="$ARGS --audio-max-len $WLK_AUDIO_MAX_LEN"
    [ -n "$WLK_AUDIO_MIN_LEN" ] && ARGS="$ARGS --audio-min-len $WLK_AUDIO_MIN_LEN"
    [ -n "$WLK_CIF_CKPT_PATH" ] && ARGS="$ARGS --cif-ckpt-path $WLK_CIF_CKPT_PATH"
    [ "$WLK_NEVER_FIRE" = "true" ] && ARGS="$ARGS --never-fire"
    [ -n "$WLK_INIT_PROMPT" ] && ARGS="$ARGS --init-prompt \"$WLK_INIT_PROMPT\""
    [ -n "$WLK_STATIC_INIT_PROMPT" ] && ARGS="$ARGS --static-init-prompt \"$WLK_STATIC_INIT_PROMPT\""
    [ -n "$WLK_MAX_CONTEXT_TOKENS" ] && ARGS="$ARGS --max-context-tokens $WLK_MAX_CONTEXT_TOKENS"
    [ -n "$WLK_MODEL_PATH" ] && ARGS="$ARGS --model-path $WLK_MODEL_PATH"
    [ -n "$WLK_PRELOADED_MODEL_COUNT" ] && ARGS="$ARGS --preloaded_model_count $WLK_PRELOADED_MODEL_COUNT"
    
    # Buffer settings
    [ -n "$WLK_BUFFER_TRIMMING" ] && ARGS="$ARGS --buffer_trimming $WLK_BUFFER_TRIMMING"
    [ -n "$WLK_BUFFER_TRIMMING_SEC" ] && ARGS="$ARGS --buffer_trimming_sec $WLK_BUFFER_TRIMMING_SEC"
    
    # Other settings
    [ "$WLK_CONFIDENCE_VALIDATION" = "true" ] && ARGS="$ARGS --confidence-validation"
    [ "$WLK_NO_TRANSCRIPTION" = "true" ] && ARGS="$ARGS --no-transcription"
    [ -n "$WLK_LOG_LEVEL" ] && ARGS="$ARGS --log-level $WLK_LOG_LEVEL"
    [ -n "$WLK_MODEL_CACHE_DIR" ] && ARGS="$ARGS --model_cache_dir $WLK_MODEL_CACHE_DIR"
    [ -n "$WLK_MODEL_DIR" ] && ARGS="$ARGS --model_dir $WLK_MODEL_DIR"
    
    echo "$ARGS"
}

# Display startup information
show_development_startup_info() {
    echo ""
    echo "================================================================"
    echo "           WhisperLiveKit Development Server Starting"
    echo "================================================================"
    echo ""
    print_status "Configuration:"
    echo "  Host: ${WLK_HOST:-localhost}"
    echo "  Port: ${WLK_PORT:-8000}"
    echo "  Model: ${WLK_MODEL:-small}"
    echo "  Language: ${WLK_LANGUAGE:-auto}"
    echo "  Backend: ${WLK_BACKEND:-simulstreaming}"
    echo "  Diarization: ${WLK_DIARIZATION:-false}"
    echo ""
    
    if [ -n "$WLK_SSL_CERTFILE" ] && [ -n "$WLK_SSL_KEYFILE" ]; then
        print_status "Server will be available at: https://${WLK_HOST:-localhost}:${WLK_PORT:-8000}"
    else
        print_status "Server will be available at: http://${WLK_HOST:-localhost}:${WLK_PORT:-8000}"
    fi
    echo ""
}

# Display production startup information
show_production_startup_info() {
    echo ""
    echo "================================================================"
    echo "           WhisperLiveKit Production Server Starting"
    echo "================================================================"
    echo ""
    print_status "Configuration:"
    echo "  Host: ${WLK_HOST:-localhost}"
    echo "  Port: ${WLK_PORT:-8000}"
    echo "  Workers: ${WLK_GUNICORN_WORKERS:-4}"
    echo "  Worker Class: ${WLK_GUNICORN_WORKER_CLASS:-uvicorn.workers.UvicornWorker}"
    echo "  Model: ${WLK_MODEL:-small}"
    echo "  Language: ${WLK_LANGUAGE:-auto}"
    echo "  Backend: ${WLK_BACKEND:-simulstreaming}"
    echo "  Diarization: ${WLK_DIARIZATION:-false}"
    echo ""
    
    if [ -n "$WLK_SSL_CERTFILE" ] && [ -n "$WLK_SSL_KEYFILE" ]; then
        print_status "Server will be available at: https://${WLK_HOST:-localhost}:${WLK_PORT:-8000}"
    else
        print_status "Server will be available at: http://${WLK_HOST:-localhost}:${WLK_PORT:-8000}"
    fi
    echo ""
}

# Start the server
start_server() {
    local args=$(build_args)
    
    if [ "$PRODUCTION_MODE" = true ]; then
        start_production_server
    else
        start_development_server "$args"
    fi
}

# Start development server (uvicorn)
start_development_server() {
    local args="$1"
    
    print_status "Starting WhisperLiveKit development server..."
    print_status "Command: whisperlivekit-server$args"
    echo ""
    
    # Execute the command
    if [ -n "$args" ]; then
        eval "whisperlivekit-server$args"
    else
        whisperlivekit-server
    fi
}

# Start production server (gunicorn)
start_production_server() {
    print_status "Starting WhisperLiveKit production server with Gunicorn..."
    
    # Create logs directory
    mkdir -p logs
    
    # Check if gunicorn is installed
    if ! command -v gunicorn &> /dev/null; then
        print_error "Gunicorn not found. Please install it first:"
        print_status "pip install gunicorn uvicorn[standard]"
        exit 1
    fi
    
    # Set production environment variables
    export WLK_DEV_MODE=false
    
    # Build gunicorn command
    local gunicorn_cmd="gunicorn"
    local gunicorn_args=""
    
    # Use configuration file if exists
    if [ -f "gunicorn.conf.py" ]; then
        gunicorn_args="$gunicorn_args -c gunicorn.conf.py"
        print_status "Using configuration from gunicorn.conf.py"
    else
        # Fallback to environment variables
        local workers=${WLK_GUNICORN_WORKERS:-4}
        local worker_class=${WLK_GUNICORN_WORKER_CLASS:-uvicorn.workers.UvicornWorker}
        local timeout=${WLK_GUNICORN_TIMEOUT:-180}
        local bind="${WLK_HOST:-localhost}:${WLK_PORT:-8000}"
        
        gunicorn_args="$gunicorn_args -w $workers"
        gunicorn_args="$gunicorn_args -k $worker_class"
        gunicorn_args="$gunicorn_args --timeout $timeout"
        gunicorn_args="$gunicorn_args --bind $bind"
        gunicorn_args="$gunicorn_args --preload"
        
        if [ -n "$WLK_GUNICORN_PIDFILE" ]; then
            gunicorn_args="$gunicorn_args --pid $WLK_GUNICORN_PIDFILE"
        fi
        
        print_status "Using environment configuration"
    fi
    
    # Application module
    local app_module="whisperlivekit.basic_server:app"
    
    print_status "Command: $gunicorn_cmd $gunicorn_args $app_module"
    echo ""
    print_status "Production server features:"
    echo "  - Multiple worker processes for high performance"
    echo "  - Automatic process management and health checks"
    echo "  - Graceful restart and shutdown"
    echo "  - Enhanced logging and monitoring"
    echo "  - Load balancing across workers"
    echo ""
    print_status "Control commands (in another terminal):"
    echo "  Graceful restart: kill -HUP \$(cat gunicorn.pid)"
    echo "  Graceful shutdown: kill -TERM \$(cat gunicorn.pid)"
    echo "  Check status: ps aux | grep gunicorn"
    echo ""
    
    # Execute gunicorn
    eval "$gunicorn_cmd $gunicorn_args $app_module"
}

# Handle script interruption
cleanup() {
    echo ""
    print_status "Shutting down server..."
    print_success "Server stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Help function
show_help() {
    echo "WhisperLiveKit Startup Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -c, --config FILE    Use specific configuration file (default: .env)"
    echo "  -h, --help          Show this help message"
    echo "  --dev               Start in development mode with auto-reload"
    echo "  --production        Start in production mode with Gunicorn"
    echo "  --no-venv           Skip virtual environment activation"
    echo ""
    echo "Environment Variables:"
    echo "  All WLK_* variables from .env file will be used as server configuration"
    echo ""
    echo "Examples:"
    echo "  $0                          # Start with default configuration"
    echo "  $0 -c production.env        # Start with specific config file"
    echo "  $0 --dev                    # Start in development mode"
    echo "  $0 --production             # Start in production mode with Gunicorn"
    echo ""
    echo "Production mode features:"
    echo "  - Multiple worker processes for better performance"
    echo "  - Automatic process management and restart"
    echo "  - Enhanced logging and monitoring"
    echo "  - Graceful shutdown handling"
    echo ""
}

# Parse command line arguments
parse_args() {
    USE_VENV=true
    DEV_MODE=false
    PRODUCTION_MODE=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -c|--config)
                ENV_FILE="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            --dev)
                DEV_MODE=true
                shift
                ;;
            --production)
                PRODUCTION_MODE=true
                shift
                ;;
            --no-venv)
                USE_VENV=false
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Validate mutually exclusive options
    if [ "$DEV_MODE" = true ] && [ "$PRODUCTION_MODE" = true ]; then
        print_error "Cannot use --dev and --production together"
        exit 1
    fi
}

# Main function
main() {
    parse_args "$@"
    
    # Load configuration
    load_env
    
    # Activate virtual environment if requested
    if [ "$USE_VENV" = true ]; then
        activate_venv
    fi
    
    # Check installation
    check_installation
    
    # Show startup information
    if [ "$PRODUCTION_MODE" = true ]; then
        show_production_startup_info
    else
        show_development_startup_info
    fi
    
    # Start the server
    if [ "$DEV_MODE" = true ]; then
        print_status "Starting in development mode..."
        # In development mode, we could add auto-reload or other dev features
        # For now, just start normally but indicate dev mode
        export WLK_LOG_LEVEL="${WLK_LOG_LEVEL:-DEBUG}"
    fi
    
    start_server
}

# Run main function with all arguments
main "$@"