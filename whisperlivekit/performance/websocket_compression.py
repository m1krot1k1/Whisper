"""
WebSocket compression and optimization for WhisperLiveKit.

This module provides:
- Message compression for reduced bandwidth
- Binary encoding optimizations
- Message batching and aggregation
- Adaptive compression based on connection quality
"""

import asyncio
import json
import logging
import time
import zlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union, Callable
from enum import Enum
import struct

logger = logging.getLogger(__name__)

class CompressionLevel(Enum):
    """Compression levels for different use cases."""
    NONE = 0        # No compression
    FAST = 1        # Fast compression (zlib level 1)
    BALANCED = 6    # Balanced (zlib level 6)
    BEST = 9        # Best compression (zlib level 9)

class MessageType(Enum):
    """WebSocket message types."""
    TRANSCRIPTION_RESULT = 1
    AUDIO_DATA = 2
    STATUS_UPDATE = 3
    ERROR_MESSAGE = 4
    HEARTBEAT = 5
    BATCH_UPDATE = 6

@dataclass
class CompressionStats:
    """Statistics for compression performance."""
    total_messages: int = 0
    compressed_messages: int = 0
    original_bytes: int = 0
    compressed_bytes: int = 0
    compression_time_ms: float = 0
    decompression_time_ms: float = 0
    
    @property
    def compression_ratio(self) -> float:
        """Get compression ratio (compressed/original)."""
        return self.compressed_bytes / max(1, self.original_bytes)
    
    @property
    def space_saved_percent(self) -> float:
        """Get percentage of space saved."""
        return (1 - self.compression_ratio) * 100

class AdaptiveCompressor:
    """
    Adaptive compression that adjusts based on message characteristics and performance.
    
    Features:
    - Automatic compression level adjustment
    - Message type-specific compression
    - Performance monitoring
    - Threshold-based compression decisions
    """
    
    def __init__(self, 
                 min_compress_size: int = 100,
                 compression_threshold_ratio: float = 0.8,
                 performance_window: int = 100):
        
        self.min_compress_size = min_compress_size
        self.compression_threshold_ratio = compression_threshold_ratio
        self.performance_window = performance_window
        
        # Compression levels per message type
        self._compression_levels = {
            MessageType.TRANSCRIPTION_RESULT: CompressionLevel.BALANCED,
            MessageType.AUDIO_DATA: CompressionLevel.FAST,
            MessageType.STATUS_UPDATE: CompressionLevel.FAST,
            MessageType.ERROR_MESSAGE: CompressionLevel.NONE,
            MessageType.HEARTBEAT: CompressionLevel.NONE,
            MessageType.BATCH_UPDATE: CompressionLevel.BEST
        }
        
        # Statistics
        self.stats = CompressionStats()
        self._recent_ratios: List[float] = []
        
        # Adaptive settings
        self._auto_adjust = True
        self._last_adjustment = time.time()
        self._adjustment_interval = 30.0  # 30 seconds
        
    def compress_message(self, 
                        message: Dict[str, Any], 
                        message_type: MessageType = MessageType.TRANSCRIPTION_RESULT) -> bytes:
        """
        Compress a message for WebSocket transmission.
        
        Args:
            message: Message to compress
            message_type: Type of message for optimal compression
            
        Returns:
            Compressed message bytes
        """
        start_time = time.time()
        
        # Serialize message
        json_data = json.dumps(message, ensure_ascii=False, separators=(',', ':'))
        original_bytes = json_data.encode('utf-8')
        original_size = len(original_bytes)
        
        self.stats.total_messages += 1
        self.stats.original_bytes += original_size
        
        # Check if compression is beneficial
        if original_size < self.min_compress_size:
            # Create uncompressed packet
            packet = self._create_packet(MessageType.TRANSCRIPTION_RESULT, original_bytes, compressed=False)
            return packet
        
        # Get compression level for message type
        compression_level = self._compression_levels.get(message_type, CompressionLevel.BALANCED)
        
        if compression_level == CompressionLevel.NONE:
            packet = self._create_packet(message_type, original_bytes, compressed=False)
            return packet
        
        # Compress data
        try:
            compressed_data = zlib.compress(original_bytes, compression_level.value)
            compressed_size = len(compressed_data)
            
            # Check compression effectiveness
            compression_ratio = compressed_size / original_size
            if compression_ratio > self.compression_threshold_ratio:
                # Compression not effective, send uncompressed
                packet = self._create_packet(message_type, original_bytes, compressed=False)
                return packet
            
            # Create compressed packet
            packet = self._create_packet(message_type, compressed_data, compressed=True)
            
            # Update statistics
            self.stats.compressed_messages += 1
            self.stats.compressed_bytes += len(packet)
            self.stats.compression_time_ms += (time.time() - start_time) * 1000
            
            # Track compression ratios for adaptive adjustment
            self._recent_ratios.append(compression_ratio)
            if len(self._recent_ratios) > self.performance_window:
                self._recent_ratios.pop(0)
            
            # Adaptive adjustment
            if self._auto_adjust:
                self._maybe_adjust_compression()
            
            return packet
            
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            # Fall back to uncompressed
            packet = self._create_packet(message_type, original_bytes, compressed=False)
            return packet
    
    def decompress_message(self, packet: bytes) -> Dict[str, Any]:
        """
        Decompress a message packet.
        
        Args:
            packet: Compressed packet bytes
            
        Returns:
            Decompressed message dictionary
        """
        start_time = time.time()
        
        try:
            # Parse packet header
            message_type, is_compressed, data = self._parse_packet(packet)
            
            if is_compressed:
                # Decompress data
                decompressed_data = zlib.decompress(data)
                self.stats.decompression_time_ms += (time.time() - start_time) * 1000
            else:
                decompressed_data = data
            
            # Deserialize JSON
            json_str = decompressed_data.decode('utf-8')
            message = json.loads(json_str)
            
            return message
            
        except Exception as e:
            logger.error(f"Decompression failed: {e}")
            raise
    
    def _create_packet(self, 
                      message_type: MessageType, 
                      data: bytes, 
                      compressed: bool) -> bytes:
        """
        Create a message packet with header.
        
        Packet format:
        - 1 byte: Message type
        - 1 byte: Flags (bit 0: compressed)
        - 4 bytes: Data length (big-endian)
        - N bytes: Data
        """
        header = struct.pack('>BB I', 
                           message_type.value,
                           1 if compressed else 0,
                           len(data))
        return header + data
    
    def _parse_packet(self, packet: bytes) -> tuple[MessageType, bool, bytes]:
        """Parse a message packet."""
        if len(packet) < 6:
            raise ValueError("Invalid packet: too short")
        
        msg_type_value, flags, data_length = struct.unpack('>BB I', packet[:6])
        
        try:
            message_type = MessageType(msg_type_value)
        except ValueError:
            message_type = MessageType.TRANSCRIPTION_RESULT
        
        is_compressed = bool(flags & 1)
        data = packet[6:6+data_length]
        
        if len(data) != data_length:
            raise ValueError(f"Invalid packet: expected {data_length} bytes, got {len(data)}")
        
        return message_type, is_compressed, data
    
    def _maybe_adjust_compression(self):
        """Automatically adjust compression levels based on performance."""
        current_time = time.time()
        if current_time - self._last_adjustment < self._adjustment_interval:
            return
        
        if len(self._recent_ratios) < 10:
            return
        
        avg_ratio = sum(self._recent_ratios) / len(self._recent_ratios)
        
        # If compression ratio is poor, reduce compression level
        if avg_ratio > 0.9:
            self._reduce_compression_levels()
            logger.debug("Reduced compression levels due to poor compression ratio")
        elif avg_ratio < 0.3:
            self._increase_compression_levels()
            logger.debug("Increased compression levels due to excellent compression ratio")
        
        self._last_adjustment = current_time
    
    def _reduce_compression_levels(self):
        """Reduce compression levels for better performance."""
        for msg_type in self._compression_levels:
            current = self._compression_levels[msg_type]
            if current == CompressionLevel.BEST:
                self._compression_levels[msg_type] = CompressionLevel.BALANCED
            elif current == CompressionLevel.BALANCED:
                self._compression_levels[msg_type] = CompressionLevel.FAST
    
    def _increase_compression_levels(self):
        """Increase compression levels for better compression."""
        for msg_type in self._compression_levels:
            current = self._compression_levels[msg_type]
            if current == CompressionLevel.FAST:
                self._compression_levels[msg_type] = CompressionLevel.BALANCED
            elif current == CompressionLevel.BALANCED:
                self._compression_levels[msg_type] = CompressionLevel.BEST
    
    def get_stats(self) -> Dict[str, Any]:
        """Get compression statistics."""
        return {
            'total_messages': self.stats.total_messages,
            'compressed_messages': self.stats.compressed_messages,
            'compression_rate': (self.stats.compressed_messages / max(1, self.stats.total_messages)) * 100,
            'original_bytes': self.stats.original_bytes,
            'compressed_bytes': self.stats.compressed_bytes,
            'compression_ratio': self.stats.compression_ratio,
            'space_saved_percent': self.stats.space_saved_percent,
            'avg_compression_time_ms': self.stats.compression_time_ms / max(1, self.stats.compressed_messages),
            'avg_decompression_time_ms': self.stats.decompression_time_ms / max(1, self.stats.compressed_messages),
            'compression_levels': {mt.name: cl.name for mt, cl in self._compression_levels.items()}
        }

class MessageBatcher:
    """
    Batch multiple small messages to reduce WebSocket overhead.
    
    Features:
    - Automatic batching based on size and time
    - Priority-based message handling
    - Configurable batch parameters
    """
    
    def __init__(self, 
                 max_batch_size: int = 10,
                 max_batch_bytes: int = 8192,
                 batch_timeout_ms: float = 50):
        
        self.max_batch_size = max_batch_size
        self.max_batch_bytes = max_batch_bytes
        self.batch_timeout_ms = batch_timeout_ms / 1000  # Convert to seconds
        
        self._batch_queue: List[Dict[str, Any]] = []
        self._batch_size_bytes = 0
        self._batch_timer: Optional[asyncio.TimerHandle] = None
        self._batch_lock = asyncio.Lock()
        self._flush_callback: Optional[Callable] = None
        
    def set_flush_callback(self, callback: Callable):
        """Set callback function for when batch is ready to send."""
        self._flush_callback = callback
    
    async def add_message(self, message: Dict[str, Any]) -> bool:
        """
        Add message to batch.
        
        Args:
            message: Message to add to batch
            
        Returns:
            True if message was added, False if batch is full
        """
        async with self._batch_lock:
            # Estimate message size
            msg_size = len(json.dumps(message, separators=(',', ':')))
            
            # Check if adding this message would exceed limits
            if (len(self._batch_queue) >= self.max_batch_size or
                self._batch_size_bytes + msg_size > self.max_batch_bytes):
                # Flush current batch first
                await self._flush_batch()
            
            # Add message to batch
            self._batch_queue.append(message)
            self._batch_size_bytes += msg_size
            
            # Set timer for automatic flush if this is the first message
            if len(self._batch_queue) == 1:
                self._set_batch_timer()
            
            return True
    
    async def flush_now(self):
        """Force immediate flush of current batch."""
        async with self._batch_lock:
            await self._flush_batch()
    
    async def _flush_batch(self):
        """Internal batch flush."""
        if not self._batch_queue:
            return
        
        # Cancel timer
        if self._batch_timer:
            self._batch_timer.cancel()
            self._batch_timer = None
        
        # Create batch message
        batch_message = {
            'type': 'batch',
            'messages': self._batch_queue.copy(),
            'count': len(self._batch_queue),
            'timestamp': time.time()
        }
        
        # Clear batch
        self._batch_queue.clear()
        self._batch_size_bytes = 0
        
        # Send via callback
        if self._flush_callback:
            try:
                await self._flush_callback(batch_message)
            except Exception as e:
                logger.error(f"Batch flush callback failed: {e}")
    
    def _set_batch_timer(self):
        """Set timer for automatic batch flush."""
        if self._batch_timer:
            self._batch_timer.cancel()
        
        loop = asyncio.get_event_loop()
        self._batch_timer = loop.call_later(
            self.batch_timeout_ms,
            lambda: asyncio.create_task(self._flush_batch())
        )

class OptimizedWebSocketHandler:
    """
    Optimized WebSocket handler with compression and batching.
    
    Features:
    - Automatic message compression
    - Message batching for small messages
    - Performance monitoring
    - Adaptive optimization
    """
    
    def __init__(self, websocket, enable_compression: bool = True, enable_batching: bool = True):
        self.websocket = websocket
        self.enable_compression = enable_compression
        self.enable_batching = enable_batching
        
        # Components
        self.compressor = AdaptiveCompressor() if enable_compression else None
        self.batcher = MessageBatcher() if enable_batching else None
        
        if self.batcher:
            self.batcher.set_flush_callback(self._send_compressed_message)
        
        # Statistics
        self._messages_sent = 0
        self._bytes_sent = 0
        self._start_time = time.time()
    
    async def send_message(self, message: Dict[str, Any], 
                          message_type: MessageType = MessageType.TRANSCRIPTION_RESULT,
                          force_immediate: bool = False):
        """
        Send a message through the optimized pipeline.
        
        Args:
            message: Message to send
            message_type: Type of message
            force_immediate: Skip batching and send immediately
        """
        # For critical messages or when batching is disabled, send immediately
        if force_immediate or not self.enable_batching or message_type in [MessageType.ERROR_MESSAGE, MessageType.HEARTBEAT]:
            await self._send_compressed_message(message, message_type)
        else:
            # Add to batch
            await self.batcher.add_message(message)
    
    async def _send_compressed_message(self, message: Dict[str, Any], 
                                     message_type: MessageType = MessageType.TRANSCRIPTION_RESULT):
        """Send a message with optional compression."""
        try:
            if self.enable_compression and self.compressor:
                # Compress message
                packet = self.compressor.compress_message(message, message_type)
                await self.websocket.send_bytes(packet)
            else:
                # Send as JSON
                json_data = json.dumps(message, ensure_ascii=False)
                await self.websocket.send_text(json_data)
            
            self._messages_sent += 1
            self._bytes_sent += len(json.dumps(message, separators=(',', ':')))
            
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
            raise
    
    async def close(self):
        """Clean up resources."""
        if self.batcher:
            await self.batcher.flush_now()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics."""
        uptime = time.time() - self._start_time
        
        stats = {
            'messages_sent': self._messages_sent,
            'bytes_sent': self._bytes_sent,
            'uptime_seconds': uptime,
            'messages_per_second': self._messages_sent / max(1, uptime),
            'bytes_per_second': self._bytes_sent / max(1, uptime)
        }
        
        if self.compressor:
            stats['compression'] = self.compressor.get_stats()
        
        return stats

# Global instances for reuse
default_compressor = AdaptiveCompressor()

# Utility functions
async def compress_websocket_message(message: Dict[str, Any], 
                                   message_type: MessageType = MessageType.TRANSCRIPTION_RESULT) -> bytes:
    """Utility function to compress a single WebSocket message."""
    return default_compressor.compress_message(message, message_type)

async def decompress_websocket_message(packet: bytes) -> Dict[str, Any]:
    """Utility function to decompress a WebSocket message packet."""
    return default_compressor.decompress_message(packet)