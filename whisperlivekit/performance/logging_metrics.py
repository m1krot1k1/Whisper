"""
Efficient logging system with performance metrics for WhisperLiveKit.

This module provides:
- High-performance structured logging
- Real-time metrics collection
- Log aggregation and analysis
- Performance-aware log levels
- Metric-driven alerting
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable, Union
from enum import Enum
import threading
from pathlib import Path
import queue
import sys

class LogLevel(Enum):
    """Enhanced log levels with performance considerations."""
    TRACE = 5      # Very detailed tracing (performance impact)
    DEBUG = 10     # Debug information
    INFO = 20      # General information
    WARNING = 30   # Warning messages
    ERROR = 40     # Error messages
    CRITICAL = 50  # Critical errors

class MetricType(Enum):
    """Types of metrics to collect."""
    COUNTER = "counter"          # Incrementing count
    GAUGE = "gauge"             # Current value
    HISTOGRAM = "histogram"     # Distribution of values
    TIMING = "timing"           # Duration measurements

@dataclass
class LogEntry:
    """Structured log entry."""
    timestamp: float = field(default_factory=time.time)
    level: LogLevel = LogLevel.INFO
    message: str = ""
    logger_name: str = ""
    module: str = ""
    function: str = ""
    line: int = 0
    thread_id: int = 0
    process_id: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

@dataclass 
class Metric:
    """Performance metric data."""
    name: str
    type: MetricType
    value: Union[int, float]
    timestamp: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)
    unit: str = ""

class MetricsCollector:
    """
    High-performance metrics collection system.
    
    Features:
    - Thread-safe metric collection
    - Automatic aggregation
    - Memory-efficient storage
    - Real-time statistics
    """
    
    def __init__(self, max_metrics: int = 10000, aggregation_window: int = 60):
        self.max_metrics = max_metrics
        self.aggregation_window = aggregation_window
        
        # Metric storage
        self._metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_metrics))
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._timings: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Statistics
        self._total_metrics = 0
        self._start_time = time.time()
        
    def increment(self, name: str, value: float = 1.0, tags: Dict[str, str] = None):
        """Increment a counter metric."""
        with self._lock:
            key = self._build_key(name, tags)
            self._counters[key] += value
            self._record_metric(Metric(name, MetricType.COUNTER, value, tags=tags or {}))
    
    def gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        """Set a gauge metric."""
        with self._lock:
            key = self._build_key(name, tags)
            self._gauges[key] = value
            self._record_metric(Metric(name, MetricType.GAUGE, value, tags=tags or {}))
    
    def histogram(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record a histogram value."""
        with self._lock:
            key = self._build_key(name, tags)
            self._histograms[key].append(value)
            # Keep only recent values
            if len(self._histograms[key]) > 1000:
                self._histograms[key] = self._histograms[key][-500:]
            self._record_metric(Metric(name, MetricType.HISTOGRAM, value, tags=tags or {}))
    
    def timing(self, name: str, duration_ms: float, tags: Dict[str, str] = None):
        """Record a timing measurement."""
        with self._lock:
            key = self._build_key(name, tags)
            self._timings[key].append(duration_ms)
            self._record_metric(Metric(name, MetricType.TIMING, duration_ms, tags=tags or {}, unit="ms"))
    
    def _record_metric(self, metric: Metric):
        """Record a metric in the time series."""
        key = self._build_key(metric.name, metric.tags)
        self._metrics[key].append(metric)
        self._total_metrics += 1
    
    def _build_key(self, name: str, tags: Dict[str, str] = None) -> str:
        """Build a unique key for a metric."""
        if not tags:
            return name
        
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"
    
    def get_counter(self, name: str, tags: Dict[str, str] = None) -> float:
        """Get current counter value."""
        key = self._build_key(name, tags)
        return self._counters.get(key, 0.0)
    
    def get_gauge(self, name: str, tags: Dict[str, str] = None) -> Optional[float]:
        """Get current gauge value."""
        key = self._build_key(name, tags)
        return self._gauges.get(key)
    
    def get_histogram_stats(self, name: str, tags: Dict[str, str] = None) -> Dict[str, float]:
        """Get histogram statistics."""
        key = self._build_key(name, tags)
        values = self._histograms.get(key, [])
        
        if not values:
            return {}
        
        sorted_values = sorted(values)
        count = len(sorted_values)
        
        return {
            'count': count,
            'min': sorted_values[0],
            'max': sorted_values[-1],
            'mean': sum(sorted_values) / count,
            'p50': sorted_values[int(count * 0.5)],
            'p90': sorted_values[int(count * 0.9)],
            'p95': sorted_values[int(count * 0.95)],
            'p99': sorted_values[int(count * 0.99)],
        }
    
    def get_timing_stats(self, name: str, tags: Dict[str, str] = None) -> Dict[str, float]:
        """Get timing statistics."""
        key = self._build_key(name, tags)
        timings = list(self._timings.get(key, []))
        
        if not timings:
            return {}
        
        sorted_timings = sorted(timings)
        count = len(sorted_timings)
        
        return {
            'count': count,
            'min_ms': sorted_timings[0],
            'max_ms': sorted_timings[-1],
            'mean_ms': sum(sorted_timings) / count,
            'p50_ms': sorted_timings[int(count * 0.5)],
            'p90_ms': sorted_timings[int(count * 0.9)],
            'p95_ms': sorted_timings[int(count * 0.95)],
            'p99_ms': sorted_timings[int(count * 0.99)],
        }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all current metrics."""
        with self._lock:
            return {
                'counters': dict(self._counters),
                'gauges': dict(self._gauges),
                'total_metrics': self._total_metrics,
                'uptime_seconds': time.time() - self._start_time,
                'metrics_per_second': self._total_metrics / (time.time() - self._start_time)
            }

class PerformanceLogger:
    """
    High-performance structured logger with metrics integration.
    
    Features:
    - Asynchronous logging to avoid blocking
    - Structured logging with context
    - Automatic performance metrics
    - Log level filtering
    - Multiple output handlers
    """
    
    def __init__(self, 
                 name: str,
                 log_level: LogLevel = LogLevel.INFO,
                 enable_metrics: bool = True,
                 buffer_size: int = 1000):
        
        self.name = name
        self.log_level = log_level
        self.enable_metrics = enable_metrics
        self.buffer_size = buffer_size
        
        # Components
        self.metrics = MetricsCollector() if enable_metrics else None
        
        # Async logging
        self._log_queue = queue.Queue(maxsize=buffer_size)
        self._handlers: List[Callable] = []
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Context
        self._context: Dict[str, Any] = {}
        self._tags: List[str] = []
        
        # Statistics
        self._logs_written = 0
        self._logs_dropped = 0
        
    def start(self):
        """Start the asynchronous logging worker."""
        if self._running:
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._log_worker, daemon=True)
        self._worker_thread.start()
    
    def stop(self):
        """Stop the logging worker and flush remaining logs."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
    
    def add_handler(self, handler: Callable[[LogEntry], None]):
        """Add a log handler function."""
        self._handlers.append(handler)
    
    def set_context(self, **kwargs):
        """Set logging context that will be included in all log entries."""
        self._context.update(kwargs)
    
    def add_tags(self, *tags: str):
        """Add tags to all log entries."""
        self._tags.extend(tags)
    
    def log(self, level: LogLevel, message: str, **kwargs):
        """Log a message with the specified level."""
        if level.value < self.log_level.value:
            return
        
        # Create log entry
        import inspect
        frame = inspect.currentframe().f_back
        
        entry = LogEntry(
            level=level,
            message=message,
            logger_name=self.name,
            module=frame.f_globals.get('__name__', ''),
            function=frame.f_code.co_name,
            line=frame.f_lineno,
            thread_id=threading.get_ident(),
            process_id=os.getpid(),
            context={**self._context, **kwargs},
            tags=self._tags.copy()
        )
        
        # Record metrics
        if self.metrics:
            self.metrics.increment(f"logs.{level.name.lower()}")
            self.metrics.increment("logs.total")
        
        # Queue for async processing
        try:
            self._log_queue.put_nowait(entry)
        except queue.Full:
            self._logs_dropped += 1
    
    def trace(self, message: str, **kwargs):
        """Log trace message."""
        self.log(LogLevel.TRACE, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self.log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self.log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self.log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message.""" 
        self.log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self.log(LogLevel.CRITICAL, message, **kwargs)
    
    def _log_worker(self):
        """Background worker to process log entries."""
        while self._running or not self._log_queue.empty():
            try:
                # Get log entry with timeout
                try:
                    entry = self._log_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Process with all handlers
                for handler in self._handlers:
                    try:
                        handler(entry)
                    except Exception as e:
                        # Avoid infinite recursion by using print
                        print(f"Log handler error: {e}", file=sys.stderr)
                
                self._logs_written += 1
                self._log_queue.task_done()
                
            except Exception as e:
                print(f"Log worker error: {e}", file=sys.stderr)

# Log handlers
def console_handler(entry: LogEntry):
    """Console log handler."""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry.timestamp))
    level_name = entry.level.name
    
    # Format message
    message = f"[{timestamp}] {level_name:8} {entry.logger_name}: {entry.message}"
    
    # Add context if present
    if entry.context:
        context_str = " ".join(f"{k}={v}" for k, v in entry.context.items())
        message += f" ({context_str})"
    
    print(message)

def json_file_handler(file_path: str):
    """Create a JSON file handler."""
    def handler(entry: LogEntry):
        with open(file_path, 'a', encoding='utf-8') as f:
            json.dump(asdict(entry), f, ensure_ascii=False, default=str)
            f.write('\n')
    return handler

def structured_file_handler(file_path: str):
    """Create a structured text file handler."""
    def handler(entry: LogEntry):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry.timestamp))
        
        # Build structured line
        parts = [
            f"timestamp={timestamp}",
            f"level={entry.level.name}",
            f"logger={entry.logger_name}",
            f"message=\"{entry.message}\"",
        ]
        
        # Add context
        for k, v in entry.context.items():
            parts.append(f"{k}={v}")
        
        # Add tags
        if entry.tags:
            parts.append(f"tags={','.join(entry.tags)}")
        
        line = " ".join(parts)
        
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    
    return handler

class TimingContext:
    """Context manager for timing operations with automatic metrics."""
    
    def __init__(self, logger: PerformanceLogger, operation_name: str, **tags):
        self.logger = logger
        self.operation_name = operation_name
        self.tags = tags
        self.start_time = 0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        
        # Log timing
        self.logger.debug(f"{self.operation_name} completed", 
                         duration_ms=duration_ms, **self.tags)
        
        # Record metrics
        if self.logger.metrics:
            self.logger.metrics.timing(f"operation.{self.operation_name}", 
                                     duration_ms, self.tags)

# Factory function
def create_performance_logger(name: str, 
                            log_level: LogLevel = LogLevel.INFO,
                            log_file: Optional[str] = None,
                            enable_console: bool = True,
                            enable_metrics: bool = True) -> PerformanceLogger:
    """Create a configured performance logger."""
    logger = PerformanceLogger(name, log_level, enable_metrics)
    
    # Add handlers
    if enable_console:
        logger.add_handler(console_handler)
    
    if log_file:
        logger.add_handler(structured_file_handler(log_file))
    
    logger.start()
    return logger

# Global logger instance
default_logger = create_performance_logger("whisperlivekit", LogLevel.INFO)