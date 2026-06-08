import os
import sys
import tempfile
import numpy as np
import soundfile as sf
import scipy.signal
import whisper
import torch

# Module-level caches for Whisper models
_whisper_base = None
_whisper_small = None

def get_base_model():
    """Lazily loads and returns the Whisper 'base' model on CPU."""
    global _whisper_base
    if _whisper_base is None:
        print("Loading Whisper 'base' model on CPU...", flush=True)
        try:
            # base model is ~140M parameters, suitable for fast CPU chunk processing
            _whisper_base = whisper.load_model("base", device="cpu")
            print("Whisper 'base' model loaded successfully.", flush=True)
        except Exception as e:
            print(f"Failed to load Whisper 'base' model: {e}", file=sys.stderr, flush=True)
            raise e
    return _whisper_base

def get_small_model():
    """Lazily loads and returns the Whisper 'small' model on CPU."""
    global _whisper_small
    if _whisper_small is None:
        print("Loading Whisper 'small' model on CPU...", flush=True)
        try:
            # small model is ~240M parameters, providing better quality for batch uploads
            _whisper_small = whisper.load_model("small", device="cpu")
            print("Whisper 'small' model loaded successfully.", flush=True)
        except Exception as e:
            print(f"Failed to load Whisper 'small' model: {e}", file=sys.stderr, flush=True)
            raise e
    return _whisper_small


from vad import contains_speech

def transcribe_chunk(audio_bytes: bytes) -> str | None:
    """
    Accepts raw audio bytes (webm/opus from browser), converts to 
    16kHz float32 numpy array, runs VAD gate, and transcribes using the base model on CPU.
    Returns None if silence or very short output.
    """
    if not audio_bytes or len(audio_bytes) == 0:
        return None
        
    temp_path = None
    try:
        # Write binary chunk to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name

        audio_array = None
        
        # Method A: Try parsing and reading with soundfile
        try:
            data, samplerate = sf.read(temp_path)
            
            # Convert stereo to mono by averaging channels
            if len(data.shape) > 1:
                data = data.mean(axis=1)
                
            # Resample to 16000Hz (required by Whisper)
            if samplerate != 16000:
                num_samples = int(len(data) * 16000 / samplerate)
                data = scipy.signal.resample(data, num_samples)
                
            audio_array = data.astype(np.float32)
        except Exception as sf_err:
            # Method B Fallback: Use Whisper's internal ffmpeg-based audio loader
            # This is extremely resilient against container wrapper formats (like WebM/Opus)
            try:
                audio_array = whisper.load_audio(temp_path)
            except Exception as ffmpeg_err:
                raise RuntimeError(f"Audio loading failed. Soundfile: {sf_err}. ffmpeg: {ffmpeg_err}")

        # VAD gate — check before sending to Whisper
        if not contains_speech(audio_array):
            return None   # skip — no speech detected

        # Run inference using the cached base model
        model = get_base_model()
        result = model.transcribe(audio_array, fp16=False, language='en')
        text = result.get("text", "").strip()

        # Additional guard: skip very short outputs (likely noise artifacts)
        if len(text) < 3:
            return None

        return text

    except Exception as e:
        print(f"Error in transcribe_chunk: {e}", file=sys.stderr, flush=True)
        return ""
    finally:
        # Ensure temporary file cleanup
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as cleanup_err:
                print(f"Error removing temp file {temp_path}: {cleanup_err}", file=sys.stderr, flush=True)


def transcribe_file(file_path: str) -> list[dict]:
    """
    Transcribes a full audio file from local path using the Whisper 'small' model on CPU.
    Returns segments in the format: [{"start": float, "end": float, "text": str, "speaker": "Unknown"}]
    """
    if not file_path or not os.path.exists(file_path):
        print(f"File not found: {file_path}", file=sys.stderr, flush=True)
        return []

    try:
        model = get_small_model()
        print(f"Running Whisper 'small' model on file: {file_path}...", flush=True)
        
        # Transcribe without fp16 on CPU
        result = model.transcribe(file_path, fp16=False)
        
        raw_segments = result.get("segments", [])
        transcribed_segments = []
        
        for seg in raw_segments:
            transcribed_segments.append({
                "start": float(seg.get("start", 0.0)),
                "end": float(seg.get("end", 0.0)),
                "text": seg.get("text", "").strip(),
                "speaker": "Unknown"
            })
            
        return transcribed_segments

    except Exception as e:
        print(f"Error in transcribe_file: {e}", file=sys.stderr, flush=True)
        return []


def assign_speakers(segments: list[dict], diarization: list[dict]) -> list[dict]:
    """
    Maps Whisper transcribed segments to pyannote diarized speakers based on timestamp overlap.
    For each text segment, we assign the speaker who speaks the most during that time interval.
    """
    if not segments:
        return []
        
    if not diarization:
        # Default all segments to "Speaker 1" if no speaker intervals were found
        for seg in segments:
            seg["speaker"] = "Speaker 1"
        return segments

    for seg in segments:
        seg_start = seg["start"]
        seg_end = seg["end"]
        
        speaker_overlaps = {}
        
        # Calculate overlap duration for each speaker
        for diar in diarization:
            diar_start = diar["start"]
            diar_end = diar["end"]
            speaker = diar["speaker"]
            
            # Find intersection of [seg_start, seg_end] and [diar_start, diar_end]
            overlap_start = max(seg_start, diar_start)
            overlap_end = min(seg_end, diar_end)
            overlap_duration = max(0.0, overlap_end - overlap_start)
            
            if overlap_duration > 0:
                speaker_overlaps[speaker] = speaker_overlaps.get(speaker, 0.0) + overlap_duration

        if speaker_overlaps:
            # Assign the speaker with the maximum overlap duration
            best_speaker = max(speaker_overlaps, key=speaker_overlaps.get)
            seg["speaker"] = best_speaker
        else:
            # Fallback: Find the closest speaker interval in time
            closest_speaker = "Unknown"
            min_dist = float('inf')
            
            for diar in diarization:
                if diar["end"] < seg_start:
                    dist = seg_start - diar["end"]
                else:
                    dist = diar["start"] - seg_end
                
                if dist < min_dist:
                    min_dist = dist
                    closest_speaker = diar["speaker"]
            
            seg["speaker"] = closest_speaker if closest_speaker != "Unknown" else "Speaker 1"

    return segments
