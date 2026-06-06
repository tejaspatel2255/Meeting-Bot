import os
import sys
import numpy as np
from playwright.sync_api import sync_playwright
from bot.base_bot import BaseBot, float32_pcm_to_wav_bytes
import time

class TeamsBot(BaseBot):
    def __init__(self, url, meeting_id, industry, socketio_instance):
        super().__init__(url, meeting_id, industry, socketio_instance)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def join(self):
        bot_name = os.getenv("BOT_NAME", "VibeNote Bot")
        
        self.playwright = sync_playwright().start()
        
        self.browser = self.playwright.chromium.launch(
            headless=True,
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
        
        self.log(f"Navigating to Teams URL: {self.url}")
        self.page.goto(self.url)
        self.page.wait_for_timeout(5000)
        
        # Click "Continue on this browser" to bypass the desktop download prompt page
        try:
            self.log("Bypassing Teams app download page...")
            bypass_btn = self.page.locator("button:has-text('Continue on this browser'), [data-tid='join-on-browser'], button.openInBrowser")
            if bypass_btn.is_visible():
                bypass_btn.click()
                self.log("Clicked 'Continue on this browser'.")
            else:
                # Some versions might redirect directly or show different structure, check url
                self.log("Bypass button not immediately visible; waiting for pre-join screen.")
        except Exception as e:
            self.log(f"Warning: Failed to bypass app download prompt: {e}")
            
        self.page.wait_for_timeout(5000)
        
        # Fill name field
        try:
            self.page.wait_for_selector("input[placeholder='Type your name'], input[id*='username'], input", timeout=15000)
            self.page.fill("input[placeholder='Type your name'], input[id*='username'], input", bot_name)
            self.log(f"Filled name: {bot_name}")
        except Exception as e:
            raise RuntimeError(f"Could not find name input field on Teams join page: {e}")

        # Click Join Now button
        try:
            join_btn = self.page.locator("button:has-text('Join now'), [data-tid='prejoin-join-button']")
            join_btn.first.click()
            self.log("Clicked Join now button.")
        except Exception as e:
            raise RuntimeError(f"Could not find or click join now button on Teams: {e}")
            
        self.status = "lobby"
        self.log("In lobby")
        
        # Wait up to 30 seconds to be admitted
        admitted = False
        start_wait = time.time()
        while time.time() - start_wait < 30:
            # Check for Teams meeting control indicators like "Hang up" / "Leave" button or call duration indicator
            if self.page.locator("[data-tid='call-hangup'], button:has-text('Leave'), [aria-label='Hang up']").is_visible():
                admitted = True
                break
            self.page.wait_for_timeout(1000)
            
        if not admitted:
            self.log("Warning: Not admitted within 30 seconds. Starting listen loop.")
            
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
        
        # AudioContext capture script
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
        self.log("Leaving Teams meeting...")
        try:
            if self.page:
                leave_btn = self.page.locator("[data-tid='call-hangup'], button:has-text('Leave')")
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
