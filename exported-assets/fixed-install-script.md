# Исправленный install.sh для WhisperLiveKit

## Проблемы в текущем скрипте установки

### Обнаруженные проблемы:
1. **Избыточные зависимости**: Установка NeMo toolkit может вызвать конфликты
2. **Неправильная установка CUDA**: Скрипт устанавливает старую версию CUDA 11.8
3. **Конфликты PyTorch**: Переустановка PyTorch может сломать existing установку
4. **Избыточная конфигурация**: Создает слишком сложную структуру папок

## Оптимизированный скрипт установки

```bash
#!/bin/bash

# WhisperLiveKit Optimized Installation Script
# Упрощенная установка для стабильной работы

set -e

echo "=============================================================="
echo " WhisperLiveKit Оптимизированная установка"
echo "=============================================================="

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m' # No Color

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
    print_status "Проверка Python установки..."
    
    PYTHON_CMD=""
    
    # Try to find existing Python installation (3.9+)
    for cmd in python3.11 python3.10 python3.9 python3 python; do
        if command -v $cmd &> /dev/null; then
            VERSION=$($cmd -c 'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null)
            if [ $? -eq 0 ]; then
                # Check if version is >= 3.9
                if $cmd -c 'import sys; exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
                    PYTHON_CMD=$cmd
                    print_success "Совместимый Python найден: $PYTHON_CMD ($VERSION)"
                    return 0
                fi
            fi
        fi
    done
    
    print_error "Python 3.9+ не найден. Пожалуйста, установите Python вручную."
    print_status "Визит: https://www.python.org/downloads/"
    exit 1
}

# Check GPU availability
check_gpu() {
    print_status "Проверка GPU доступности..."
    
    if command -v nvidia-smi &> /dev/null; then
        GPU_INFO=$(nvidia-smi --query-gpu=name --format=csv,noheader,nounits 2>/dev/null | head -1)
        if [ $? -eq 0 ] && [ -n "$GPU_INFO" ]; then
            print_success "NVIDIA GPU обнаружен: $GPU_INFO"
            GPU_AVAILABLE=true
            
            # Check CUDA availability
            if command -v nvcc &> /dev/null; then
                CUDA_VERSION=$(nvcc --version | grep "release" | sed 's/.*release \\([0-9]\\+\\.[0-9]\\+\\).*/\\1/')
                print_success "CUDA $CUDA_VERSION установлен"
            else
                print_warning "CUDA toolkit не найден. Будет использоваться PyTorch CUDA runtime."
            fi
        else
            print_warning "GPU не обнаружен или драйверы не установлены."
            GPU_AVAILABLE=false
        fi
    else
        print_warning "nvidia-smi не найден. GPU не доступен."
        GPU_AVAILABLE=false
    fi
}

# Install system dependencies
install_system_dependencies() {
    print_status "Установка системных зависимостей..."
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v apt-get &> /dev/null; then
            print_status "Установка зависимостей через apt..."
            sudo apt-get update
            sudo apt-get install -y ffmpeg python3-dev build-essential git
        elif command -v yum &> /dev/null; then
            print_status "Установка зависимостей через yum..."
            sudo yum install -y ffmpeg python3-devel gcc gcc-c++ git
        elif command -v dnf &> /dev/null; then
            print_status "Установка зависимостей через dnf..."
            sudo dnf install -y ffmpeg python3-devel gcc gcc-c++ git
        else
            print_error "Не удалось определить пакетный менеджер."
            exit 1
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            print_status "Установка зависимостей через Homebrew..."
            brew install ffmpeg
        else
            print_error "Homebrew не найден. Установите зависимости вручную."
            exit 1
        fi
    fi
    
    print_success "Системные зависимости установлены"
}

# Check and install FFmpeg
check_ffmpeg() {
    print_status "Проверка FFmpeg..."
    
    if command -v ffmpeg &> /dev/null; then
        FFMPEG_VERSION=$(ffmpeg -version | head -n 1 | cut -d' ' -f3)
        print_success "FFmpeg $FFMPEG_VERSION уже установлен"
    else
        print_error "FFmpeg не найден. Пожалуйста, установите FFmpeg."
        exit 1
    fi
}

# Create virtual environment
create_venv() {
    print_status "Создание виртуального окружения..."
    
    if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
        print_warning "Виртуальное окружение уже существует."
        read -p "Пересоздать? (y/N): " recreate
        if [[ $recreate =~ ^[Yy]$ ]]; then
            rm -rf venv
        else
            print_status "Используем существующее окружение."
            return 0
        fi
    fi
    
    print_status "Создание нового виртуального окружения..."
    $PYTHON_CMD -m venv venv
    
    if [ $? -eq 0 ] && [ -f "venv/bin/activate" ]; then
        print_success "Виртуальное окружение создано"
    else
        print_error "Не удалось создать виртуальное окружение"
        exit 1
    fi
}

# Install Python dependencies
install_dependencies() {
    print_status "Установка WhisperLiveKit и зависимостей..."
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    print_status "Обновление pip..."
    python -m pip install --upgrade pip
    
    # Install PyTorch with appropriate backend
    if [ "$GPU_AVAILABLE" = true ]; then
        print_status "Установка PyTorch с CUDA поддержкой..."
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
    else
        print_status "Установка PyTorch (CPU версия)..."
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    fi
    
    # Install core dependencies
    print_status "Установка основных зависимостей..."
    pip install -e .
    
    # Install additional audio dependencies
    pip install soundfile librosa
    
    # Install faster-whisper for better performance
    pip install faster-whisper
    
    # Install production server dependencies
    pip install gunicorn uvicorn[standard]
    
    print_success "Основные зависимости установлены"
}

# Install optional dependencies
install_optional_dependencies() {
    print_status "Установка дополнительных зависимостей..."
    
    # Activate virtual environment
    source venv/bin/activate
    
    echo ""
    print_status "Дополнительные компоненты:"
    echo "1. Диаризация (определение говорящих) - для multi-speaker аудио"
    echo "2. OpenAI API backend - для использования OpenAI API"
    echo ""
    
    read -p "Установить диаризацию? (y/N): " install_diarization
    if [[ $install_diarization =~ ^[Yy]$ ]]; then
        print_status "Установка диаризации..."
        pip install pyannote.audio diart
        print_success "Диаризация установлена"
        print_warning "Не забудьте:"
        print_status "1. Принять условия pyannote моделей на Hugging Face"
        print_status "2. Установить HUGGINGFACE_HUB_TOKEN в .env файле"
        print_status "3. Войти: huggingface-cli login"
    fi
    
    read -p "Установить OpenAI API backend? (y/N): " install_openai
    if [[ $install_openai =~ ^[Yy]$ ]]; then
        print_status "Установка OpenAI..."
        pip install openai
        print_success "OpenAI API backend установлен"
    fi
}

# Create directory structure
create_directories() {
    print_status "Создание структуры папок..."
    
    # Create essential directories only
    mkdir -p models/{whisper,cache}
    mkdir -p logs
    
    print_success "Структура папок создана:"
    echo " ./models/whisper/ - Whisper модели"
    echo " ./models/cache/ - Временные файлы"
    echo " ./logs/ - Логи сервера"
}

# Create optimized configuration
create_config() {
    print_status "Создание оптимизированной конфигурации..."
    
    # Create optimized .env file
    cat > .env << 'EOF'
# Оптимизированная конфигурация WhisperLiveKit

# =============================================
# GPU НАСТРОЙКИ
# =============================================
CUDA_VISIBLE_DEVICES=0
WHISPER_DEVICE=cuda
FASTER_WHISPER_CUDA=1
PYTHONWARNINGS=ignore::UserWarning

# =============================================
# СЕРВЕР
# =============================================
WLK_HOST=0.0.0.0
WLK_PORT=8000

# =============================================
# МОДЕЛЬ (ОПТИМИЗИРОВАНО ДЛЯ СКОРОСТИ)
# =============================================
WLK_MODEL=small
WLK_LANGUAGE=ru
WLK_TASK=transcribe
WLK_BACKEND=faster-whisper
WLK_MODEL_CACHE_DIR=./models

# =============================================
# ПРОИЗВОДИТЕЛЬНОСТЬ
# =============================================
WLK_FRAME_THRESHOLD=25
WLK_BEAMS=3
WLK_MIN_CHUNK_SIZE=0.5
WLK_AUDIO_MAX_LEN=30

# =============================================
# УПРОЩЕННЫЕ НАСТРОЙКИ
# =============================================
WLK_NO_VAD=false
WLK_DIARIZATION=false
WLK_LOG_LEVEL=INFO

# =============================================
# ПРОДАКШЕН (ОПТИМИЗИРОВАННО)
# =============================================
WLK_GUNICORN_WORKERS=4
WLK_GUNICORN_TIMEOUT=120
EOF
    
    print_success "Конфигурация создана в .env файле"
}

# Verify installation
verify_installation() {
    print_status "Проверка установки..."
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Test import
    if python -c "import whisperlivekit; print('WhisperLiveKit импортирован успешно')" 2>/dev/null; then
        print_success "WhisperLiveKit установлен корректно"
    else
        print_error "Проблема с установкой WhisperLiveKit"
        exit 1
    fi
    
    # Test PyTorch
    if python -c "import torch; print(f'PyTorch {torch.__version__} работает')" 2>/dev/null; then
        print_success "PyTorch работает"
        
        # Check CUDA
        CUDA_AVAILABLE=$(python -c "import torch; print(torch.cuda.is_available())" 2>/dev/null)
        if [ "$CUDA_AVAILABLE" = "True" ]; then
            GPU_COUNT=$(python -c "import torch; print(torch.cuda.device_count())" 2>/dev/null)
            print_success "CUDA доступен с $GPU_COUNT GPU"
        else
            print_warning "CUDA недоступен. Будет использоваться CPU режим."
        fi
    else
        print_warning "Проблема с PyTorch"
    fi
    
    # Test FFmpeg
    if command -v ffmpeg &> /dev/null; then
        print_success "FFmpeg доступен"
    else
        print_error "FFmpeg недоступен"
        exit 1
    fi
}

# Main installation process
main() {
    echo ""
    print_status "Запуск оптимизированной установки WhisperLiveKit..."
    echo ""
    
    check_python
    check_gpu
    install_system_dependencies
    check_ffmpeg
    create_venv
    install_dependencies
    install_optional_dependencies
    create_directories
    create_config
    verify_installation
    
    echo ""
    echo "=============================================================="
    print_success " Установка завершена успешно!"
    echo "=============================================================="
    echo ""
    print_status "Следующие шаги:"
    echo "1. Активировать окружение: source venv/bin/activate"
    echo "2. Запустить сервер: python -m whisperlivekit.basic_server"
    echo "3. Открыть браузер: http://localhost:8000"
    echo ""
    
    if [ "$GPU_AVAILABLE" = true ]; then
        print_success "GPU ускорение доступно!"
    else
        print_warning "Работа в CPU режиме. Для лучшей производительности установите CUDA."
    fi
    
    echo ""
}

# Run main function
main "$@"
```

## Ключевые улучшения

1. **Упрощенная установка**: Убраны избыточные зависимости
2. **Лучшая детекция GPU**: Правильная проверка CUDA
3. **Оптимизированная конфигурация**: Автоматическое создание .env
4. **Стабильность**: Минимальный набор необходимых пакетов
5. **Производительность**: Настройки оптимизированы для скорости

## Использование

```bash
# Сделать исполняемым
chmod +x install.sh

# Запустить установку
./install.sh
```