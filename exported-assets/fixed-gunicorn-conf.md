# Исправленный gunicorn.conf.py для WhisperLiveKit

## Проблемы в текущей конфигурации

### Текущие проблемы:
1. **Слишком много воркеров**: 12 воркеров для одного пользователя избыточно
2. **Высокий таймаут**: 300 секунд может привести к зависаниям
3. **Неоптимальные настройки памяти**: отсутствуют ограничения
4. **Отсутствие мониторинга**: нет проверки состояния воркеров

## Оптимизированная конфигурация

```python
#!/usr/bin/env python3
"""
Оптимизированная конфигурация Gunicorn для WhisperLiveKit
Настроена для производительной работы с GPU ускорением
"""

import multiprocessing
import os
from pathlib import Path

# =============================================
# ОСНОВНЫЕ НАСТРОЙКИ СЕРВЕРА
# =============================================

# Привязка к интерфейсу (0.0.0.0 для внешнего доступа)
bind = os.getenv("WLK_HOST", "0.0.0.0") + ":" + str(os.getenv("WLK_PORT", "8000"))

# Оптимальное количество воркеров для GPU работы
# Для GPU задач лучше меньше воркеров, но стабильных
cpu_count = multiprocessing.cpu_count()
workers = int(os.getenv("WLK_GUNICORN_WORKERS", min(4, cpu_count)))

# Класс воркеров (обязательно для async/WebSocket)
worker_class = os.getenv("WLK_GUNICORN_WORKER_CLASS", "uvicorn.workers.UvicornWorker")

# =============================================
# НАСТРОЙКИ ТАЙМАУТОВ (ОПТИМИЗИРОВАНЫ)
# =============================================

# Сокращенный таймаут для лучшей отзывчивости
timeout = int(os.getenv("WLK_GUNICORN_TIMEOUT", "120"))

# Время ожидания graceful shutdown
graceful_timeout = int(os.getenv("WLK_GUNICORN_GRACEFUL_TIMEOUT", "30"))

# Таймаут для keep-alive соединений
keepalive = 5

# =============================================
# УПРАВЛЕНИЕ ЗАПРОСАМИ (ОПТИМИЗИРОВАНО)
# =============================================

# Ограничение запросов на воркер (предотвращает утечки памяти)
max_requests = int(os.getenv("WLK_GUNICORN_MAX_REQUESTS", "500"))
max_requests_jitter = 50

# Размер очереди подключений
backlog = int(os.getenv("WLK_GUNICORN_BACKLOG", "1024"))

# =============================================
# УПРАВЛЕНИЕ ПАМЯТЬЮ И РЕСУРСАМИ
# =============================================

# Preload приложения (экономия памяти)
preload_app = os.getenv("WLK_GUNICORN_PRELOAD", "true").lower() == "true"

# Максимальный размер запроса (для аудио файлов)
limit_request_line = 8192
limit_request_fields = 100  
limit_request_field_size = 8192

# =============================================
# ЛОГИРОВАНИЕ (УПРОЩЕНО)
# =============================================

# Пути к логам
log_dir = Path("./logs")
log_dir.mkdir(exist_ok=True)

accesslog = str(log_dir / "gunicorn_access.log")
errorlog = str(log_dir / "gunicorn_error.log")

# Уровень логирования
loglevel = os.getenv("WLK_LOG_LEVEL", "info").lower()

# Формат логов
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# =============================================
# БЕЗОПАСНОСТЬ И ПРОИЗВОДИТЕЛЬНОСТЬ
# =============================================

# PID файл для управления процессом
pidfile = os.getenv("WLK_GUNICORN_PIDFILE", "./gunicorn.pid")

# Пользователь и группа (для продакшена)
# user = "whisperlivekit"
# group = "whisperlivekit"

# Переменные окружения для воркеров
raw_env = [
    "CUDA_VISIBLE_DEVICES=0",
    "PYTHONWARNINGS=ignore::UserWarning",
    "TORCH_WARN_LEVEL=0"
]

# =============================================
# НАСТРОЙКИ ДЛЯ GPU РАБОТЫ
# =============================================

# Отключение worker restarts для стабильности GPU
max_worker_connections = 100
worker_connections = 100

# Настройки для work_class uvicorn
if worker_class == "uvicorn.workers.UvicornWorker":
    # Дополнительные настройки для uvicorn воркеров
    worker_tmp_dir = "/dev/shm"  # Использование RAM диска для temp файлов

# =============================================
# ХУКИ ЖИЗНЕННОГО ЦИКЛА
# =============================================

def on_starting(server):
    """Вызывается при запуске master процесса"""
    server.log.info("🚀 Starting WhisperLiveKit server...")
    
    # Проверка GPU доступности
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0)
            server.log.info(f"✅ GPU acceleration available: {gpu_name} ({gpu_count} devices)")
        else:
            server.log.warning("⚠️  GPU not available, using CPU mode")
    except ImportError:
        server.log.warning("⚠️  PyTorch not installed, GPU check skipped")

def on_reload(server):
    """Вызывается при перезагрузке конфигурации"""
    server.log.info("🔄 Reloading WhisperLiveKit server...")

def worker_int(worker):
    """Вызывается при получении SIGINT воркером"""
    worker.log.info("🛑 Worker received SIGINT, shutting down...")

def on_exit(server):
    """Вызывается при завершении работы"""
    server.log.info("👋 WhisperLiveKit server shutting down...")

# =============================================
# ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ ДЛЯ РАЗРАБОТКИ
# =============================================

# Для разработки можно включить автоперезагрузку
if os.getenv("WLK_DEVELOPMENT", "false").lower() == "true":
    reload = True
    workers = 1
    loglevel = "debug"
    server.log.info("🔧 Development mode enabled")

# =============================================
# МОНИТОРИНГ И ДИАГНОСТИКА
# =============================================

def worker_abort(worker):
    """Вызывается при аварийном завершении воркера"""
    worker.log.error(f"💥 Worker {worker.pid} aborted!")

def pre_fork(server, worker):
    """Вызывается перед fork воркера"""
    server.log.info(f"🔄 Forking worker {worker.pid}")

def post_fork(server, worker):
    """Вызывается после fork воркера"""
    server.log.info(f"✅ Worker {worker.pid} ready")
    
    # Установка CUDA устройства для каждого воркера
    if hasattr(worker, 'cfg') and worker.cfg:
        try:
            import os
            os.environ['CUDA_VISIBLE_DEVICES'] = '0'
        except Exception as e:
            worker.log.warning(f"Failed to set CUDA device: {e}")

# =============================================
# ВЫВОД КОНФИГУРАЦИИ
# =============================================

def print_config():
    """Выводит текущую конфигурацию"""
    print(f"""
=== WhisperLiveKit Gunicorn Configuration ===
Bind: {bind}
Workers: {workers}
Worker Class: {worker_class}
Timeout: {timeout}s
Max Requests: {max_requests}
Preload App: {preload_app}
Log Level: {loglevel}
=============================================""")

if __name__ == "__main__":
    print_config()
```

## Использование

### 1. Запуск с новой конфигурацией:
```bash
gunicorn -c gunicorn.conf.py whisperlivekit.basic_server:app
```

### 2. Для разработки:
```bash
WLK_DEVELOPMENT=true gunicorn -c gunicorn.conf.py whisperlivekit.basic_server:app
```

### 3. Мониторинг:
```bash
# Просмотр логов
tail -f logs/gunicorn_access.log
tail -f logs/gunicorn_error.log

# Graceful restart
kill -HUP $(cat gunicorn.pid)

# Остановка
kill -TERM $(cat gunicorn.pid)
```

## Ключевые улучшения

1. **Производительность**: Оптимизированы воркеры для GPU работы
2. **Стабильность**: Добавлены проверки и хуки жизненного цикла  
3. **Мониторинг**: Детальное логирование и диагностика
4. **Безопасность**: Ограничения ресурсов и размеров запросов
5. **Гибкость**: Поддержка dev/prod режимов