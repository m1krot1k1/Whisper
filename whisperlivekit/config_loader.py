"""
Configuration Loader for WhisperLiveKit

Loads configuration from .env files and provides type-safe defaults.
Ensures single source of truth for all configuration settings.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Union, Optional

logger = logging.getLogger(__name__)

def str_to_bool(value: Union[str, bool]) -> bool:
    """Convert string to boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on')
    return False

def str_to_int(value: Union[str, int], default: int = 0) -> int:
    """Convert string to integer with fallback."""
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def str_to_float(value: Union[str, float], default: float = 0.0) -> float:
    """Convert string to float with fallback."""
    if isinstance(value, float):
        return value
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def load_env_config(env_file: str = ".env.clone") -> Dict[str, Any]:
    """
    Load configuration from .env file with proper type conversion.
    
    Args:
        env_file: Path to env file (default: .env.clone)
        
    Returns:
        Dictionary with typed configuration values
    """
    config = {}
    env_path = Path(env_file)
    
    if not env_path.exists():
        logger.warning(f"Environment file {env_file} not found, using minimal defaults")
        return get_minimal_defaults()
    
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                if '=' not in line:
                    continue
                    
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                
                # Convert environment variable names to config keys
                config_key = env_key_to_config_key(key)
                if config_key:
                    config[config_key] = value
                    
    except Exception as e:
        logger.error(f"Error reading {env_file}: {e}")
        return get_minimal_defaults()
    
    return apply_type_conversions(config)

def env_key_to_config_key(env_key: str) -> Optional[str]:
    """Convert environment variable name to configuration key."""
    mapping = {
        'WLK_HOST': 'host',
        'WLK_PORT': 'port',
        'WLK_WARMUP_FILE': 'warmup_file',
        'WLK_DIARIZATION': 'diarization',
        'WLK_PUNCTUATION_SPLIT': 'punctuation_split',
        'WLK_MIN_CHUNK_SIZE': 'min_chunk_size',
        'WLK_MODEL': 'model',
        'WLK_MODEL_CACHE_DIR': 'model_cache_dir',
        'WLK_MODEL_DIR': 'model_dir',
        'WLK_LANGUAGE': 'lan',
        'WLK_TASK': 'task',
        'WLK_BACKEND': 'backend',
        'WLK_VAC': 'vac',
        'WLK_VAC_CHUNK_SIZE': 'vac_chunk_size',
        'WLK_LOG_LEVEL': 'log_level',
        'WLK_SSL_CERTFILE': 'ssl_certfile',
        'WLK_SSL_KEYFILE': 'ssl_keyfile',
        'WLK_TRANSCRIPTION': 'transcription',
        'WLK_VAD': 'vad',
        'WLK_BUFFER_TRIMMING': 'buffer_trimming',
        'WLK_CONFIDENCE_VALIDATION': 'confidence_validation',
        'WLK_BUFFER_TRIMMING_SEC': 'buffer_trimming_sec',
        'WLK_DISABLE_FAST_ENCODER': 'disable_fast_encoder',
        'WLK_FRAME_THRESHOLD': 'frame_threshold',
        'WLK_BEAMS': 'beams',
        'WLK_DECODER_TYPE': 'decoder_type',
        'WLK_AUDIO_MAX_LEN': 'audio_max_len',
        'WLK_AUDIO_MIN_LEN': 'audio_min_len',
        'WLK_CIF_CKPT_PATH': 'cif_ckpt_path',
        'WLK_NEVER_FIRE': 'never_fire',
        'WLK_INIT_PROMPT': 'init_prompt',
        'WLK_STATIC_INIT_PROMPT': 'static_init_prompt',
        'WLK_MAX_CONTEXT_TOKENS': 'max_context_tokens',
        'WLK_MODEL_PATH': 'model_path',
        'WLK_DIARIZATION_BACKEND': 'diarization_backend',
        'WLK_SEGMENTATION_MODEL': 'segmentation_model',
        'WLK_EMBEDDING_MODEL': 'embedding_model',
    }
    return mapping.get(env_key)

def apply_type_conversions(config: Dict[str, str]) -> Dict[str, Any]:
    """Apply proper type conversions to configuration values."""
    conversions = {
        # Network settings
        'port': lambda x: str_to_int(x, 8000),
        
        # Boolean settings
        'diarization': str_to_bool,
        'punctuation_split': str_to_bool,
        'vac': str_to_bool,
        'transcription': str_to_bool,
        'vad': str_to_bool,
        'confidence_validation': str_to_bool,
        'disable_fast_encoder': str_to_bool,
        'never_fire': str_to_bool,
        
        # Float settings
        'min_chunk_size': lambda x: str_to_float(x, 0.5),
        'vac_chunk_size': lambda x: str_to_float(x, 0.04),
        'audio_max_len': lambda x: str_to_float(x, 20.0),
        'audio_min_len': lambda x: str_to_float(x, 0.0),
        
        # Integer settings
        'buffer_trimming_sec': lambda x: str_to_int(x, 15),
        'frame_threshold': lambda x: str_to_int(x, 25),
        'beams': lambda x: str_to_int(x, 1),
        'max_context_tokens': lambda x: str_to_int(x, 0) if x else None,
    }
    
    typed_config = {}
    for key, value in config.items():
        if key in conversions:
            typed_config[key] = conversions[key](value)
        else:
            # Handle None values
            if value.lower() in ('none', 'null', ''):
                typed_config[key] = None
            else:
                typed_config[key] = value
    
    return typed_config

def get_minimal_defaults() -> Dict[str, Any]:
    """
    Get minimal required defaults when no .env file is found.
    These are the absolute minimum required for the system to start.
    """
    return {
        "host": "localhost",
        "port": 8000,
        "model": "tiny",
        "backend": "faster-whisper",
        "model_cache_dir": "./models",
        "lan": "auto",
        "task": "transcribe",
        "log_level": "DEBUG",
        "vac": True,
        "vad": True,
        "transcription": True,
        "diarization": False,
        "punctuation_split": False,
        "min_chunk_size": 0.5,
        "vac_chunk_size": 0.04,
        "buffer_trimming": "segment",
        "confidence_validation": False,
        "buffer_trimming_sec": 15,
        "disable_fast_encoder": False,
        "frame_threshold": 25,
        "beams": 1,
        "audio_max_len": 20.0,
        "audio_min_len": 0.0,
        "never_fire": False,
        "diarization_backend": "sortformer",
        "segmentation_model": "pyannote/segmentation-3.0",
        "embedding_model": "pyannote/embedding",
    }

def get_configuration(**kwargs) -> Dict[str, Any]:
    """
    Get final configuration by merging .env config with runtime kwargs.
    
    Priority (highest to lowest):
    1. Runtime kwargs
    2. .env.clone file values  
    3. Minimal defaults
    
    Args:
        **kwargs: Runtime configuration overrides
        
    Returns:
        Final configuration dictionary
    """
    # Start with minimal defaults
    config = get_minimal_defaults()
    
    # Load from .env.clone if available
    env_config = load_env_config()
    config.update(env_config)
    
    # Apply runtime overrides
    config.update(kwargs)
    
    logger.debug(f"Final configuration loaded with {len(config)} settings")
    logger.debug(f"Using backend: {config.get('backend')}, model: {config.get('model')}")
    
    return config
