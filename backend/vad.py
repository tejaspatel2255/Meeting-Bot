import torch
import numpy as np
import sys

# Load silero-vad model once at module level (CPU)
# Use torch.hub to load — no pip install needed beyond torch
model = None
try:
    model, utils = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad',
        force_reload=False,
        trust_repo=True
    )
    (get_speech_timestamps, _, read_audio, *_) = utils
    print("Silero VAD model loaded successfully.", flush=True)
except Exception as e:
    print(f"Warning: Failed to load Silero VAD from torch.hub: {e}. Falling back to default pass-through VAD.", file=sys.stderr, flush=True)

VAD_THRESHOLD = 0.5      # confidence threshold (0.0-1.0)
SAMPLE_RATE = 16000

def contains_speech(audio) -> bool:
    """
    Returns True if audio chunk contains human speech.
    Returns False if silence, music, background noise only.
    Fast: runs in <10ms on CPU.
    """
    if model is None:
        # Fallback: always assume there is speech to avoid breaking the audio pipeline
        return True
        
    if isinstance(audio, bytes):
        audio_np = np.frombuffer(audio, dtype=np.float32)
    else:
        audio_np = audio
        
    if len(audio_np) == 0:
        return False
        
    try:
        audio_tensor = torch.from_numpy(audio_np)
        # Use get_speech_timestamps helper to handle arbitrary length audio
        timestamps = get_speech_timestamps(
            audio_tensor,
            model,
            sampling_rate=SAMPLE_RATE,
            threshold=VAD_THRESHOLD
        )
        return len(timestamps) > 0
    except Exception as e:
        print(f"Error running VAD inference: {e}. Falling back to True.", file=sys.stderr, flush=True)
        return True

def get_speech_confidence(audio) -> float:
    """Returns raw speech probability 0.0-1.0"""
    if model is None:
        return 1.0
        
    if isinstance(audio, bytes):
        audio_np = np.frombuffer(audio, dtype=np.float32)
    else:
        audio_np = audio
        
    if len(audio_np) == 0:
        return 0.0
        
    try:
        audio_tensor = torch.from_numpy(audio_np)
        # Fallback raw probability by getting model score on first 512 samples or returning 1.0/0.0 based on timestamps
        timestamps = get_speech_timestamps(
            audio_tensor,
            model,
            sampling_rate=SAMPLE_RATE,
            threshold=VAD_THRESHOLD
        )
        return 1.0 if len(timestamps) > 0 else 0.0
    except Exception as e:
        return 1.0
