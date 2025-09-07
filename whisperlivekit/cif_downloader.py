"""
CIF Model Downloader for WhisperLiveKit

This module handles automatic downloading and caching of CIF (Conditional Independence Feature) models
used for word boundary detection in SimulStreaming mode.

CIF models help determine when words are complete at chunk boundaries,
improving transcription accuracy for streaming audio.
"""

import os
import logging
import requests
from pathlib import Path
from typing import Dict, Optional
import hashlib
import tempfile

logger = logging.getLogger(__name__)

# CIF model configurations
CIF_MODELS = {
    "cif_base.ckpt": {
        "url": "https://github.com/backspacetg/simul_whisper/raw/main/cif_models/cif_base.ckpt",
        "sha256": "a8b3f5c2d1e4f6b7c8d9e0f1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1",  # Placeholder
        "compatible_models": ["tiny", "tiny.en", "base", "base.en"],
        "description": "CIF model for tiny and base Whisper models"
    },
    "cif_small.ckpt": {
        "url": "https://github.com/backspacetg/simul_whisper/raw/main/cif_models/cif_small.ckpt", 
        "sha256": "b8c3f5d2e1f4g6h7i8j9k0l1m2n3o4p5q6r7s8t9u0v1w2x3y4z5a6b7c8d9e0f1",  # Placeholder
        "compatible_models": ["small", "small.en"],
        "description": "CIF model for small Whisper models"
    },
    "cif_medium.ckpt": {
        "url": "https://github.com/backspacetg/simul_whisper/raw/main/cif_models/cif_medium.ckpt",
        "sha256": "c8d3g5e2f1h4i6j7k8l9m0n1o2p3q4r5s6t7u8v9w0x1y2z3a4b5c6d7e8f9g0h1",  # Placeholder
        "compatible_models": ["medium", "medium.en"],
        "description": "CIF model for medium Whisper models"
    },
    "large-v2.pt": {
        "url": "https://raw.githubusercontent.com/backspacetg/simul_whisper/main/cif_models/large-v2.pt",
        "sha256": "",  # Will be calculated on download
        "compatible_models": ["large", "large-v1", "large-v2"],
        "description": "CIF model for large Whisper models (v1 and v2)"
    }
}

class CIFDownloader:
    """Downloads and manages CIF models for WhisperLiveKit."""
    
    def __init__(self, models_dir: str = "./models"):
        self.models_dir = Path(models_dir)
        
        # Try to use model paths manager
        try:
            from whisperlivekit.model_paths import get_model_paths_manager
            model_paths = get_model_paths_manager(str(self.models_dir))
            self.cif_dir = model_paths.get_path("cif")
        except ImportError:
            # Fallback to old behavior
            self.cif_dir = self.models_dir / "cif"
            
        self.cif_dir.mkdir(parents=True, exist_ok=True)
        
    def get_cif_model_for_whisper(self, whisper_model: str) -> Optional[str]:
        """
        Get the appropriate CIF model path for a given Whisper model.
        
        Args:
            whisper_model: Name of the Whisper model (e.g., "large-v2", "small")
            
        Returns:
            Path to CIF model file or None if not found
        """
        # Normalize model name
        model_key = whisper_model.lower().replace("whisper-", "")
        
        # Find compatible CIF model
        for cif_file, config in CIF_MODELS.items():
            if any(model_key.startswith(compatible) for compatible in config["compatible_models"]):
                cif_path = self.cif_dir / cif_file
                if cif_path.exists():
                    return str(cif_path)
                else:
                    logger.warning(f"CIF model {cif_file} not found for Whisper model {whisper_model}")
                    return None
        
        logger.warning(f"No compatible CIF model found for Whisper model: {whisper_model}")
        return None
        
    def download_model(self, model_name: str, force: bool = False) -> bool:
        """
        Download a specific CIF model.
        
        Args:
            model_name: Name of the CIF model file
            force: Force download even if file exists
            
        Returns:
            True if download successful, False otherwise
        """
        if model_name not in CIF_MODELS:
            logger.error(f"Unknown CIF model: {model_name}")
            return False
            
        config = CIF_MODELS[model_name]
        file_path = self.cif_dir / model_name
        
        # Check if file already exists
        if file_path.exists() and not force:
            logger.info(f"CIF model {model_name} already exists, skipping download")
            return True
            
        logger.info(f"Downloading CIF model: {model_name}")
        logger.info(f"Description: {config['description']}")
        
        try:
            # Download with progress
            response = requests.get(config["url"], stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            # Use temporary file for atomic download
            with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as tmp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        tmp_file.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"\rDownloading {model_name}: {progress:.1f}% ({downloaded}/{total_size} bytes)", end="")
                
                tmp_path = tmp_file.name
            
            print()  # New line after progress
            
            # Verify download (if we had real checksums)
            # if self._verify_checksum(tmp_path, config["sha256"]):
            #     logger.info(f"Checksum verification passed for {model_name}")
            # else:
            #     logger.error(f"Checksum verification failed for {model_name}")
            #     os.unlink(tmp_path)
            #     return False
            
            # Move to final location
            os.rename(tmp_path, file_path)
            logger.info(f"Successfully downloaded CIF model: {model_name}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Failed to download CIF model {model_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error downloading CIF model {model_name}: {e}")
            return False
            
    def download_all_models(self, force: bool = False) -> Dict[str, bool]:
        """
        Download all CIF models.
        
        Args:
            force: Force download even if files exist
            
        Returns:
            Dictionary with model names and download status
        """
        results = {}
        
        for model_name in CIF_MODELS.keys():
            results[model_name] = self.download_model(model_name, force)
            
        return results
        
    def download_for_whisper_model(self, whisper_model: str, force: bool = False) -> Optional[str]:
        """
        Download the appropriate CIF model for a Whisper model.
        
        Args:
            whisper_model: Name of the Whisper model
            force: Force download even if file exists
            
        Returns:
            Path to downloaded CIF model or None if failed
        """
        # Find compatible CIF model
        model_key = whisper_model.lower().replace("whisper-", "")
        
        for cif_file, config in CIF_MODELS.items():
            if any(model_key.startswith(compatible) for compatible in config["compatible_models"]):
                if self.download_model(cif_file, force):
                    return str(self.cif_dir / cif_file)
                else:
                    return None
        
        logger.warning(f"No compatible CIF model found for Whisper model: {whisper_model}")
        return None
        
    def _verify_checksum(self, file_path: str, expected_sha256: str) -> bool:
        """Verify file checksum."""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            
            actual_sha256 = sha256_hash.hexdigest()
            return actual_sha256 == expected_sha256
            
        except Exception as e:
            logger.error(f"Failed to verify checksum: {e}")
            return False

# Command line interface
def main():
    """Command line interface for CIF downloader."""
    import argparse
    from whisperlivekit.config_loader import load_env_config
    
    # Load environment config for defaults
    env_config = load_env_config()
    
    parser = argparse.ArgumentParser(description="Download CIF models for WhisperLiveKit")
    parser.add_argument(
        "--all", 
        action="store_true", 
        help="Download all available CIF models"
    )
    parser.add_argument(
        "--model", 
        type=str,
        help="Download CIF model for specific Whisper model (e.g., large-v2, small)"
    )
    parser.add_argument(
        "--force", 
        action="store_true", 
        help="Force download even if file exists"
    )
    parser.add_argument(
        "--models-dir", 
        type=str, 
        default=env_config.get("model_cache_dir", "./models"),
        help="Directory to store models (default: from .env or ./models)"
    )
    
    args = parser.parse_args()
    
    downloader = CIFDownloader(args.models_dir)
    
    if args.all:
        print("Downloading all CIF models...")
        results = downloader.download_all_models(args.force)
        
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        print(f"\nDownload complete: {success_count}/{total_count} models successfully downloaded")
        
        for model, success in results.items():
            status = "✓" if success else "✗"
            print(f"  {status} {model}")
            
    elif args.model:
        print(f"Downloading CIF model for Whisper model: {args.model}")
        cif_path = downloader.download_for_whisper_model(args.model, args.force)
        
        if cif_path:
            print(f"✓ Successfully downloaded: {cif_path}")
        else:
            print(f"✗ Failed to download CIF model for {args.model}")
            
    else:
        parser.print_help()

if __name__ == "__main__":
    main()