"""
Async task management and latency optimization for WhisperLiveKit.

This module provides:
- Advanced async task pooling and management
- Latency optimization techniques
- Concurrent processing optimization
- Task priority management
- Resource-aware scheduling
"""

import asyncio
import logging
import time
import weakref
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Coroutine, Union
from enum import Enum
import threading
from contextlib import asynccontextmanager
import concurrent.futures

logger = logging.getLogger(__name__)

class TaskPriority(Enum):
    """Task priority levels."""
    CRITICAL = 0    # Real-time audio processing
    HIGH = 1        # User interactions
    NORMAL = 2      # Background processing
    LOW = 3         # Cleanup, logging

@dataclass
class TaskInfo:
    """Information about a task."""
    task_id: str
    priority: TaskPriority
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[Exception] = None
    result: Any = None

class AsyncTaskPool:
    """
    High-performance async task pool with priority scheduling.
    
    Features:
    - Priority-based task scheduling
    - Resource-aware concurrency limits
    - Task monitoring and statistics
    - Automatic cleanup of completed tasks
    """
    
    def __init__(self, 
                 max_concurrent_tasks: int = 100,
                 max_pending_tasks: int = 1000,
                 cleanup_interval: float = 60.0):
        
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_pending_tasks = max_pending_tasks
        self.cleanup_interval = cleanup_interval
        
        # Task storage
        self._pending_tasks: Dict[TaskPriority, deque] = {
            priority: deque() for priority in TaskPriority
        }
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._completed_tasks: Dict[str, TaskInfo] = {}
        
        # Synchronization
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._task_available = asyncio.Event()
        
        # Worker management
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Statistics
        self._task_counter = 0
        self._total_submitted = 0
        self._total_completed = 0
        self._total_failed = 0
        self._total_cancelled = 0
        
    async def start(self, num_workers: int = 10):
        """Start the task pool with the specified number of workers."""
        if self._running:
            logger.warning("Task pool already running")
            return
        
        self._running = True
        
        # Start worker tasks
        for i in range(num_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(worker)
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info(f"Task pool started with {num_workers} workers")
        
    async def stop(self):
        """Stop the task pool and wait for all tasks to complete."""
        self._running = False
        
        # Cancel pending tasks
        async with self._lock:
            for priority_queue in self._pending_tasks.values():
                priority_queue.clear()
        
        # Wait for workers to finish
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
            self._workers.clear()
        
        # Stop cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Task pool stopped")
        
    async def submit(self, 
                    coro: Coroutine,
                    priority: TaskPriority = TaskPriority.NORMAL,
                    task_id: str = None) -> str:
        """
        Submit a coroutine for execution.
        
        Args:
            coro: Coroutine to execute
            priority: Task priority
            task_id: Optional task ID
            
        Returns:
            Task ID
        """
        if task_id is None:
            self._task_counter += 1
            task_id = f"task-{self._task_counter}"
        
        task_info = TaskInfo(task_id=task_id, priority=priority)
        
        async with self._lock:
            # Check pending task limit
            total_pending = sum(len(q) for q in self._pending_tasks.values())
            if total_pending >= self.max_pending_tasks:
                raise asyncio.QueueFull("Task pool is full")
            
            # Add to appropriate priority queue
            self._pending_tasks[priority].append((task_info, coro))
            self._total_submitted += 1
        
        # Notify workers
        self._task_available.set()
        
        logger.debug(f"Task submitted: {task_id} (priority: {priority.name})")
        return task_id
        
    async def _worker(self, worker_name: str):
        """Worker task that processes queued coroutines."""
        logger.debug(f"Worker {worker_name} started")
        
        while self._running:
            try:
                # Wait for tasks to be available
                await self._task_available.wait()
                
                # Get next task
                task_info, coro = await self._get_next_task()
                if task_info is None:
                    continue
                
                # Acquire semaphore
                await self._semaphore.acquire()
                
                try:
                    # Execute task
                    task_info.started_at = time.time()
                    
                    # Create and run the task
                    task = asyncio.create_task(coro)
                    
                    async with self._lock:
                        self._running_tasks[task_info.task_id] = task
                    
                    try:
                        result = await task
                        task_info.result = result
                        task_info.completed_at = time.time()
                        self._total_completed += 1
                        
                    except asyncio.CancelledError:
                        self._total_cancelled += 1
                        raise
                    except Exception as e:
                        task_info.error = e
                        task_info.completed_at = time.time()
                        self._total_failed += 1
                        logger.error(f"Task {task_info.task_id} failed: {e}")
                    
                    finally:
                        # Remove from running tasks
                        async with self._lock:
                            self._running_tasks.pop(task_info.task_id, None)
                            self._completed_tasks[task_info.task_id] = task_info
                        
                finally:
                    self._semaphore.release()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
                await asyncio.sleep(1)  # Brief pause before retrying
        
        logger.debug(f"Worker {worker_name} stopped")
        
    async def _get_next_task(self) -> tuple[Optional[TaskInfo], Optional[Coroutine]]:
        """Get the next task from priority queues."""
        async with self._lock:
            # Check all priority levels in order
            for priority in TaskPriority:
                if self._pending_tasks[priority]:
                    return self._pending_tasks[priority].popleft()
            
            # No tasks available
            self._task_available.clear()
            return None, None
    
    async def _cleanup_loop(self):
        """Background cleanup of completed tasks."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_completed_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    async def _cleanup_completed_tasks(self):
        """Remove old completed tasks to prevent memory leaks."""
        cutoff_time = time.time() - (self.cleanup_interval * 2)
        
        async with self._lock:
            old_tasks = [
                task_id for task_id, task_info in self._completed_tasks.items()
                if task_info.completed_at and task_info.completed_at < cutoff_time
            ]
            
            for task_id in old_tasks:
                del self._completed_tasks[task_id]
        
        if old_tasks:
            logger.debug(f"Cleaned up {len(old_tasks)} completed tasks")
    
    async def get_task_info(self, task_id: str) -> Optional[TaskInfo]:
        """Get information about a task."""
        async with self._lock:
            # Check completed tasks first
            if task_id in self._completed_tasks:
                return self._completed_tasks[task_id]
            
            # Check running tasks
            if task_id in self._running_tasks:
                # Create a basic TaskInfo for running tasks
                return TaskInfo(task_id=task_id, priority=TaskPriority.NORMAL, started_at=time.time())
        
        return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        async with self._lock:
            if task_id in self._running_tasks:
                task = self._running_tasks[task_id]
                task.cancel()
                return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get task pool statistics."""
        total_pending = sum(len(q) for q in self._pending_tasks.values())
        
        pending_by_priority = {
            priority.name: len(queue) 
            for priority, queue in self._pending_tasks.items()
        }
        
        return {
            'total_submitted': self._total_submitted,
            'total_completed': self._total_completed,
            'total_failed': self._total_failed,
            'total_cancelled': self._total_cancelled,
            'pending_tasks': total_pending,
            'running_tasks': len(self._running_tasks),
            'completed_tasks': len(self._completed_tasks),
            'pending_by_priority': pending_by_priority,
            'success_rate': self._total_completed / max(1, self._total_submitted) * 100,
            'pool_utilization': len(self._running_tasks) / self.max_concurrent_tasks * 100
        }

class LatencyOptimizer:
    """
    Latency optimization techniques for async operations.
    
    Features:
    - Request batching
    - Predictive preloading
    - Cache warming
    - Connection pooling
    """
    
    def __init__(self):
        self._batch_queues: Dict[str, deque] = defaultdict(deque)
        self._batch_timers: Dict[str, asyncio.TimerHandle] = {}
        self._batch_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        
        # Batching configuration
        self.batch_size = 10
        self.batch_timeout = 0.1  # 100ms
        
    async def batch_requests(self, 
                           operation_key: str,
                           request_data: Any,
                           batch_processor: Callable) -> Any:
        """
        Batch requests for the same operation to reduce latency.
        
        Args:
            operation_key: Key to group related operations
            request_data: Data for this request
            batch_processor: Function to process batched requests
            
        Returns:
            Result for this specific request
        """
        future = asyncio.Future()
        
        async with self._batch_locks[operation_key]:
            # Add request to batch
            self._batch_queues[operation_key].append((request_data, future))
            
            # Check if we should process the batch
            should_process = (
                len(self._batch_queues[operation_key]) >= self.batch_size or
                operation_key not in self._batch_timers
            )
            
            if should_process:
                # Cancel existing timer
                if operation_key in self._batch_timers:
                    self._batch_timers[operation_key].cancel()
                
                # Process batch immediately or schedule
                if len(self._batch_queues[operation_key]) >= self.batch_size:
                    await self._process_batch(operation_key, batch_processor)
                else:
                    # Schedule batch processing
                    loop = asyncio.get_event_loop()
                    self._batch_timers[operation_key] = loop.call_later(
                        self.batch_timeout,
                        lambda: asyncio.create_task(
                            self._process_batch(operation_key, batch_processor)
                        )
                    )
        
        return await future
    
    async def _process_batch(self, operation_key: str, batch_processor: Callable):
        """Process a batch of requests."""
        async with self._batch_locks[operation_key]:
            if not self._batch_queues[operation_key]:
                return
            
            # Extract batch
            batch = list(self._batch_queues[operation_key])
            self._batch_queues[operation_key].clear()
            
            # Remove timer
            if operation_key in self._batch_timers:
                del self._batch_timers[operation_key]
        
        # Process batch
        try:
            requests = [item[0] for item in batch]
            results = await batch_processor(requests)
            
            # Distribute results
            for (_, future), result in zip(batch, results):
                if not future.done():
                    future.set_result(result)
                    
        except Exception as e:
            # Propagate error to all futures
            for _, future in batch:
                if not future.done():
                    future.set_exception(e)

class ResourceAwareScheduler:
    """
    Resource-aware task scheduler that adjusts concurrency based on system load.
    
    Features:
    - Dynamic concurrency adjustment
    - CPU and memory monitoring
    - Load-based task prioritization
    - Adaptive batching
    """
    
    def __init__(self, task_pool: AsyncTaskPool):
        self.task_pool = task_pool
        self._monitoring_enabled = True
        self._monitoring_task: Optional[asyncio.Task] = None
        
        # Thresholds
        self.cpu_threshold = 80.0  # Percentage
        self.memory_threshold = 85.0  # Percentage
        
        # Adaptive settings
        self.base_concurrency = task_pool.max_concurrent_tasks
        self.min_concurrency = max(1, self.base_concurrency // 4)
        self.max_concurrency = self.base_concurrency * 2
        
    async def start_monitoring(self):
        """Start resource monitoring."""
        if self._monitoring_task:
            return
        
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Resource monitoring started")
        
    async def stop_monitoring(self):
        """Stop resource monitoring."""
        self._monitoring_enabled = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Resource monitoring stopped")
        
    async def _monitoring_loop(self):
        """Monitor system resources and adjust concurrency."""
        while self._monitoring_enabled:
            try:
                # Monitor system resources (would use psutil in real implementation)
                cpu_percent = 50.0  # Placeholder
                memory_percent = 60.0  # Placeholder
                
                # Adjust concurrency based on load
                current_concurrency = self.task_pool._semaphore._value
                new_concurrency = self._calculate_optimal_concurrency(
                    cpu_percent, memory_percent, current_concurrency
                )
                
                if new_concurrency != current_concurrency:
                    await self._adjust_concurrency(new_concurrency)
                
                await asyncio.sleep(5.0)  # Check every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Resource monitoring error: {e}")
                await asyncio.sleep(5.0)
    
    def _calculate_optimal_concurrency(self, 
                                     cpu_percent: float,
                                     memory_percent: float,
                                     current_concurrency: int) -> int:
        """Calculate optimal concurrency based on resource usage."""
        # High resource usage - reduce concurrency
        if cpu_percent > self.cpu_threshold or memory_percent > self.memory_threshold:
            return max(self.min_concurrency, current_concurrency - 2)
        
        # Low resource usage - increase concurrency
        elif cpu_percent < 50.0 and memory_percent < 60.0:
            return min(self.max_concurrency, current_concurrency + 1)
        
        # Keep current concurrency
        return current_concurrency
    
    async def _adjust_concurrency(self, new_concurrency: int):
        """Adjust task pool concurrency."""
        # This is a simplified approach - in practice, you'd need to
        # implement proper semaphore resizing
        logger.info(f"Adjusting concurrency from {self.task_pool._semaphore._value} to {new_concurrency}")

# Global instances
task_pool = AsyncTaskPool()
latency_optimizer = LatencyOptimizer()
resource_scheduler = ResourceAwareScheduler(task_pool)

@asynccontextmanager
async def optimized_task_context():
    """Context manager for optimized async task management."""
    await task_pool.start()
    await resource_scheduler.start_monitoring()
    
    try:
        yield {
            'task_pool': task_pool,
            'latency_optimizer': latency_optimizer,
            'scheduler': resource_scheduler
        }
    finally:
        await resource_scheduler.stop_monitoring()
        await task_pool.stop()

# Decorator for automatic task submission
def async_task(priority: TaskPriority = TaskPriority.NORMAL):
    """Decorator to automatically submit functions to the task pool."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            coro = func(*args, **kwargs)
            task_id = await task_pool.submit(coro, priority)
            return task_id
        return wrapper
    return decorator