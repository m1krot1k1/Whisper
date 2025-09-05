# Gunicorn configuration for WhisperLiveKit
# Конфигурация Gunicorn для WhisperLiveKit

import os
import multiprocessing

# =================================================================
# ОСНОВНЫЕ НАСТРОЙКИ
# =================================================================

# Адрес и порт для привязки
bind = f"{os.getenv('WLK_HOST', 'localhost')}:{os.getenv('WLK_PORT', '8000')}"

# Количество worker процессов
# Рекомендуемая формула: 2 * CPU_CORES + 1
workers = int(os.getenv('WLK_GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))

# Класс worker'а (обязательно для WebSocket)
worker_class = os.getenv('WLK_GUNICORN_WORKER_CLASS', 'uvicorn.workers.UvicornWorker')

# Тайм-аут для worker'ов (секунды)
timeout = int(os.getenv('WLK_GUNICORN_TIMEOUT', '180'))

# =================================================================
# ПРОИЗВОДИТЕЛЬНОСТЬ
# =================================================================

# Максимальное количество одновременных соединений на worker
max_requests = int(os.getenv('WLK_GUNICORN_MAX_REQUESTS', '1000'))

# Случайное отклонение для max_requests (предотвращает одновременный restart всех workers)
max_requests_jitter = max_requests // 10

# Количество слушающих сокетов (backlog)
backlog = int(os.getenv('WLK_GUNICORN_BACKLOG', '2048'))

# Включить режим preload (загрузка приложения до создания workers)
preload_app = os.getenv('WLK_GUNICORN_PRELOAD', 'true').lower() == 'true'

# =================================================================
# ЛОГИРОВАНИЕ
# =================================================================

# Уровень логирования
loglevel = os.getenv('WLK_LOG_LEVEL', 'info').lower()

# Файлы логов
accesslog = os.getenv('WLK_GUNICORN_ACCESS_LOG', './logs/gunicorn_access.log')
errorlog = os.getenv('WLK_GUNICORN_ERROR_LOG', './logs/gunicorn_error.log')

# Формат логов доступа
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Отключить стандартный вывод логов (использовать только файлы)
disable_redirect_access_to_syslog = True

# =================================================================
# БЕЗОПАСНОСТЬ И НАДЕЖНОСТЬ
# =================================================================

# Максимальное время ожидания graceful shutdown
graceful_timeout = int(os.getenv('WLK_GUNICORN_GRACEFUL_TIMEOUT', '30'))

# PID файл для контроля процесса
pidfile = os.getenv('WLK_GUNICORN_PIDFILE', './gunicorn.pid')

# Пользователь и группа (только для Unix-систем)
# user = 'whisper'
# group = 'whisper'

# =================================================================
# МОНИТОРИНГ
# =================================================================

# Включить статистику
enable_stdio_inheritance = True

# =================================================================
# SSL/TLS НАСТРОЙКИ (если используется HTTPS)
# =================================================================

# SSL сертификат и ключ
keyfile = os.getenv('WLK_SSL_KEYFILE', None)
certfile = os.getenv('WLK_SSL_CERTFILE', None)

# Версия SSL/TLS
ssl_version = 3  # TLS 1.2+

# =================================================================
# ХУКИ И ОБРАБОТЧИКИ СОБЫТИЙ
# =================================================================

def on_starting(server):
    """Вызывается при запуске мастер-процесса"""
    server.log.info("Starting WhisperLiveKit with Gunicorn")
    
    # Создаем папку для логов если её нет
    log_dir = os.path.dirname(accesslog) if accesslog else './logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # Проверяем наличие FFmpeg
    import shutil
    if not shutil.which('ffmpeg'):
        server.log.warning("FFmpeg not found in PATH. Audio processing may not work properly.")

def on_reload(server):
    """Вызывается при перезагрузке конфигурации"""
    server.log.info("Reloading WhisperLiveKit configuration")

def worker_int(worker):
    """Вызывается при получении сигнала SIGINT worker'ом"""
    worker.log.info("Worker received SIGINT signal, shutting down gracefully")

def pre_fork(server, worker):
    """Вызывается перед созданием worker'а"""
    server.log.info(f"Starting worker process {worker.pid}")

def post_fork(server, worker):
    """Вызывается после создания worker'а"""
    server.log.info(f"Worker {worker.pid} started successfully")

def pre_exec(server):
    """Вызывается перед exec() при restart"""
    server.log.info("Restarting WhisperLiveKit server")

def when_ready(server):
    """Вызывается когда сервер готов к приему соединений"""
    server.log.info(f"WhisperLiveKit server ready at {bind}")
    server.log.info(f"Running with {workers} worker processes")
    server.log.info(f"Worker class: {worker_class}")
    
    # Выводим конфигурацию модели если доступна
    model = os.getenv('WLK_MODEL', 'small')
    language = os.getenv('WLK_LANGUAGE', 'auto')
    diarization = os.getenv('WLK_DIARIZATION', 'false')
    
    server.log.info(f"Model: {model}, Language: {language}, Diarization: {diarization}")

def worker_abort(worker):
    """Вызывается при аварийном завершении worker'а"""
    worker.log.error(f"Worker {worker.pid} aborted")

# =================================================================
# НАСТРОЙКИ ДЛЯ РАЗРАБОТКИ И ОТЛАДКИ
# =================================================================

# Перезагрузка при изменении файлов (только для разработки)
if os.getenv('WLK_DEV_MODE', 'false').lower() == 'true':
    reload = True
    reload_extra_files = ['./env.example', './.env']
    worker_class = 'uvicorn.workers.UvicornWorker'
    workers = 1  # Для отладки лучше использовать один worker
    loglevel = 'debug'
    timeout = 0  # Отключить тайм-аут для отладки

# =================================================================
# ПРОВЕРКА ЗАВИСИМОСТЕЙ
# =================================================================

def validate_dependencies():
    """Проверяет наличие необходимых зависимостей"""
    try:
        import whisperlivekit
        import torch
        import uvicorn
        return True
    except ImportError as e:
        print(f"Missing dependency: {e}")
        return False

# Проверяем зависимости при загрузке конфигурации
if not validate_dependencies():
    raise RuntimeError("Required dependencies not found. Please run install.sh first.")

# =================================================================
# ИНФОРМАЦИЯ О КОНФИГУРАЦИИ
# =================================================================

print(f"""
╔══════════════════════════════════════════════════════════╗
║                 WhisperLiveKit Gunicorn                 ║
║                     Configuration                       ║
╠══════════════════════════════════════════════════════════╣
║ Workers: {workers:<47} ║
║ Worker Class: {worker_class:<42} ║
║ Bind Address: {bind:<42} ║
║ Timeout: {timeout}s{'':<45} ║
║ Max Requests: {max_requests:<40} ║
║ Preload App: {preload_app:<43} ║
║ Log Level: {loglevel:<45} ║
╚══════════════════════════════════════════════════════════╝
""")