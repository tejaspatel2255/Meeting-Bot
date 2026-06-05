import os
import sys
import torch
from pyannote.audio import Pipeline

from config import Config

# Module-level cache for the Pyannote Diarization pipeline
_pipeline = None
_pipeline_initialized = False

def get_diarization_pipeline():
    """
    Lazily loads the Pyannote speaker diarization pipeline once.
    Requires HF_TOKEN env variable to download models from Hugging Face.
    Forces the pipeline to run on CPU.
    """
    global _pipeline, _pipeline_initialized
    if not _pipeline_initialized:
        _pipeline_initialized = True
        hf_token = Config.HF_TOKEN
        
        if not hf_token:
            print("Warning: HF_TOKEN is not configured in .env. Pyannote speaker diarization will be unavailable.", 
                  file=sys.stderr, flush=True)
            return None
            
        print("Loading Pyannote Speaker Diarization pipeline (3.1) on CPU...", flush=True)
        try:
            # Load the pipeline
            _pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=hf_token
            )
            if _pipeline is not None:
                # Force pipeline to execute on CPU
                _pipeline.to(torch.device("cpu"))
                print("Pyannote Speaker Diarization pipeline loaded successfully on CPU.", flush=True)
            else:
                print("Failed to download or initialize Pyannote pipeline (returned None).", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"Error loading Pyannote Speaker Diarization pipeline: {e}\n"
                  f"Note: Make sure your HF_TOKEN is valid and you have accepted the user agreements for "
                  f"both 'pyannote/speaker-diarization-3.1' and 'pyannote/segmentation-3.0' on Hugging Face.", 
                  file=sys.stderr, flush=True)
            _pipeline = None
            
    return _pipeline


def diarize(file_path: str) -> list[dict]:
    """
    Executes speaker diarization on a local audio file path using Pyannote.
    Returns a list of diarized intervals: [{"speaker": str, "start": float, "end": float}]
    """
    if not file_path or not os.path.exists(file_path):
        print(f"Diarize failed: File not found: {file_path}", file=sys.stderr, flush=True)
        return []

    pipeline = get_diarization_pipeline()
    if pipeline is None:
        # Fallback to empty list so caller can apply default labels gracefully
        print("Pyannote pipeline not available. Skipping speaker diarization.", flush=True)
        return []

    try:
        print(f"Running Pyannote speaker diarization on: {file_path}...", flush=True)
        
        import torchaudio
        # Load audio in-memory to bypass torchcodec/FFmpeg loading warning
        waveform, sample_rate = torchaudio.load(file_path)
        
        # Run diarization pipeline using the loaded waveform
        annotation = pipeline({"waveform": waveform, "sample_rate": sample_rate})
        
        intervals = []
        for turn, _, speaker in annotation.itertracks(yield_label=True):
            intervals.append({
                "speaker": str(speaker),
                "start": float(turn.start),
                "end": float(turn.end)
            })
            
        print(f"Diarization complete. Found {len(intervals)} speaker intervals.", flush=True)
        return intervals

    except Exception as e:
        print(f"Error executing diarization pipeline: {e}", file=sys.stderr, flush=True)
        return []
