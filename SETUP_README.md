# WhisperLiveKit Setup Scripts

This directory contains setup and launch scripts for the WhisperLiveKit project. These scripts automate the installation of dependencies and provide an easy way to start the server with custom configurations.

## Files Overview

### Installation Scripts
- **`install.sh`** - Installation script for Linux/macOS
- **`install.ps1`** - Installation script for Windows PowerShell
- **`start.sh`** - Launch script for Linux/macOS  
- **`start.ps1`** - Launch script for Windows PowerShell
- **`env.example`** - Environment configuration template

## Quick Start

### Windows (PowerShell)

1. **Install dependencies:**
   ```powershell
   .\install.ps1
   ```

2. **Configure settings:**
   ```powershell
   Copy-Item env.example .env
   # Edit .env file with your preferred settings
   ```

3. **Start the server:**
   ```powershell
   .\start.ps1
   ```

### Linux/macOS (Bash)

1. **Make scripts executable:**
   ```bash
   chmod +x install.sh start.sh
   ```

2. **Install dependencies:**
   ```bash
   ./install.sh
   ```

3. **Configure settings:**
   ```bash
   cp env.example .env
   # Edit .env file with your preferred settings
   ```

4. **Start the server:**
   ```bash
   ./start.sh
   ```

## Installation Script Features

### `install.sh` / `install.ps1`

- **Automatic dependency detection and installation**
- **Python version verification** (requires Python 3.9+)
- **FFmpeg installation** (with OS-specific instructions)
- **Virtual environment creation**
- **Core package installation** (WhisperLiveKit and dependencies)
- **Optional components installation:**
  - Speaker diarization with Sortformer (NVIDIA NeMo)
  - Apple Silicon optimized backend (MLX Whisper)
  - OpenAI API backend
  - Sentence tokenization support

### Installation Options

#### Linux/macOS
```bash
./install.sh                    # Full installation with prompts
```

#### Windows
```powershell
.\install.ps1                   # Full installation with prompts
.\install.ps1 -SkipFFmpeg       # Skip FFmpeg installation check
.\install.ps1 -NoVenv           # Install without virtual environment
.\install.ps1 -Help             # Show help information
```

## Launch Script Features

### `start.sh` / `start.ps1`

- **Environment configuration loading** from `.env` file
- **Virtual environment activation**
- **Installation verification**
- **Command-line argument building** from environment variables
- **SSL/HTTPS support**
- **Development mode support**

### Launch Options

#### Linux/macOS
```bash
./start.sh                          # Start with default configuration (.env)
./start.sh -c production.env        # Use specific configuration file
./start.sh --dev                    # Start in development mode
./start.sh --no-venv                # Skip virtual environment activation
./start.sh -h                       # Show help
```

#### Windows
```powershell
.\start.ps1                         # Start with default configuration (.env)
.\start.ps1 -Config production.env  # Use specific configuration file
.\start.ps1 -Dev                    # Start in development mode
.\start.ps1 -NoVenv                 # Skip virtual environment activation
.\start.ps1 -Help                   # Show help
```

## Configuration File (`env.example`)

The `env.example` file contains all available configuration options with explanations. Key configuration categories:

### Server Configuration
- `WLK_HOST` - Server host (default: localhost)
- `WLK_PORT` - Server port (default: 8000)
- `WLK_SSL_CERTFILE` / `WLK_SSL_KEYFILE` - SSL certificates for HTTPS

### Model Configuration
- `WLK_MODEL` - Whisper model size (tiny, base, small, medium, large-v3, etc.)
- `WLK_LANGUAGE` - Source language or 'auto' for detection
- `WLK_TASK` - transcribe or translate
- `WLK_BACKEND` - Processing backend (simulstreaming, faster-whisper, etc.)

### Audio Processing
- `WLK_MIN_CHUNK_SIZE` - Minimum audio chunk size in seconds
- `WLK_NO_VAD` / `WLK_NO_VAC` - Voice Activity Detection settings
- `WLK_WARMUP_FILE` - Audio file for model warmup

### Diarization (Speaker Identification)
- `WLK_DIARIZATION` - Enable speaker identification
- `WLK_DIARIZATION_BACKEND` - sortformer or diart
- `WLK_SEGMENTATION_MODEL` / `WLK_EMBEDDING_MODEL` - Models for Diart

### SimulStreaming Settings
- `WLK_FRAME_THRESHOLD` - AlignAtt threshold (lower = faster, higher = more accurate)
- `WLK_BEAMS` - Number of beams for beam search
- `WLK_AUDIO_MAX_LEN` / `WLK_AUDIO_MIN_LEN` - Audio buffer settings

## Example Configurations

### High-Accuracy English with Speaker ID
```bash
WLK_MODEL=large-v3
WLK_LANGUAGE=en
WLK_DIARIZATION=true
WLK_DIARIZATION_BACKEND=sortformer
```

### Fast Multilingual Transcription
```bash
WLK_MODEL=medium
WLK_LANGUAGE=auto
WLK_BACKEND=faster-whisper
WLK_MIN_CHUNK_SIZE=0.3
```

### Production Server with HTTPS
```bash
WLK_HOST=0.0.0.0
WLK_PORT=443
WLK_SSL_CERTFILE=/etc/ssl/certs/whisperlivekit.pem
WLK_SSL_KEYFILE=/etc/ssl/private/whisperlivekit.key
WLK_MODEL=large-v3
WLK_LOG_LEVEL=WARNING
```

## Prerequisites

### Required
- **Python 3.9+** - Core runtime
- **FFmpeg** - Audio processing (auto-installed on Linux/macOS, manual on Windows)
- **pip** - Python package manager

### Optional
- **NVIDIA GPU + CUDA** - For GPU acceleration
- **Hugging Face Account** - For Diart diarization models
- **SSL Certificates** - For HTTPS deployment

## Troubleshooting

### Common Issues

1. **FFmpeg not found on Windows:**
   - Download from https://ffmpeg.org/download.html
   - Extract and add `bin` folder to PATH
   - Restart PowerShell

2. **Virtual environment activation fails:**
   - Ensure execution policy allows scripts: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
   - Or use `-NoVenv` flag

3. **Diarization with Diart fails:**
   - Accept user conditions for pyannote models on Hugging Face
   - Login with: `huggingface-cli login`

4. **GPU memory issues:**
   - Use smaller model size
   - Set `WLK_DISABLE_FAST_ENCODER=true`
   - Reduce `WLK_AUDIO_MAX_LEN`

### Getting Help

1. **View available options:**
   ```bash
   ./start.sh -h        # Linux/macOS
   .\start.ps1 -Help    # Windows
   ```

2. **Check installation:**
   ```bash
   python -c "import whisperlivekit; print('OK')"
   ffmpeg -version
   ```

3. **Debug mode:**
   ```bash
   ./start.sh --dev     # Linux/macOS
   .\start.ps1 -Dev     # Windows
   ```

## Development

For development work:

1. **Install in development mode** (automatic with scripts)
2. **Use development configuration:**
   ```bash
   WLK_LOG_LEVEL=DEBUG
   WLK_MODEL=base  # Smaller model for faster testing
   ```
3. **Start in development mode:**
   ```bash
   ./start.sh --dev
   ```

## Model Storage and Management

### Model Directory Structure

After installation, WhisperLiveKit creates the following directory structure:

```
./models/
├── whisper/          # Whisper model files (auto-downloaded)
│   ├── tiny.pt       # ~40MB
│   ├── base.pt       # ~150MB
│   ├── small.pt      # ~250MB
│   ├── medium.pt     # ~770MB
│   └── large-v3.pt   # ~1.5GB
├── silero_vad/       # Voice Activity Detection model (auto-downloaded)
│   └── silero_vad.onnx  # ~40MB
├── cif/              # CIF models for word boundary detection (manual)
│   ├── cif_base.ckpt
│   ├── cif_small.ckpt
│   └── cif_medium.ckpt
└── cache/            # Temporary cache files
```

### Automatic Downloads

These models are **automatically downloaded** when needed:

1. **Whisper Models** - Downloaded from OpenAI on first use
2. **Silero VAD Model** - Downloaded automatically for voice detection
3. **PyAnnote Models** - Downloaded via Hugging Face (requires token)
   - Stored in `~/.cache/huggingface/hub/`
   - `models--pyannote--segmentation-3.0/`
   - `models--speechbrain--spkrec-ecapa-voxceleb/`

### Manual Downloads Required

**CIF Models** (Optional - for better word boundary detection):
- Download from: https://github.com/backspacetg/simul_whisper/tree/main/cif_models
- Place in `./models/cif/` directory
- Available for: base, small, medium (no large-v3 model)

### Model Configuration

In your `.env` file:

```bash
# Specify models directory
WLK_MODEL_CACHE_DIR=./models

# Use specific model directory (if you have pre-downloaded models)
# WLK_MODEL_DIR=./models/whisper

# CIF model for word boundary detection
# WLK_CIF_CKPT_PATH=./models/cif/cif_small.ckpt
```

### Model Selection Guide

| Model | Size | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| tiny | ~40MB | Very Fast | Low | Testing, demos |
| base | ~150MB | Fast | Good | General use |
| small | ~250MB | Moderate | High | **Recommended** |
| medium | ~770MB | Slow | Very High | High quality needs |
| large-v3 | ~1.5GB | Very Slow | Highest | Professional use |

### Storage Requirements

- **Minimum**: ~500MB (small model + dependencies)
- **Recommended**: ~2GB (multiple models + cache)
- **Full Setup**: ~5GB (all models + logs + cache)

### Model Management Commands

```bash
# Check model storage usage
du -sh models/

# Clear model cache
rm -rf models/cache/*

# Pre-download specific model
python -c "import whisperlivekit; whisperlivekit.load_model('medium')"

# Check available models
ls -la models/whisper/
```

## Gunicorn Production Deployment

WhisperLiveKit поддерживает production развертывание с Gunicorn для высокой производительности и стабильности.

### Что такое Gunicorn?

Gunicorn (Green Unicorn) - это Python WSGI HTTP сервер для UNIX. Он:
- **Запускает несколько worker процессов** для обработки запросов параллельно
- **Автоматически перезапускает** упавшие workers
- **Балансирует нагрузку** между процессами
- **Обеспечивает graceful restart** без потери соединений
- **Мониторит состояние** процессов

### Production vs Development

| Режим | Процессы | Производительность | Отладка | Рестарт |
|-------|----------|-------------------|---------|----------|
| Development | 1 | Низкая | Легкая | Быстрый |
| Production | 4+ | Высокая | Сложная | Graceful |

### Конфигурация Production

В `env.example` настройте параметры Gunicorn:

```bash
# Количество worker процессов (формула: 2 * CPU_CORES + 1)
WLK_GUNICORN_WORKERS=4

# Класс worker'а (обязательно для WebSocket)
WLK_GUNICORN_WORKER_CLASS=uvicorn.workers.UvicornWorker

# Тайм-аут для worker'ов
WLK_GUNICORN_TIMEOUT=180

# Максимальное количество соединений на worker
WLK_GUNICORN_MAX_REQUESTS=1000

# Включить preload mode
WLK_GUNICORN_PRELOAD=true
```

### Запуск Production Сервера

```bash
# Запуск с Gunicorn
./start.sh --production

# Или напрямую
gunicorn -c gunicorn.conf.py whisperlivekit.basic_server:app
```

### Управление Production Сервером

Используйте скрипт `manage.sh` (Linux/macOS) или `manage.ps1` (Windows):

```bash
# Запуск сервера
./manage.sh start

# Проверка статуса
./manage.sh status

# Graceful restart (без потери соединений)
./manage.sh reload

# Полный перезапуск
./manage.sh restart

# Просмотр логов в реальном времени
./manage.sh logs

# Остановка сервера
./manage.sh stop

# Очистка логов
./manage.sh clean
```

### Мониторинг и Логи

```bash
# Просмотр логов
tail -f logs/gunicorn_access.log
tail -f logs/gunicorn_error.log

# Проверка процессов
ps aux | grep gunicorn

# Мониторинг ресурсов
top -p $(cat gunicorn.pid)
```

### Nginx Configuration

Для production рекомендуется использовать Nginx как reverse proxy:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL configuration
    ssl_certificate /path/to/certificate.pem;
    ssl_certificate_key /path/to/private_key.pem;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # Proxy to WhisperLiveKit
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Static files (optional)
    location /static/ {
        alias /path/to/static/files/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### Systemd Service (Linux)

Создайте systemd service для автозапуска:

```ini
# /etc/systemd/system/whisperlivekit.service
[Unit]
Description=WhisperLiveKit Production Server
After=network.target

[Service]
Type=forking
User=whisper
Group=whisper
WorkingDirectory=/opt/whisperlivekit
Environment=PATH=/opt/whisperlivekit/venv/bin
ExecStart=/opt/whisperlivekit/venv/bin/gunicorn -c gunicorn.conf.py whisperlivekit.basic_server:app
ExecReload=/bin/kill -HUP $MAINPID
PIDFile=/opt/whisperlivekit/gunicorn.pid
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
# Активация service
sudo systemctl enable whisperlivekit
sudo systemctl start whisperlivekit
sudo systemctl status whisperlivekit
```