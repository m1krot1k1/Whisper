"""
Performance optimization package for WhisperLiveKit.

This package provides comprehensive performance optimization tools including:

Modules:
- monitor: System performance monitoring and alerting
- memory: Memory optimization and buffer management
- connection: Connection pooling and load balancing
- async_tasks: Async task management and latency optimization
- websocket_compression: WebSocket message compression and batching

Usage:
    from whisperlivekit.performance import (
        performance_monitor,
        memory_optimizer,
        connection_pool,
        task_pool,
        default_compressor
    )

Quick Start:
    # Start performance monitoring
    await performance_monitor.start_monitoring()
    
    # Optimize memory usage
    memory_optimizer.optimize_memory_usage()
    
    # Use optimized connection pool
    async with managed_connection() as conn_id:
        # Your code here
        pass
    
    # Submit async tasks with priority
    task_id = await task_pool.submit(my_coroutine(), priority=TaskPriority.HIGH)
    
    # Compress WebSocket messages
    compressed = await compress_websocket_message(message)
"""

from .monitor import performance_monitor, PerformanceTimer, performance_timer
from .memory import memory_optimizer, CircularAudioBuffer, MemoryPool, SmartCache
from .connection import connection_pool, rate_limiter, load_balancer, managed_connection
from .async_tasks import task_pool, latency_optimizer, resource_scheduler, TaskPriority, optimized_task_context
from .websocket_compression import default_compressor, compress_websocket_message, decompress_websocket_message, OptimizedWebSocketHandler, MessageType

__all__ = [
    # Monitor
    'performance_monitor',
    'PerformanceTimer', 
    'performance_timer',
    
    # Memory
    'memory_optimizer',
    'CircularAudioBuffer',
    'MemoryPool',
    'SmartCache',
    
    # Connection
    'connection_pool',
    'rate_limiter',
    'load_balancer',
    'managed_connection',
    
    # Async Tasks
    'task_pool',
    'latency_optimizer',
    'resource_scheduler',
    'TaskPriority',
    'optimized_task_context',
    
    # WebSocket Compression
    'default_compressor',
    'compress_websocket_message',
    'decompress_websocket_message',
    'OptimizedWebSocketHandler',
    'MessageType'
]

__version__ = "1.0.0"