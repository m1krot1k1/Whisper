
import logging

logger = logging.getLogger(__name__)

def load_file(warmup_file=None, timeout=5):
    import os
    import tempfile
    import librosa
    
    # If warmup_file is explicitly set to False or "false", skip warmup
    if warmup_file is False or warmup_file == "false":
        logger.info("Warmup disabled by configuration")
        return None
    
    # If warmup_file is provided, try to use it
    if warmup_file and warmup_file != "false":
        # Try to use model paths manager to get warmup file
        if not os.path.isabs(warmup_file):
            try:
                from whisperlivekit.model_paths import get_model_paths_manager
                model_paths = get_model_paths_manager()
                
                # If it's just a filename, look in progrev directory
                if not os.path.dirname(warmup_file):
                    warmup_file = model_paths.get_warmup_file_path(warmup_file)
                else:
                    # It's a relative path, make it absolute relative to base models dir
                    warmup_file = str(model_paths.base_dir / warmup_file)
                    
                logger.debug(f"Using warmup file: {warmup_file}")
            except ImportError:
                logger.warning("Could not import model_paths, using warmup file as-is")
        
        if os.path.exists(warmup_file) and os.path.getsize(warmup_file) > 0:
            try:
                audio, sr = librosa.load(warmup_file, sr=16000)
                logger.info(f"Loaded warmup file: {warmup_file}")
                return audio
            except Exception as e:
                logger.warning(f"Failed to load warmup file {warmup_file}: {e}")
        else:
            logger.warning(f"Warmup file {warmup_file} not found or empty")
        
    if warmup_file is None:
        # Download JFK sample if not already present
        jfk_url = "https://github.com/ggerganov/whisper.cpp/raw/master/samples/jfk.wav"
        temp_dir = tempfile.gettempdir()
        warmup_file = os.path.join(temp_dir, "whisper_warmup_jfk.wav")
        
        if not os.path.exists(warmup_file):
            logger.debug(f"Downloading warmup file from {jfk_url}")
            print(f"Downloading warmup file from {jfk_url}")
            import time
            import urllib.request
            import urllib.error
            import socket
            
            original_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(timeout)
            
            start_time = time.time()
            try:
                urllib.request.urlretrieve(jfk_url, warmup_file)
                logger.debug(f"Download successful in {time.time() - start_time:.2f}s")
            except (urllib.error.URLError, socket.timeout) as e:
                logger.warning(f"Download failed: {e}. Proceeding without warmup.")
                return None
            finally:
                socket.setdefaulttimeout(original_timeout)
    elif not warmup_file:
        return None 
    
    if not warmup_file or not os.path.exists(warmup_file) or os.path.getsize(warmup_file) == 0:
        logger.warning(f"Warmup file {warmup_file} invalid or missing.")
        return None
    
    try:
        audio, sr = librosa.load(warmup_file, sr=16000)
    except Exception as e:
        logger.warning(f"Failed to load audio file: {e}")
        return None
    return audio

def warmup_asr(asr, warmup_file=None, timeout=5):
    """
    Warmup the ASR model by transcribing a short audio file.
    """
    audio = load_file(warmup_file, timeout)
    if audio is not None:
        asr.transcribe(audio)
        logger.info("ASR model is warmed up")
    else:
        logger.warning("Skipping ASR warmup due to missing audio file")
    
def warmup_online(online, warmup_file=None, timeout=5):
    audio = load_file(warmup_file, timeout)
    if audio is not None:
        online.warmup(audio)
        logger.info("Online ASR is warmed up")
    else:
        logger.warning("Skipping online ASR warmup due to missing audio file")