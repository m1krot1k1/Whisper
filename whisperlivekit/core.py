try:
    from whisperlivekit.whisper_streaming_custom.whisper_online import backend_factory
    from whisperlivekit.whisper_streaming_custom.online_asr import OnlineASRProcessor
except ImportError:
    from .whisper_streaming_custom.whisper_online import backend_factory
    from .whisper_streaming_custom.online_asr import OnlineASRProcessor
from whisperlivekit.warmup import warmup_asr, warmup_online
from whisperlivekit.model_paths import get_model_paths_manager
from whisperlivekit.config_loader import get_configuration
from argparse import Namespace
from typing import Optional, Union, Tuple
import sys

class TranscriptionEngine:
    _instance = None
    _initialized = False
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, **kwargs):
        if TranscriptionEngine._initialized:
            return

        # Initialize model paths manager first
        self.model_paths = get_model_paths_manager(kwargs.get('model_cache_dir', './models'))

        # Load configuration from .env.clone and merge with runtime kwargs
        config_dict = get_configuration(**kwargs)

        # Set up backend-specific cache directories
        if not config_dict.get('model_cache_dir'):
            config_dict['model_cache_dir'] = self.model_paths.get_backend_specific_cache_dir(
                config_dict.get('backend', 'faster-whisper')
            )

        if 'no_transcription' in kwargs:
            config_dict['transcription'] = not kwargs['no_transcription']
        if 'no_vad' in kwargs:
            config_dict['vad'] = not kwargs['no_vad']
        if 'no_vac' in kwargs:
            config_dict['vac'] = not kwargs['no_vac']
        
        config_dict.pop('no_transcription', None)
        config_dict.pop('no_vad', None)

        if 'language' in kwargs:
            config_dict['lan'] = kwargs['language']
        config_dict.pop('language', None) 

        self.args = Namespace(**config_dict)
        
        self.asr = None
        self.tokenizer = None
        self.diarization = None
        self.vac_model = None
        
        if self.args.vac:
            import torch
            self.vac_model, _ = torch.hub.load(repo_or_dir="snakers4/silero-vad", model="silero_vad")            
        
        if self.args.transcription:
            if self.args.backend == "simulstreaming": 
                from whisperlivekit.simul_whisper import SimulStreamingASR
                self.tokenizer = None
                simulstreaming_kwargs = {}
                for attr in ['frame_threshold', 'beams', 'decoder_type', 'audio_max_len', 'audio_min_len', 
                            'cif_ckpt_path', 'never_fire', 'init_prompt', 'static_init_prompt', 
                            'max_context_tokens', 'model_path', 'warmup_file', 'preload_model_count', 'disable_fast_encoder']:
                    if hasattr(self.args, attr):
                        simulstreaming_kwargs[attr] = getattr(self.args, attr)
        
                # Add segment_length from min_chunk_size
                simulstreaming_kwargs['segment_length'] = getattr(self.args, 'min_chunk_size', 0.5)
                simulstreaming_kwargs['task'] = self.args.task
                
                size = self.args.model
                self.asr = SimulStreamingASR(
                    modelsize=size,
                    lan=self.args.lan,
                    cache_dir=getattr(self.args, 'model_cache_dir', None),
                    model_dir=getattr(self.args, 'model_dir', None),
                    **simulstreaming_kwargs
                )

            else:
                self.asr, self.tokenizer = backend_factory(self.args)
            warmup_asr(self.asr, self.args.warmup_file) #for simulstreaming, warmup should be done in the online class not here

        if self.args.diarization:
            if self.args.diarization_backend == "diart":
                from whisperlivekit.diarization.diart_backend import DiartDiarization
                self.diarization_model = DiartDiarization(
                    block_duration=self.args.min_chunk_size,
                    segmentation_model_name=self.args.segmentation_model,
                    embedding_model_name=self.args.embedding_model
                )
            elif self.args.diarization_backend == "sortformer":
                from whisperlivekit.diarization.sortformer_backend import SortformerDiarization
                self.diarization_model = SortformerDiarization()
            else:
                raise ValueError(f"Unknown diarization backend: {self.args.diarization_backend}")
            
        TranscriptionEngine._initialized = True



def online_factory(args, asr, tokenizer, logfile=sys.stderr):
    if args.backend == "simulstreaming":    
        from whisperlivekit.simul_whisper import SimulStreamingOnlineProcessor
        online = SimulStreamingOnlineProcessor(
            asr,
            logfile=logfile,
        )
        # warmup_online(online, args.warmup_file)
    else:
        online = OnlineASRProcessor(
            asr,
            tokenizer,
            logfile=logfile,
            buffer_trimming=(args.buffer_trimming, args.buffer_trimming_sec),
            confidence_validation = args.confidence_validation
        )
    return online
  
  
def online_diarization_factory(args, diarization_backend):
    if args.diarization_backend == "diart":
        online = diarization_backend
        # Not the best here, since several user/instances will share the same backend, but diart is not SOTA anymore and sortformer is recommanded
    
    if args.diarization_backend == "sortformer":
        from whisperlivekit.diarization.sortformer_backend import SortformerDiarizationOnline
        online = SortformerDiarizationOnline(shared_model=diarization_backend)
    return online

        