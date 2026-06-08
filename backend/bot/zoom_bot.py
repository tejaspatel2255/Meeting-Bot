import os
import sys
import re
import urllib.parse
import numpy as np
from playwright.sync_api import sync_playwright
from bot.base_bot import BaseBot, float32_pcm_to_wav_bytes
import time

def parse_zoom_url(url: str) -> dict:
    """Parses Zoom meeting ID and passcode from typical join links."""
    # Find sequence of digits after /j/ or /wc/
    match_id = re.search(r'/(?:j|wc)/(\d+)', url)
    meeting_id = match_id.group(1) if match_id else ""
    
    # Extract passcode from pwd query parameter
    parsed = urllib.parse.urlparse(url)
    queries = urllib.parse.parse_qs(parsed.query)
    password = queries.get('pwd', [''])[0]
    
    return {"meeting_id": meeting_id, "password": password}

class ZoomBot(BaseBot):
    def __init__(self, url, meeting_id, industry, socketio_instance):
        super().__init__(url, meeting_id, industry, socketio_instance)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def join(self):
        parsed = parse_zoom_url(self.url)
        zoom_id = parsed["meeting_id"]
        zoom_pwd = parsed["password"]
        
        if not zoom_id:
            raise ValueError(f"Could not parse valid Zoom Meeting ID from URL: {self.url}")
            
        bot_name = os.getenv("BOT_NAME", "VibeNote Bot")
        
        # Build the Web Client URL format
        join_url = f"https://zoom.us/wc/{zoom_id}/join"
        if zoom_pwd:
            join_url += f"?pwd={zoom_pwd}"
            
        self.playwright = sync_playwright().start()
        
        # Locate system chromium inside Linux containers if available
        exec_path = "/usr/bin/chromium" if os.path.exists("/usr/bin/chromium") else None
        
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
        
        self.log(f"Navigating to Zoom Web Client: {join_url}")
        self.page.goto(join_url)
        self.page.wait_for_timeout(4000)
        
        # Dismiss initial cookie consent overlay if it appears
        try:
            consent_btn = self.page.locator("#onetrust-accept-btn-handler, button:has-text('Accept All')")
            if consent_btn.is_visible():
                consent_btn.click(timeout=2000)
        except Exception:
            pass

        # Handle joining name field
        try:
            self.page.wait_for_selector("input[name='name'], input[placeholder='Your Name'], #inputname", timeout=15000)
            self.page.fill("input[name='name'], input[placeholder='Your Name'], #inputname", bot_name)
            self.log(f"Filled name field: {bot_name}")
        except Exception as e:
            raise RuntimeError(f"Could not find Name input on Zoom Web page: {e}")
            
        # Fill passcode if not in URL and requested on screen
        if self.page.locator("input[name='password'], input[placeholder='Meeting Passcode'], #inputpasscode").is_visible():
            if zoom_pwd:
                self.page.fill("input[name='password'], input[placeholder='Meeting Passcode'], #inputpasscode", zoom_pwd)
                self.log("Filled on-screen passcode field.")
            else:
                self.log("Warning: passcode input visible but no pwd parameter was supplied.")
                
        # Click Join Button
        try:
            join_btn = self.page.locator("button:has-text('Join'), button[type='submit'], .button-join")
            join_btn.first.click()
            self.log("Clicked Join button.")
        except Exception as e:
            raise RuntimeError(f"Could not find or click join button on Zoom Web: {e}")
            
        self.status = "lobby"
        self.log("In lobby")
        self.lobby_entered_at = time.time()
        
        while self.running:
            # Check if blocked or denied entry
            if self.page.locator("text=declined, text=removed, text=denied, text=Meeting ID is not valid").is_visible():
                self._notify("blocked", "Zoom blocked the bot. Use the Chrome extension instead.")
                self.stop()
                break
                
            # Check if admitted
            if self.page.locator("button:has-text('Leave'), .foot-button__leave-btn, [aria-label='Leave meeting']").is_visible():
                self.status = "live"
                self._notify("admitted", "Bot successfully admitted to Zoom.")
                self.log("Live")
                break
                
            # If still waiting in lobby, check timeout
            self._check_lobby_timeout()
            
            # Sleep 10 seconds in small intervals to stay responsive to stop signals
            for _ in range(10):
                if not self.running:
                    break
                self.page.wait_for_timeout(1000)

    def capture_audio(self):
        def handle_chunk(float_list):
            if not self.running:
                return
            arr = np.array(float_list, dtype=np.float32)
            wav_bytes = float32_pcm_to_wav_bytes(arr)
            self._send_audio_chunk(wav_bytes)
            
        self.page.expose_function("sendAudioChunk", handle_chunk)
        
        # AudioContext interception script (same mix logic)
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
        self.log("Leaving Zoom meeting...")
        try:
            if self.page:
                leave_btn = self.page.locator("button:has-text('Leave'), .foot-button__leave-btn")
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
