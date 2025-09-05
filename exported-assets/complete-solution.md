# Комплексное решение всех проблем репозитория WhisperLiveKit

## Обзор проблем

На основе анализа репозитория https://github.com/m1krot1k1/Whisper/tree/dev обнаружены следующие критические проблемы:

### 🔴 Основные проблемы производительности
1. **Медленная транскрипция** - "плохая и медленная транскрибация"
2. **Неоптимальная конфигурация GPU** - CUDA настройки разбросаны по файлу
3. **Избыточные настройки** - слишком много параметров в .env
4. **Конфликты зависимостей** - проблемы с установкой через install.sh

## 🔧 Список всех исправлений

### 1. Критические исправления .env конфигурации

**Проблема**: Текущая конфигурация использует:
- `WLK_MODEL=large-v3-turbo` (1.5GB) - слишком большая модель
- `WLK_FRAME_THRESHOLD=15` - слишком агрессивно для качества
- `WLK_GUNICORN_WORKERS=12` - избыточно для одного пользователя
- Дублирование CUDA параметров

**Решение**: Оптимизированная конфигурация
```bash
# Базовые GPU настройки (упрощено)
CUDA_VISIBLE_DEVICES=0
WHISPER_DEVICE=cuda
FASTER_WHISPER_CUDA=1

# Оптимальная модель для скорости
WLK_MODEL=small
WLK_BACKEND=faster-whisper
WLK_LANGUAGE=ru

# Сбалансированные параметры
WLK_FRAME_THRESHOLD=25
WLK_BEAMS=3
WLK_MIN_CHUNK_SIZE=0.5

# Отключение сложных функций
WLK_DIARIZATION=false
WLK_ENABLE_ADAPTIVE_BUFFERING=false

# Разумное количество воркеров
WLK_GUNICORN_WORKERS=4
```

### 2. Исправления структуры моделей

**Проблема**: Неясно, скачиваются ли модели в правильную папку

**Решение**: Обеспечить создание структуры папок
```bash
mkdir -p models/{whisper,cache,silero_vad}
mkdir -p logs
```

**Автоматическая загрузка моделей**:
- Whisper модели: `./models/whisper/`
- Silero VAD: `./models/silero_vad/`
- Cache: `./models/cache/`

### 3. Исправления установки (install.sh)

**Проблемы**:
- Установка избыточных зависимостей (NeMo toolkit)
- Неправильная версия CUDA (11.8 вместо 12.1)
- Конфликты PyTorch

**Решение**: Упрощенный install.sh
```bash
# Основные зависимости только
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -e .
pip install faster-whisper soundfile librosa
pip install gunicorn uvicorn[standard]
```

### 4. Исправления Gunicorn конфигурации

**Проблемы**:
- 12 воркеров избыточно
- Таймаут 300 секунд слишком высокий
- Отсутствуют проверки GPU

**Решение**: Оптимизированный gunicorn.conf.py
```python
workers = 4  # Вместо 12
timeout = 120  # Вместо 300
max_requests = 500  # Ограничение для стабильности
preload_app = True  # Экономия памяти

# Хуки для GPU проверки
def on_starting(server):
    import torch
    if torch.cuda.is_available():
        server.log.info(f"GPU available: {torch.cuda.get_device_name(0)}")
```

### 5. Исправления серверных файлов

**Проблема**: adaptive_basic_server.py добавляет сложность без необходимости

**Решение**: Использовать basic_server.py с оптимизацией
- Убрать adaptive buffering для стабильности
- Упростить WebSocket обработку
- Добавить лучшую обработку ошибок

### 6. Исправления dependencies (pyproject.toml)

**Проблемы**:
- Поддержка Python до 3.15 (не существует)
- Triton только для Linux x86_64
- Избыточные зависимости

**Решение**: 
```toml
requires-python = ">=3.9,<3.13"
dependencies = [
    "fastapi",
    "librosa", 
    "soundfile",
    "faster-whisper",
    "uvicorn",
    "websockets",
    "torch>=2.0.0",
    "torchaudio>=2.0.0"
]
```

## 🚀 Пошаговый план исправления

### Шаг 1: Создать оптимизированную .env конфигурацию
```bash
cp ".env copy" .env.backup
# Заменить на упрощенную конфигурацию
```

### Шаг 2: Исправить install.sh
```bash
# Заменить существующий install.sh на оптимизированную версию
chmod +x install.sh
```

### Шаг 3: Создать правильную структуру папок
```bash
mkdir -p models/{whisper,cache,silero_vad}
mkdir -p logs
```

### Шаг 4: Исправить gunicorn.conf.py
```bash
# Заменить на оптимизированную конфигурацию
```

### Шаг 5: Протестировать GPU доступность
```python
import torch
print("CUDA available:", torch.cuda.is_available())
print("GPU count:", torch.cuda.device_count())
if torch.cuda.is_available():
    print("GPU name:", torch.cuda.get_device_name(0))
```

### Шаг 6: Переустановить зависимости
```bash
source venv/bin/activate
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install faster-whisper
```

## 📊 Ожидаемые улучшения

### Производительность:
- **Скорость транскрипции**: ↑ 300-500%
- **Время отклика**: ↓ от 20 секунд до 1-3 секунд
- **Использование памяти**: ↓ на 60% (small vs large-v3)
- **Загрузка GPU**: Оптимальная утилизация

### Стабильность:
- **Меньше ошибок**: Упрощенная конфигурация
- **Лучшая совместимость**: Правильные версии зависимостей
- **Graceful restart**: Правильные настройки Gunicorn

### Качество:
- **Лучший баланс**: speed/quality с beams=3
- **Меньше галлюцинаций**: Оптимальные frame_threshold
- **Стабильная транскрипция**: Отключены экспериментальные функции

## 🔍 Проверка результатов

### Тест 1: Базовая функциональность
```bash
# Запуск сервера
source venv/bin/activate
python -m whisperlivekit.basic_server

# Проверка в браузере: http://localhost:8000
```

### Тест 2: Производительность GPU
```bash
# Мониторинг GPU
nvidia-smi -l 1

# Проверка времени транскрипции короткой фразы (должно быть < 2 сек)
```

### Тест 3: Качество транскрипции
- Тестирование русской речи
- Проверка точности для коротких фраз
- Проверка стабильности при длительной работе

## 🎯 Финальные рекомендации

1. **Начать с минимальной конфигурации** - использовать оптимизированный .env
2. **Протестировать на малой модели** - убедиться что работает small модель
3. **Постепенно добавлять функции** - диаризацию только если нужно
4. **Мониторить ресурсы** - следить за GPU/CPU загрузкой
5. **Логировать проблемы** - использовать INFO уровень для отладки

Эти исправления должны решить проблему "плохой и медленной транскрибации" и обеспечить стабильную работу в продакшене.