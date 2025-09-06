"""
Model Paths Manager for WhisperLiveKit

This module manages download paths for different types of models,
ensuring they are organized in separate folders within the models directory.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class ModelPathsManager:
    """Manages model download paths and directories."""
    
    def __init__(self, base_models_dir: str = "./models"):
        """
        Initialize the model paths manager.
        
        Args:
            base_models_dir: Base directory for all models
        """
        self.base_dir = Path(base_models_dir).resolve()
        
        # Model type subdirectories
        self.paths = {
            "whisper": self.base_dir / "whisper",
            "faster_whisper": self.base_dir / "faster-whisper",
            "huggingface": self.base_dir / "huggingface",
            "silero_vad": self.base_dir / "silero_vad",
            "cif": self.base_dir / "cif",
            "progrev": self.base_dir / "progrev",
            "mlx_whisper": self.base_dir / "mlx-whisper",
            "nemo": self.base_dir / "nemo",
        }
        
        # Create directories if they don't exist
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create model directories if they don't exist."""
        for model_type, path in self.paths.items():
            try:
                path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Ensured directory exists: {path}")
            except Exception as e:
                logger.warning(f"Failed to create directory {path}: {e}")
    
    def get_path(self, model_type: str) -> Path:
        """
        Get the path for a specific model type.
        
        Args:
            model_type: Type of model (whisper, faster_whisper, etc.)
            
        Returns:
            Path object for the model type directory
            
        Raises:
            ValueError: If model_type is not supported
        """
        if model_type not in self.paths:
            raise ValueError(f"Unsupported model type: {model_type}. "
                           f"Supported types: {list(self.paths.keys())}")
        
        return self.paths[model_type]
    
    def get_whisper_cache_dir(self) -> str:
        """Get cache directory for OpenAI Whisper models."""
        return str(self.paths["whisper"])
    
    def get_faster_whisper_cache_dir(self) -> str:
        """Get cache directory for Faster-Whisper models."""
        return str(self.paths["faster_whisper"])
    
    def get_huggingface_cache_dir(self) -> str:
        """Get cache directory for HuggingFace models."""
        return str(self.paths["huggingface"])
    
    def get_silero_vad_cache_dir(self) -> str:
        """Get cache directory for Silero VAD models."""
        return str(self.paths["silero_vad"])
    
    def get_cif_cache_dir(self) -> str:
        """Get cache directory for CIF models."""
        return str(self.paths["cif"])
    
    def get_warmup_file_path(self, filename: str = "progrev.mp3") -> str:
        """
        Get path to warmup audio file.
        
        Args:
            filename: Name of the warmup file
            
        Returns:
            Full path to the warmup file
        """
        return str(self.paths["progrev"] / filename)
    
    def setup_environment_variables(self):
        """
        Set up environment variables for various model caches.
        This ensures models are downloaded to the correct locations.
        """
        # HuggingFace cache
        os.environ["HF_HOME"] = str(self.paths["huggingface"])
        os.environ["HUGGINGFACE_HUB_CACHE"] = str(self.paths["huggingface"])
        
        # Torch hub cache (for Silero VAD and NeMo models)
        os.environ["TORCH_HOME"] = str(self.paths["nemo"])
        
        logger.info(f"Set up environment variables for model caches:")
        logger.info(f"  HF_HOME: {os.environ.get('HF_HOME')}")
        logger.info(f"  HUGGINGFACE_HUB_CACHE: {os.environ.get('HUGGINGFACE_HUB_CACHE')}")
        logger.info(f"  TORCH_HOME: {os.environ.get('TORCH_HOME')}")
    
    def get_backend_specific_cache_dir(self, backend: str) -> str:
        """
        Get cache directory based on the backend type.
        
        Args:
            backend: Backend name (faster-whisper, simulstreaming, etc.)
            
        Returns:
            Appropriate cache directory path
        """
        backend_mapping = {
            "faster-whisper": self.get_faster_whisper_cache_dir(),
            "simulstreaming": self.get_whisper_cache_dir(),
            "whisper_timestamped": self.get_whisper_cache_dir(),
            "mlx-whisper": str(self.paths["mlx_whisper"]),
            "openai-api": "",  # No local cache needed for API
        }
        
        return backend_mapping.get(backend, self.get_whisper_cache_dir())
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about model directories and their contents.
        
        Returns:
            Dictionary with model directory information
        """
        info = {}
        
        for model_type, path in self.paths.items():
            if path.exists():
                try:
                    files = [f.name for f in path.iterdir() if f.is_file() and not f.name.startswith('.')]
                    dirs = [d.name for d in path.iterdir() if d.is_dir()]
                    
                    info[model_type] = {
                        "path": str(path),
                        "exists": True,
                        "files": files,
                        "directories": dirs,
                        "total_files": len(files),
                        "total_dirs": len(dirs)
                    }
                except Exception as e:
                    info[model_type] = {
                        "path": str(path),
                        "exists": True,
                        "error": str(e)
                    }
            else:
                info[model_type] = {
                    "path": str(path),
                    "exists": False
                }
        
        return info
    
    def cleanup_empty_dirs(self):
        """Remove empty model directories (except .gitkeep files)."""
        for model_type, path in self.paths.items():
            if path.exists():
                try:
                    files = [f for f in path.iterdir() if f.is_file() and not f.name.startswith('.git')]
                    dirs = [d for d in path.iterdir() if d.is_dir()]
                    
                    if not files and not dirs:
                        # Only .gitkeep files remain
                        logger.info(f"Directory {path} is empty (only .gitkeep files)")
                except Exception as e:
                    logger.warning(f"Error checking directory {path}: {e}")


# Global instance
_model_paths_manager = None

def get_model_paths_manager(base_models_dir: str = "./models") -> ModelPathsManager:
    """
    Get the global ModelPathsManager instance.
    
    Args:
        base_models_dir: Base directory for models (only used for first call)
        
    Returns:
        ModelPathsManager instance
    """
    global _model_paths_manager
    
    if _model_paths_manager is None:
        _model_paths_manager = ModelPathsManager(base_models_dir)
        _model_paths_manager.setup_environment_variables()
    
    return _model_paths_manager
