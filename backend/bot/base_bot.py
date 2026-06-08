import abc
import time
import os
import sys
import numpy as np
import io
import wave
from transcriber import transcribe_chunk
from gemini_client import analyze_line

def float32_pcm_to_wav_bytes(float32_array, samplerate=16000):
    """Converts a numpy Float32 PCM array into 16-bit PCM WAV bytes."""
    # Clip values to prevent distortion/overflow
    clipped = np.clip(float32_array, -1.0, 1.0)
    int16_array = (clipped * 32767.0).astype(np.int16)
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(samplerate)
        wav_file.writeframes(int16_array.tobytes())
    return wav_io.getvalue()

class BaseBot(abc.ABC):
    def __init__(self, url: str, meeting_id: str, industry: str, socketio_instance):
        self.url = url
        self.meeting_id = meeting_id
        self.industry = industry
        self.socketio = socketio_instance
        self.running = False
        self.status = "joining" # joining | lobby | live | stopped | error
        self.logs = ["Launching"]
        self.start_time = time.time()
        self.error_msg = None
        
        # Lobby configuration
        self.lobby_timeout = int(os.getenv("LOBBY_TIMEOUT", 120))
        self.max_lobby_notifications = int(os.getenv("MAX_LOBBY_NOTIFICATIONS", 3))
        self.lobby_entered_at = None
        self.lobby_notifications_sent = 0
        self.last_notification_sent_at = 0

    def log(self, message: str):
        print(f"[Bot][{self.meeting_id}] {message}", flush=True)
        self.logs.append(message)

    @abc.abstractmethod
    def join(self):
        pass

    @abc.abstractmethod
    def capture_audio(self):
        pass

    @abc.abstractmethod
    def leave(self):
        pass

    def start(self):
        self.running = True
        try:
            self.log("Navigating")
            self.join()
            # The join subclass method determines when transitioning to 'lobby' or 'live'
            self.capture_audio()
        except Exception as e:
            self.log(f"Error encountered: {e}")
            self.status = "error"
            self.error_msg = str(e)
            if self.socketio:
                self.socketio.emit("bot_error", {"meeting_id": self.meeting_id, "error": str(e)}, room=self.meeting_id)
            self.stop()

    def stop(self):
        self.running = False
        if self.status != "error":
            self.status = "stopped"
        self.log("Stopped")
        try:
            self.leave()
        except Exception as e:
            print(f"Error cleanup during leave: {e}", file=sys.stderr, flush=True)

    def _send_audio_chunk(self, audio_bytes: bytes):
        if not self.running:
            return
        
        # Process transcription chunk
        text = transcribe_chunk(audio_bytes)
        if text is None:
            return   # silence — skip
            
        elapsed_sec = int(time.time() - self.start_time)
        min_part = elapsed_sec // 60
        sec_part = elapsed_sec % 60
        timestamp = f"{min_part}:{sec_part:02d}"
        
        # Analyze using LLM
        analysis = analyze_line(text, "VibeNote Bot", self.industry)
        
        line_data = {
            "speaker": "VibeNote Bot",
            "text": text,
            "timestamp": timestamp,
            "emotion": analysis.get("emotion", "Neutral"),
            "insight": analysis.get("insight", ""),
            "jargon_terms": analysis.get("jargon_terms", []),
            "real_speech": True
        }
        
        # Propagate to dashboard rooms via Socket.IO
        if self.socketio:
            self.socketio.emit("transcript_line", line_data, room=self.meeting_id)
            self.socketio.emit("live_transcript", {"speaker": "VibeNote Bot", "text": text, "timestamp": timestamp}, room=self.meeting_id)

    def _notify(self, type: str, message: str, extra: dict = {}):
        self.log(f"Notification [{type}]: {message}")
        if self.socketio:
            data = {
                "type": type,
                "message": message,
                "meeting_id": self.meeting_id,
                "timestamp": time.time()
            }
            data.update(extra)
            self.socketio.emit("bot_notification", data, room=self.meeting_id)

    def _check_lobby_timeout(self):
        if not self.lobby_entered_at:
            self.lobby_entered_at = time.time()
            self.lobby_notifications_sent = 0
            self.last_notification_sent_at = 0
            
        elapsed = time.time() - self.lobby_entered_at
        if elapsed > self.lobby_timeout:
            now = time.time()
            if self.lobby_notifications_sent == 0 or (now - self.last_notification_sent_at >= 60):
                self.lobby_notifications_sent += 1
                self.last_notification_sent_at = now
                
                if self.lobby_notifications_sent <= self.max_lobby_notifications:
                    self._notify(
                        "lobby_timeout",
                        f"Bot has been waiting in lobby for {int(elapsed // 60)} minutes. Please admit VibeNote Bot from the meeting.",
                        {"waited_seconds": int(elapsed)}
                    )
                else:
                    self._notify(
                        "bot_abandoned",
                        "Bot gave up waiting after 4 minutes. Please rejoin manually or upload a recording."
                    )
                    self.stop()
            
            # Aggregate global emotions spectrum update
            # We can update global state via Socket.IO if needed, but emitting directly is the primary requirement.
