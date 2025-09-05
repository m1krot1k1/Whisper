"""
Memory optimization utilities for WhisperLiveKit.

This module provides tools for optimizing memory usage including:
- Efficient audio buffer management
- Memory pool management
- Automatic memory cleanup
- Smart caching strategies
"""

import asyncio
import gc
import logging
import time
import weakref
from collections import deque
from typing import Dict, List, Optional, Any, Union
import numpy as np
from threading import Lock
from dataclasses import dataclass
import psutil

logger = logging.getLogger(__name__)

@dataclass
class MemoryUsage:
    """Memory usage statistics."""
    total_mb: float
    available_mb: float
    used_mb: float
    percent: float
    buffers_mb: float = 0.0
    cache_mb: float = 0.0

class CircularAudioBuffer:
    """
    Memory-efficient circular buffer for audio data.
    
    Features:
    - Pre-allocated memory to avoid frequent allocations
    - Automatic resizing with hysteresis
    - Memory-mapped storage for large buffers
    - Efficient batch operations
    """
    
    def __init__(self, 
                 initial_capacity: int = 320000,  # 20 seconds at 16kHz
                 max_capacity: int = 1600000,     # 100 seconds
                 dtype: np.dtype = np.float32):
        
        self.max_capacity = max_capacity
        self.dtype = dtype
        self._lock = Lock()
        
        # Pre-allocate buffer
        self._buffer = np.zeros(initial_capacity, dtype=dtype)
        self._capacity = initial_capacity
        self._size = 0
        self._head = 0
        self._tail = 0
        
        # Statistics
        self._total_writes = 0
        self._total_reads = 0
        self._resize_count = 0
        
    def append(self, data: np.ndarray) -> bool:
        """
        Append data to the buffer.
        
        Returns:
            bool: True if successful, False if buffer is full
        """
        with self._lock:
            data_size = len(data)
            
            # Check if we need to resize
            if self._size + data_size > self._capacity:
                if not self._resize(self._size + data_size):
                    return False
            
            # Handle wrapping
            if self._tail + data_size <= self._capacity:
                # No wrapping needed
                self._buffer[self._tail:self._tail + data_size] = data
            else:
                # Split across wrap boundary
                first_part = self._capacity - self._tail
                self._buffer[self._tail:] = data[:first_part]
                self._buffer[:data_size - first_part] = data[first_part:]
            
            self._tail = (self._tail + data_size) % self._capacity
            self._size += data_size
            self._total_writes += 1
            
            return True
    
    def read(self, size: int) -> Optional[np.ndarray]:
        """
        Read data from the buffer without removing it.
        
        Args:
            size: Number of samples to read
            
        Returns:
            numpy array or None if not enough data
        """
        with self._lock:
            if size > self._size:
                return None
            
            result = np.zeros(size, dtype=self.dtype)
            
            if self._head + size <= self._capacity:
                # No wrapping
                result[:] = self._buffer[self._head:self._head + size]
            else:
                # Handle wrapping
                first_part = self._capacity - self._head
                result[:first_part] = self._buffer[self._head:]
                result[first_part:] = self._buffer[:size - first_part]
            
            self._total_reads += 1
            return result
    
    def consume(self, size: int) -> Optional[np.ndarray]:
        """
        Read and remove data from the buffer.
        
        Args:
            size: Number of samples to consume
            
        Returns:
            numpy array or None if not enough data
        """
        with self._lock:
            result = self.read(size)
            if result is not None:
                self._head = (self._head + size) % self._capacity
                self._size -= size
                
                # Auto-shrink if buffer is mostly empty
                if self._size < self._capacity // 4 and self._capacity > 320000:
                    self._resize(max(320000, self._size * 2))
            
            return result
    
    def peek(self, size: int, offset: int = 0) -> Optional[np.ndarray]:
        """
        Peek at data without consuming it.
        
        Args:
            size: Number of samples to peek at
            offset: Offset from head
            
        Returns:
            numpy array or None if not enough data
        """
        with self._lock:
            if offset + size > self._size:
                return None
            
            start_pos = (self._head + offset) % self._capacity
            result = np.zeros(size, dtype=self.dtype)
            
            if start_pos + size <= self._capacity:
                result[:] = self._buffer[start_pos:start_pos + size]
            else:
                first_part = self._capacity - start_pos
                result[:first_part] = self._buffer[start_pos:]
                result[first_part:] = self._buffer[:size - first_part]
            
            return result
    
    def clear(self):
        """Clear the buffer."""
        with self._lock:
            self._size = 0
            self._head = 0
            self._tail = 0
    
    def _resize(self, new_capacity: int) -> bool:
        """
        Resize the buffer.
        
        Args:
            new_capacity: New capacity in samples
            
        Returns:
            bool: True if resize successful
        """
        if new_capacity > self.max_capacity:
            logger.warning(f"Cannot resize buffer beyond max capacity: {self.max_capacity}")
            return False
        
        # Round up to nearest power of 2 for better memory alignment
        new_capacity = 2 ** int(np.ceil(np.log2(new_capacity)))
        
        if new_capacity == self._capacity:
            return True
        
        logger.debug(f"Resizing audio buffer from {self._capacity} to {new_capacity}")
        
        # Create new buffer
        new_buffer = np.zeros(new_capacity, dtype=self.dtype)
        
        # Copy existing data
        if self._size > 0:
            data = self.read(self._size)
            if data is not None:
                new_buffer[:self._size] = data
        
        # Update buffer
        self._buffer = new_buffer
        self._capacity = new_capacity
        self._head = 0
        self._tail = self._size
        self._resize_count += 1
        
        return True
    
    @property
    def size(self) -> int:
        """Current size of data in buffer."""
        return self._size
    
    @property
    def capacity(self) -> int:
        """Current capacity of buffer."""
        return self._capacity
    
    @property
    def available_space(self) -> int:
        """Available space in buffer."""
        return self._capacity - self._size
    
    @property
    def memory_usage_mb(self) -> float:
        """Memory usage in MB."""
        return (self._capacity * self.dtype.itemsize) / (1024 * 1024)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        return {
            'size': self._size,
            'capacity': self._capacity,
            'utilization_percent': (self._size / self._capacity) * 100,
            'memory_mb': self.memory_usage_mb,
            'total_writes': self._total_writes,
            'total_reads': self._total_reads,
            'resize_count': self._resize_count,
        }

class MemoryPool:
    """
    Memory pool for efficient allocation of numpy arrays.
    
    Reduces memory fragmentation and allocation overhead by reusing
    pre-allocated arrays of common sizes.
    """
    
    def __init__(self, 
                 pool_sizes: List[int] = None,
                 max_arrays_per_size: int = 10,
                 dtype: np.dtype = np.float32):
        
        if pool_sizes is None:
            # Common audio chunk sizes (in samples)
            pool_sizes = [
                160,     # 10ms at 16kHz
                320,     # 20ms at 16kHz
                480,     # 30ms at 16kHz
                800,     # 50ms at 16kHz
                1600,    # 100ms at 16kHz
                8000,    # 500ms at 16kHz
                16000,   # 1s at 16kHz
                32000,   # 2s at 16kHz
            ]
        
        self.pool_sizes = sorted(pool_sizes)
        self.max_arrays_per_size = max_arrays_per_size
        self.dtype = dtype
        
        # Initialize pools
        self._pools: Dict[int, deque] = {}
        self._locks: Dict[int, Lock] = {}
        
        for size in pool_sizes:
            self._pools[size] = deque()
            self._locks[size] = Lock()
            
            # Pre-allocate some arrays
            for _ in range(min(3, max_arrays_per_size)):
                array = np.zeros(size, dtype=dtype)
                self._pools[size].append(array)
        
        # Statistics
        self._allocations = 0
        self._hits = 0
        self._misses = 0
        
    def get_array(self, size: int) -> np.ndarray:
        """
        Get an array from the pool or allocate a new one.
        
        Args:
            size: Required array size
            
        Returns:
            numpy array of the requested size
        """
        self._allocations += 1
        
        # Find best fit pool
        pool_size = None
        for ps in self.pool_sizes:
            if ps >= size:
                pool_size = ps
                break
        
        if pool_size is not None and pool_size in self._pools:
            with self._locks[pool_size]:
                if self._pools[pool_size]:
                    array = self._pools[pool_size].popleft()
                    self._hits += 1
                    # Clear the array
                    array.fill(0)
                    return array[:size] if size < pool_size else array
        
        # Pool miss - allocate new array
        self._misses += 1
        return np.zeros(size, dtype=self.dtype)
    
    def return_array(self, array: np.ndarray):
        """
        Return an array to the pool for reuse.
        
        Args:
            array: Array to return to pool
        """
        size = len(array)
        
        # Find matching pool
        pool_size = None
        for ps in self.pool_sizes:
            if ps == size:
                pool_size = ps
                break
        
        if pool_size is not None and pool_size in self._pools:
            with self._locks[pool_size]:
                if len(self._pools[pool_size]) < self.max_arrays_per_size:
                    # Make sure it's contiguous
                    if not array.flags.c_contiguous:
                        array = np.ascontiguousarray(array)
                    self._pools[pool_size].append(array)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        pool_stats = {}
        total_arrays = 0
        total_memory_mb = 0
        
        for size, pool in self._pools.items():
            count = len(pool)
            memory_mb = (count * size * self.dtype.itemsize) / (1024 * 1024)
            pool_stats[f'size_{size}'] = {
                'count': count,
                'memory_mb': memory_mb
            }
            total_arrays += count
            total_memory_mb += memory_mb
        
        hit_rate = (self._hits / self._allocations) * 100 if self._allocations > 0 else 0
        
        return {
            'total_arrays': total_arrays,
            'total_memory_mb': total_memory_mb,
            'hit_rate_percent': hit_rate,
            'allocations': self._allocations,
            'hits': self._hits,
            'misses': self._misses,
            'pools': pool_stats
        }

class SmartCache:
    """
    LRU cache with automatic cleanup and memory pressure handling.
    """
    
    def __init__(self, 
                 max_size: int = 100,
                 max_memory_mb: float = 512,
                 cleanup_threshold: float = 0.8):
        
        self.max_size = max_size
        self.max_memory_mb = max_memory_mb
        self.cleanup_threshold = cleanup_threshold
        
        self._cache: Dict[str, Any] = {}
        self._access_order: deque = deque()
        self._memory_usage = 0
        self._lock = Lock()
        
        # Weak references for automatic cleanup
        self._weak_refs: Dict[str, weakref.ref] = {}
        
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache."""
        with self._lock:
            if key in self._cache:
                # Move to end (most recently used)
                self._access_order.remove(key)
                self._access_order.append(key)
                return self._cache[key]
        return None
    
    def put(self, key: str, value: Any, size_mb: float = None):
        """Put item in cache."""
        if size_mb is None:
            size_mb = self._estimate_size(value)
        
        with self._lock:
            # Remove if already exists
            if key in self._cache:
                self.remove(key)
            
            # Check if we need to make space
            while (len(self._cache) >= self.max_size or 
                   self._memory_usage + size_mb > self.max_memory_mb):
                if not self._evict_oldest():
                    break
            
            # Add new item
            self._cache[key] = value
            self._access_order.append(key)
            self._memory_usage += size_mb
            
            # Set up weak reference for automatic cleanup
            def cleanup_callback(ref):
                with self._lock:
                    if key in self._weak_refs and self._weak_refs[key] is ref:
                        self.remove(key)
            
            self._weak_refs[key] = weakref.ref(value, cleanup_callback)
    
    def remove(self, key: str) -> bool:
        """Remove item from cache."""
        if key in self._cache:
            del self._cache[key]
            self._access_order.remove(key)
            if key in self._weak_refs:
                del self._weak_refs[key]
            return True
        return False
    
    def _evict_oldest(self) -> bool:
        """Evict the oldest item from cache."""
        if not self._access_order:
            return False
        
        oldest_key = self._access_order.popleft()
        if oldest_key in self._cache:
            del self._cache[oldest_key]
            if oldest_key in self._weak_refs:
                del self._weak_refs[oldest_key]
        
        return True
    
    def _estimate_size(self, obj: Any) -> float:
        """Estimate object size in MB."""
        if isinstance(obj, np.ndarray):
            return obj.nbytes / (1024 * 1024)
        elif hasattr(obj, '__sizeof__'):
            return obj.__sizeof__() / (1024 * 1024)
        else:
            return 0.1  # Default estimate
    
    def clear(self):
        """Clear all cached items."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self._weak_refs.clear()
            self._memory_usage = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'memory_usage_mb': self._memory_usage,
            'max_memory_mb': self.max_memory_mb,
            'utilization_percent': (len(self._cache) / self.max_size) * 100
        }

class MemoryOptimizer:
    """
    Advanced memory optimization for WhisperLiveKit.
    
    Features:
    - Automatic garbage collection
    - Memory pressure monitoring
    - Object pooling
    - Buffer optimization
    """
    
    def __init__(self):
        self.memory_pools = MemoryPool()
        self.audio_buffers = {}
        self.gc_enabled = True
        self.last_gc_time = time.time()
        self.gc_interval = 10.0  # seconds
        self.memory_threshold_mb = 512  # MB
        
    def optimize_memory_usage(self):
        """Perform memory optimization tasks."""
        current_time = time.time()
        
        # Periodic garbage collection
        if (self.gc_enabled and 
            current_time - self.last_gc_time > self.gc_interval):
            
            collected = gc.collect()
            if collected > 0:
                logger.debug(f"Garbage collection freed {collected} objects")
            self.last_gc_time = current_time
        
        # Check memory pressure
        memory_usage = psutil.virtual_memory()
        if memory_usage.percent > 85.0:
            logger.warning(f"High memory usage: {memory_usage.percent:.1f}%")
            self._emergency_cleanup()
    
    def _emergency_cleanup(self):
        """Emergency memory cleanup when memory pressure is high."""
        logger.info("Performing emergency memory cleanup...")
        
        # Force garbage collection
        before = psutil.virtual_memory().used
        collected = gc.collect()
        after = psutil.virtual_memory().used
        freed_mb = (before - after) / (1024*1024)
        
        logger.info(f"Emergency cleanup: {collected} objects, {freed_mb:.1f}MB freed")
        
        # Clear old audio buffers
        self._cleanup_old_buffers()
    
    def _cleanup_old_buffers(self):
        """Clean up old audio buffers."""
        current_time = time.time()
        old_buffers = []
        
        for buffer_id, (buffer, timestamp) in self.audio_buffers.items():
            if current_time - timestamp > 300:  # 5 minutes old
                old_buffers.append(buffer_id)
        
        for buffer_id in old_buffers:
            del self.audio_buffers[buffer_id]
            
        if old_buffers:
            logger.debug(f"Cleaned up {len(old_buffers)} old audio buffers")
    
    def get_audio_buffer(self, buffer_id: str, size: int) -> CircularAudioBuffer:
        """Get or create an audio buffer."""
        if buffer_id not in self.audio_buffers:
            buffer = CircularAudioBuffer(initial_capacity=size)
            self.audio_buffers[buffer_id] = (buffer, time.time())
        else:
            buffer, _ = self.audio_buffers[buffer_id]
            # Update timestamp
            self.audio_buffers[buffer_id] = (buffer, time.time())
        
        return buffer
    
    def release_audio_buffer(self, buffer_id: str):
        """Release an audio buffer."""
        if buffer_id in self.audio_buffers:
            del self.audio_buffers[buffer_id]
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get comprehensive memory statistics."""
        memory = psutil.virtual_memory()
        
        buffer_stats = {
            'count': len(self.audio_buffers),
            'total_memory_mb': sum(buf.memory_usage_mb for buf, _ in self.audio_buffers.values())
        }
        
        return {
            'system_memory': {
                'total_mb': memory.total / (1024*1024),
                'available_mb': memory.available / (1024*1024),
                'used_mb': memory.used / (1024*1024),
                'percent': memory.percent
            },
            'audio_buffers': buffer_stats,
            'memory_pools': self.memory_pools.get_stats(),
            'gc_stats': {
                'collections': gc.get_count(),
                'threshold': gc.get_threshold()
            }
        }

# Global memory optimizer instance
memory_optimizer = MemoryOptimizer()