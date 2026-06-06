import os
import sys
import numpy as np
from playwright.sync_api import sync_playwright
from bot.base_bot import BaseBot, float32_pcm_to_wav_bytes
import time

class GoogleMeetBot(BaseBot):
    def __init__(self, url, meeting_id, industry, socketio_instance):
        super().__init__(url, meeting_id, industry, socketio_instance)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def join(self):
        self.playwright = sync_playwright().start()
        
        bot_name = os.getenv("BOT_NAME", "VibeNote Bot")
        
        # Locate system chromium inside Linux containers if available
        exec_path = "/usr/bin/chromium" if os.path.exists("/usr/bin/chromium") else None
        
        # Launch Chromium with anti-detection and media settings
        self.browser = self.playwright.chromium.launch(
            headless=True,
            executable_path=exec_path,
            args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--window-size=1280,720"
            ]
        )
        
        self.context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        
        self.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.page = self.context.new_page()
        
        self.log(f"Navigating to Meet: {self.url}")
        self.page.goto(self.url)
        self.page.wait_for_timeout(3000)
        
        try:
            dismiss_buttons = [
                "button:has-text('Got it')",
                "button:has-text('Dismiss')",
                "[aria-label='Close']"
            ]
            for selector in dismiss_buttons:
                if self.page.locator(selector).is_visible():
                    self.page.click(selector, timeout=2000)
        except Exception:
            pass

        try:
            self.page.wait_for_selector("input[type='text'], [placeholder='Your name']", timeout=15000)
            self.page.fill("input[type='text'], [placeholder='Your name']", bot_name)
            self.log(f"Filled name: {bot_name}")
        except Exception as e:
            raise RuntimeError(f"Could not find name input field on Google Meet page: {e}")
            
        try:
            join_btn = self.page.locator("button:has-text('Ask to join'), button:has-text('Join now'), [aria-label='Ask to join'], [aria-label='Join now']")
            join_btn.first.click()
            self.log("Clicked Join button.")
        except Exception as e:
            raise RuntimeError(f"Could not find or click join button: {e}")
            
        self.status = "lobby"
        self.log("In lobby")
        
        admitted = False
        start_wait = time.time()
        while time.time() - start_wait < 30:
            if self.page.locator("text=You can't join this call").is_visible():
                raise RuntimeError("Access denied: You can't join this call.")
                
            if self.page.locator("[aria-label='Leave call'], button:has-text('Leave'), [aria-label='More options']").is_visible():
                admitted = True
                break
                
            self.page.wait_for_timeout(1000)
            
        if not admitted:
            self.log("Warning: Not admitted within 30 seconds. Proceeding to listen anyway.")
            
        self.status = "live"
        self.log("Live")

    def capture_audio(self):
        def handle_chunk(float_list):
            if not self.running:
                return
            arr = np.array(float_list, dtype=np.float32)
            wav_bytes = float32_pcm_to_wav_bytes(arr)
            self._send_audio_chunk(wav_bytes)
            
        self.page.expose_function("sendAudioChunk", handle_chunk)
        
        js_script = """
        (async () => {
            console.log("Injecting VibeNote Audio Capture Script...");
            const targetCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            const mixer = targetCtx.createChannelMerger(1);
            const bufferSize = 4096;
            const processor = targetCtx.createScriptProcessor(bufferSize, 1, 1);
            
            let sampleCounter = 0;
            let floatBuffer = new Float32Array(16000);
            
            processor.onaudioprocess = (e) => {
                const inputData = e.inputBuffer.getChannelData(0);
                for (let i = 0; i < inputData.length; i++) {
                    floatBuffer[sampleCounter++] = inputData[i];
                    if (sampleCounter >= 16000) {
                        if (window.sendAudioChunk) {
                            window.sendAudioChunk(Array.from(floatBuffer));
                        }
                        sampleCounter = 0;
                        floatBuffer = new Float32Array(16000);
                    }
                }
            };
            
            mixer.connect(processor);
            processor.connect(targetCtx.destination);
            
            window.connectStreamToMixer = (stream) => {
                try {
                    if (!stream || stream.getAudioTracks().length === 0) return;
                    console.log("Connecting stream to mixer:", stream.id);
                    const source = targetCtx.createMediaStreamSource(stream);
                    source.connect(mixer);
                } catch (err) {
                    console.warn(err);
                }
            };
            
            const origAddTrack = RTCPeerConnection.prototype.addTrack;
            RTCPeerConnection.prototype.addTrack = function(track, ...streams) {
                if (track.kind === 'audio') {
                    streams.forEach(stream => window.connectStreamToMixer(stream));
                }
                return origAddTrack.apply(this, [track, ...streams]);
            };
            
            const origSetOntrack = Object.getOwnPropertyDescriptor(RTCPeerConnection.prototype, 'ontrack');
            Object.defineProperty(RTCPeerConnection.prototype, 'ontrack', {
                set: function(fn) {
                    const wrapped = function(e) {
                        if (e.streams && e.streams[0]) {
                            window.connectStreamToMixer(e.streams[0]);
                        }
                        if (fn) fn.apply(this, [e]);
                    };
                    this.addEventListener('track', wrapped);
                }
            });

            setInterval(() => {
                const audios = document.querySelectorAll('audio, video');
                audios.forEach(el => {
                    if (el.srcObject && !el.dataset.capturedByVibeNote) {
                        el.dataset.capturedByVibeNote = "true";
                        window.connectStreamToMixer(el.srcObject);
                    }
                });
            }, 2000);
        })();
        """
        self.page.evaluate(js_script)
        
        while self.running:
            self.page.wait_for_timeout(1000)

    def leave(self):
        self.log("Leaving Google Meet meeting...")
        try:
            if self.page:
                leave_btn = self.page.locator("[aria-label='Leave call']")
                if leave_btn.is_visible():
                    leave_btn.click()
        except Exception:
            pass
            
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
            
        try:
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
