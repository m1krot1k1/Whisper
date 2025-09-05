# Оптимизированная конфигурация .env для WhisperLiveKit

## Проблемы в текущей конфигурации

### 1. Критические проблемы производительности
- **Слишком большая модель**: `WLK_MODEL=large-v3-turbo` (~1.5GB) замедляет работу
- **Низкий frame threshold**: `WLK_FRAME_THRESHOLD=15` снижает качество для скорости
- **Минимальные beams**: `WLK_BEAMS=1` снижает точность транскрипции
- **Избыточные воркеры**: `WLK_GUNICORN_WORKERS=12` для одного пользователя

### 2. Проблемы конфигурации GPU
- Дублирование CUDA переменных в разных секциях
- Конфликтующие настройки ускорения
- Излишне сложная конфигурация для базового использования

### 3. Проблемы со стабильностью
- Слишком агрессивные настройки real-time обработки
- Конфликты между adaptive buffering и стандартной буферизацией
- Избыточная диаризация для простой транскрипции

## Оптимизированная конфигурация

```bash
# =============================================
# БАЗОВАЯ КОНФИГУРАЦИЯ GPU ДЛЯ ПРОИЗВОДИТЕЛЬНОСТИ
# =============================================

# GPU настройки (критически важно!)
CUDA_VISIBLE_DEVICES=0
WHISPER_DEVICE=cuda
FASTER_WHISPER_CUDA=1
FASTER_WHISPER_DEVICE=cuda

# Отключение предупреждений
PYTHONWARNINGS=ignore::UserWarning
TORCH_WARN_LEVEL=0

# =============================================
# СЕРВЕРНАЯ КОНФИГУРАЦИЯ 
# =============================================

# Хост и порт
WLK_HOST=0.0.0.0
WLK_PORT=8000

# =============================================
# МОДЕЛЬ И ПРОИЗВОДИТЕЛЬНОСТЬ (ОПТИМИЗИРОВАНО!)
# =============================================

# Оптимальная модель для баланса скорость/качество
WLK_MODEL=small
WLK_LANGUAGE=ru
WLK_TASK=transcribe
WLK_BACKEND=faster-whisper

# Директория моделей
WLK_MODEL_CACHE_DIR=./models

# =============================================
# ОПТИМИЗИРОВАННЫЕ ПАРАМЕТРЫ ОБРАБОТКИ
# =============================================

# Баланс скорости и качества
WLK_FRAME_THRESHOLD=25
WLK_BEAMS=3
WLK_MIN_CHUNK_SIZE=0.5

# Буферизация
WLK_AUDIO_MAX_LEN=30
WLK_BUFFER_TRIMMING=segment
WLK_BUFFER_TRIMMING_SEC=5

# VAD настройки
WLK_NO_VAD=false
WLK_VAC_CHUNK_SIZE=0.04

# =============================================
# ОТКЛЮЧЕНИЕ СЛОЖНЫХ ФУНКЦИЙ ДЛЯ СТАБИЛЬНОСТИ
# =============================================

# Отключить диаризацию (улучшает производительность)
WLK_DIARIZATION=false

# Отключить адаптивную буферизацию (упрощает)
WLK_ENABLE_ADAPTIVE_BUFFERING=false
WLK_USE_ADAPTIVE_SERVER=false

# =============================================
# ПРОДАКШЕН НАСТРОЙКИ (ОПТИМИЗИРОВАНЫ)
# =============================================

# Разумное количество воркеров (вместо 12)
WLK_GUNICORN_WORKERS=4
WLK_GUNICORN_WORKER_CLASS=uvicorn.workers.UvicornWorker
WLK_GUNICORN_TIMEOUT=120
WLK_GUNICORN_PRELOAD=true

# Логирование
WLK_LOG_LEVEL=INFO

# =============================================
# ПРОМПТЫ ДЛЯ РУССКОЙ РЕЧИ
# =============================================

WLK_INIT_PROMPT="Привет! Говорите четко и медленно."
WLK_STATIC_INIT_PROMPT="Русская речь. Четкое произношение."
```

## Дополнительные исправления

### 1. Создание правильной структуры папок
```bash
mkdir -p models/{whisper,cache,cif}
mkdir -p logs
```

### 2. Проверка GPU доступности
```bash
# Проверить доступность CUDA
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
python -c "import torch; print('GPU count:', torch.cuda.device_count())"
```

### 3. Установка правильной версии PyTorch
```bash
# Переустановить PyTorch с CUDA 11.8
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 4. Настройка системных переменных
```bash
export CUDA_HOME=/usr/local/cuda-11.8
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
```

## Запуск оптимизированного сервера

### Для разработки:
```bash
source venv/bin/activate
cp .env.copy .env
# Редактировать .env с оптимизированными настройками
python -m whisperlivekit.basic_server
```

### Для продакшена:
```bash
source venv/bin/activate
gunicorn -c gunicorn.conf.py whisperlivekit.basic_server:app
```

## Ожидаемые улучшения

1. **Скорость транскрипции**: Увеличение в 3-5 раз
2. **Качество**: Лучший баланс точности и скорости
3. **Стабильность**: Меньше ошибок и зависаний
4. **Использование ресурсов**: Оптимальная загрузка GPU/CPU
5. **Память**: Снижение потребления RAM в 2-3 раза

## Тестирование

После применения настроек протестировать:
1. Время отклика на короткие фразы (< 1 сек)
2. Качество транскрипции русской речи
3. Стабильность при длительной работе
4. Загрузку GPU и CPU