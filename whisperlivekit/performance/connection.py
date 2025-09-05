"""
Connection pooling and queue optimization for WhisperLiveKit.

This module provides:
- WebSocket connection pooling and management
- High-performance queuing systems
- Load balancing and concurrency control
- Resource throttling and rate limiting
"""

import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Set
from enum import Enum
import weakref
import threading
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    """WebSocket connection states."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    PROCESSING = "processing"
    IDLE = "idle"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"

@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""
    connection_id: str
    state: ConnectionState = ConnectionState.CONNECTING
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    bytes_processed: int = 0
    messages_processed: int = 0
    error_count: int = 0
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None

class PriorityQueue:
    """
    High-performance priority queue with support for different priority levels.
    
    Features:
    - Multiple priority levels
    - Fair scheduling within priority levels
    - Queue size limits
    - Timeout handling
    """
    
    def __init__(self, max_size: int = 10000, priority_levels: int = 3):
        self.max_size = max_size
        self.priority_levels = priority_levels
        
        # One queue per priority level (0 = highest priority)
        self._queues: List[deque] = [deque() for _ in range(priority_levels)]
        self._sizes = [0] * priority_levels
        self._total_size = 0
        
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
        self._not_full = asyncio.Condition(self._lock)
        
        # Statistics
        self._enqueued = 0
        self._dequeued = 0
        self._dropped = 0
        
    async def put(self, item: Any, priority: int = 1, timeout: Optional[float] = None) -> bool:
        """
        Add item to queue with specified priority.
        
        Args:
            item: Item to add
            priority: Priority level (0 = highest)
            timeout: Maximum time to wait for space
            
        Returns:
            True if item was added, False if queue is full or timeout
        """
        if priority < 0 or priority >= self.priority_levels:
            priority = self.priority_levels - 1
            
        async with self._lock:
            # Wait for space if queue is full
            if self._total_size >= self.max_size:
                if timeout is None:
                    await self._not_full.wait()
                else:
                    try:
                        await asyncio.wait_for(self._not_full.wait(), timeout)
                    except asyncio.TimeoutError:
                        self._dropped += 1
                        return False
            
            # Check again after waiting
            if self._total_size >= self.max_size:
                self._dropped += 1
                return False
            
            # Add to appropriate priority queue
            self._queues[priority].append(item)
            self._sizes[priority] += 1
            self._total_size += 1
            self._enqueued += 1
            
            # Notify waiting consumers
            self._not_empty.notify()
            
            return True
    
    async def get(self, timeout: Optional[float] = None) -> Optional[Any]:
        """
        Get next item from queue (highest priority first).
        
        Args:
            timeout: Maximum time to wait for item
            
        Returns:
            Next item or None if timeout
        """
        async with self._lock:
            # Wait for items if queue is empty
            while self._total_size == 0:
                if timeout is None:
                    await self._not_empty.wait()
                else:
                    try:
                        await asyncio.wait_for(self._not_empty.wait(), timeout)
                    except asyncio.TimeoutError:
                        return None
            
            # Get item from highest priority non-empty queue
            for priority in range(self.priority_levels):
                if self._sizes[priority] > 0:
                    item = self._queues[priority].popleft()
                    self._sizes[priority] -= 1
                    self._total_size -= 1
                    self._dequeued += 1
                    
                    # Notify waiting producers
                    self._not_full.notify()
                    
                    return item
            
            return None
    
    def qsize(self) -> int:
        """Get total queue size."""
        return self._total_size
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            'total_size': self._total_size,
            'max_size': self.max_size,
            'priority_sizes': self._sizes.copy(),
            'utilization_percent': (self._total_size / self.max_size) * 100,
            'enqueued': self._enqueued,
            'dequeued': self._dequeued,
            'dropped': self._dropped,
            'drop_rate_percent': (self._dropped / max(1, self._enqueued)) * 100
        }

class ConnectionPool:
    """
    WebSocket connection pool with load balancing and resource management.
    
    Features:
    - Connection lifecycle management
    - Load balancing across connections
    - Resource throttling
    - Health monitoring
    """
    
    def __init__(self, 
                 max_connections: int = 1000,
                 max_concurrent_per_connection: int = 10,
                 connection_timeout: float = 300.0,  # 5 minutes
                 cleanup_interval: float = 60.0):   # 1 minute
        
        self.max_connections = max_connections
        self.max_concurrent_per_connection = max_concurrent_per_connection
        self.connection_timeout = connection_timeout
        self.cleanup_interval = cleanup_interval
        
        # Connection storage
        self._connections: Dict[str, ConnectionInfo] = {}
        self._connection_loads: Dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Statistics
        self._total_connections = 0
        self._peak_connections = 0
        self._rejected_connections = 0
        
    async def start(self):
        """Start the connection pool."""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Connection pool started")
        
    async def stop(self):
        """Stop the connection pool."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Connection pool stopped")
        
    async def add_connection(self, 
                           connection_id: str = None,
                           client_ip: str = None,
                           user_agent: str = None) -> Optional[str]:
        """
        Add a new connection to the pool.
        
        Args:
            connection_id: Optional connection ID
            client_ip: Client IP address
            user_agent: Client user agent
            
        Returns:
            Connection ID if added, None if rejected
        """
        async with self._lock:
            # Check connection limit
            if len(self._connections) >= self.max_connections:
                self._rejected_connections += 1
                logger.warning(f"Connection rejected: pool full ({len(self._connections)}/{self.max_connections})")
                return None
            
            # Generate connection ID if not provided
            if connection_id is None:
                connection_id = str(uuid.uuid4())
            
            # Create connection info
            conn_info = ConnectionInfo(
                connection_id=connection_id,
                state=ConnectionState.CONNECTED,
                client_ip=client_ip,
                user_agent=user_agent
            )
            
            self._connections[connection_id] = conn_info
            self._connection_loads[connection_id] = 0
            self._total_connections += 1
            
            # Update peak connections
            current_count = len(self._connections)
            if current_count > self._peak_connections:
                self._peak_connections = current_count
            
            logger.debug(f"Connection added: {connection_id} ({current_count} total)")
            return connection_id
    
    async def remove_connection(self, connection_id: str):
        """Remove a connection from the pool."""
        async with self._lock:
            if connection_id in self._connections:
                del self._connections[connection_id]
                del self._connection_loads[connection_id]
                logger.debug(f"Connection removed: {connection_id} ({len(self._connections)} remaining)")
    
    async def update_connection_activity(self, 
                                       connection_id: str,
                                       bytes_processed: int = 0,
                                       messages_processed: int = 0):
        """Update connection activity metrics."""
        async with self._lock:
            if connection_id in self._connections:
                conn = self._connections[connection_id]
                conn.last_activity = time.time()
                conn.bytes_processed += bytes_processed
                conn.messages_processed += messages_processed
    
    async def get_least_loaded_connection(self) -> Optional[str]:
        """Get the connection ID with the lowest load."""
        async with self._lock:
            if not self._connections:
                return None
            
            # Find connection with minimum load
            min_load = min(self._connection_loads.values())
            for conn_id, load in self._connection_loads.items():
                if load == min_load:
                    conn_info = self._connections.get(conn_id)
                    if (conn_info and 
                        conn_info.state == ConnectionState.CONNECTED and
                        load < self.max_concurrent_per_connection):
                        return conn_id
            
            return None
    
    async def acquire_connection_slot(self, connection_id: str) -> bool:
        """
        Acquire a processing slot for a connection.
        
        Args:
            connection_id: Connection to acquire slot for
            
        Returns:
            True if slot acquired, False if connection is overloaded
        """
        async with self._lock:
            if connection_id not in self._connections:
                return False
            
            current_load = self._connection_loads[connection_id]
            if current_load >= self.max_concurrent_per_connection:
                return False
            
            self._connection_loads[connection_id] += 1
            self._connections[connection_id].state = ConnectionState.PROCESSING
            return True
    
    async def release_connection_slot(self, connection_id: str):
        """Release a processing slot for a connection."""
        async with self._lock:
            if connection_id in self._connections:
                current_load = self._connection_loads[connection_id]
                if current_load > 0:
                    self._connection_loads[connection_id] -= 1
                
                # Update state based on remaining load
                if self._connection_loads[connection_id] == 0:
                    self._connections[connection_id].state = ConnectionState.IDLE
    
    async def _cleanup_loop(self):
        """Background task to clean up inactive connections."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_inactive_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in connection cleanup: {e}")
    
    async def _cleanup_inactive_connections(self):
        """Clean up connections that have been inactive too long."""
        current_time = time.time()
        inactive_connections = []
        
        async with self._lock:
            for conn_id, conn_info in self._connections.items():
                if (current_time - conn_info.last_activity > self.connection_timeout and
                    self._connection_loads[conn_id] == 0):
                    inactive_connections.append(conn_id)
        
        for conn_id in inactive_connections:
            await self.remove_connection(conn_id)
            logger.debug(f"Cleaned up inactive connection: {conn_id}")
    
    def get_connection_count(self) -> int:
        """Get current number of connections."""
        return len(self._connections)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        current_time = time.time()
        
        # Calculate connection states
        state_counts = defaultdict(int)
        total_load = 0
        active_connections = 0
        
        for conn_info in self._connections.values():
            state_counts[conn_info.state.value] += 1
            
            if current_time - conn_info.last_activity < 60:  # Active in last minute
                active_connections += 1
        
        for load in self._connection_loads.values():
            total_load += load
        
        return {
            'total_connections': len(self._connections),
            'max_connections': self.max_connections,
            'active_connections': active_connections,
            'peak_connections': self._peak_connections,
            'rejected_connections': self._rejected_connections,
            'total_load': total_load,
            'average_load': total_load / max(1, len(self._connections)),
            'state_distribution': dict(state_counts),
            'utilization_percent': (len(self._connections) / self.max_connections) * 100
        }

class RateLimiter:
    """
    Token bucket rate limiter for controlling request rates.
    
    Features:
    - Per-connection rate limiting
    - Burst allowance
    - Configurable refill rates
    """
    
    def __init__(self, 
                 requests_per_second: float = 10.0,
                 burst_size: int = 20,
                 per_connection: bool = True):
        
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size
        self.per_connection = per_connection
        
        # Token buckets per connection (or global)
        self._buckets: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            'tokens': burst_size,
            'last_refill': time.time()
        })
        
        self._lock = threading.Lock()
        
    def is_allowed(self, connection_id: str = "global") -> bool:
        """
        Check if request is allowed for the given connection.
        
        Args:
            connection_id: Connection ID (or "global" for global limiting)
            
        Returns:
            True if request is allowed, False if rate limited
        """
        if not self.per_connection:
            connection_id = "global"
        
        with self._lock:
            bucket = self._buckets[connection_id]
            current_time = time.time()
            
            # Refill tokens based on elapsed time
            elapsed = current_time - bucket['last_refill']
            tokens_to_add = elapsed * self.requests_per_second
            bucket['tokens'] = min(self.burst_size, bucket['tokens'] + tokens_to_add)
            bucket['last_refill'] = current_time
            
            # Check if request can be served
            if bucket['tokens'] >= 1.0:
                bucket['tokens'] -= 1.0
                return True
            else:
                return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        with self._lock:
            active_connections = len(self._buckets)
            total_tokens = sum(bucket['tokens'] for bucket in self._buckets.values())
            
            return {
                'requests_per_second': self.requests_per_second,
                'burst_size': self.burst_size,
                'active_connections': active_connections,
                'total_available_tokens': total_tokens,
                'average_tokens_per_connection': total_tokens / max(1, active_connections)
            }

class LoadBalancer:
    """
    Load balancer for distributing work across multiple processors.
    
    Features:
    - Round-robin and least-connections algorithms
    - Health checking
    - Automatic failover
    """
    
    def __init__(self, algorithm: str = "least_connections"):
        self.algorithm = algorithm
        self._processors: List[str] = []
        self._processor_loads: Dict[str, int] = defaultdict(int)
        self._processor_health: Dict[str, bool] = defaultdict(lambda: True)
        self._round_robin_index = 0
        self._lock = asyncio.Lock()
        
    async def add_processor(self, processor_id: str):
        """Add a processor to the load balancer."""
        async with self._lock:
            if processor_id not in self._processors:
                self._processors.append(processor_id)
                self._processor_loads[processor_id] = 0
                self._processor_health[processor_id] = True
                logger.debug(f"Processor added: {processor_id}")
    
    async def remove_processor(self, processor_id: str):
        """Remove a processor from the load balancer."""
        async with self._lock:
            if processor_id in self._processors:
                self._processors.remove(processor_id)
                del self._processor_loads[processor_id]
                del self._processor_health[processor_id]
                logger.debug(f"Processor removed: {processor_id}")
    
    async def get_next_processor(self) -> Optional[str]:
        """Get the next processor according to the load balancing algorithm."""
        async with self._lock:
            healthy_processors = [p for p in self._processors if self._processor_health[p]]
            
            if not healthy_processors:
                return None
            
            if self.algorithm == "round_robin":
                processor = healthy_processors[self._round_robin_index % len(healthy_processors)]
                self._round_robin_index += 1
            elif self.algorithm == "least_connections":
                processor = min(healthy_processors, 
                              key=lambda p: self._processor_loads[p])
            else:
                # Default to round robin
                processor = healthy_processors[self._round_robin_index % len(healthy_processors)]
                self._round_robin_index += 1
            
            self._processor_loads[processor] += 1
            return processor
    
    async def release_processor(self, processor_id: str):
        """Release a processor after work completion."""
        async with self._lock:
            if processor_id in self._processor_loads:
                if self._processor_loads[processor_id] > 0:
                    self._processor_loads[processor_id] -= 1
    
    async def mark_processor_unhealthy(self, processor_id: str):
        """Mark a processor as unhealthy."""
        async with self._lock:
            self._processor_health[processor_id] = False
            logger.warning(f"Processor marked unhealthy: {processor_id}")
    
    async def mark_processor_healthy(self, processor_id: str):
        """Mark a processor as healthy."""
        async with self._lock:
            self._processor_health[processor_id] = True
            logger.info(f"Processor marked healthy: {processor_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get load balancer statistics."""
        healthy_count = sum(1 for health in self._processor_health.values() if health)
        total_load = sum(self._processor_loads.values())
        
        return {
            'algorithm': self.algorithm,
            'total_processors': len(self._processors),
            'healthy_processors': healthy_count,
            'total_load': total_load,
            'processor_loads': dict(self._processor_loads),
            'processor_health': dict(self._processor_health)
        }

# Global instances
connection_pool = ConnectionPool()
rate_limiter = RateLimiter()
load_balancer = LoadBalancer()

@asynccontextmanager
async def managed_connection(connection_id: str = None, **kwargs):
    """Context manager for automatic connection lifecycle management."""
    conn_id = await connection_pool.add_connection(connection_id, **kwargs)
    if conn_id is None:
        raise RuntimeError("Failed to acquire connection from pool")
    
    try:
        yield conn_id
    finally:
        await connection_pool.remove_connection(conn_id)