import os
import sys
import numpy as np
from playwright.async_api import async_playwright
from bot.base_bot import BaseBot, float32_pcm_to_wav_bytes
import time
import asyncio
import random

async def _human_type(page, selector: str, text: str):
    """Type like a human — random delay between each keystroke"""
    await page.click(selector)
    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.05, 0.18))

async def _human_move_and_click(page, selector: str):
    """Move mouse to element with slight random offset before clicking"""
    element = await page.query_selector(selector)
    box = await element.bounding_box()
    # Move to a random point near center of element
    x = box['x'] + box['width'] / 2 + random.uniform(-5, 5)
    y = box['y'] + box['height'] / 2 + random.uniform(-3, 3)
    await page.mouse.move(x, y, steps=random.randint(8, 15))
    await asyncio.sleep(random.uniform(0.1, 0.3))
    await page.mouse.click(x, y)

async def _random_delay(min_ms=500, max_ms=1500):
    """Random pause to simulate human thinking"""
    await asyncio.sleep(random.uniform(min_ms/1000, max_ms/1000))

class GoogleMeetBot(BaseBot):
    def __init__(self, url, meeting_id, industry, socketio_instance):
        super().__init__(url, meeting_id, industry, socketio_instance)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.loop = asyncio.new_event_loop()

    def join(self):
        self.loop.run_until_complete(self.join_with_retry())

    async def join_with_retry(self):
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                self.log(f"Attempting to join Google Meet (Try {attempt + 1}/{max_retries + 1})")
                await self.async_join()
                return # Success!
            except Exception as e:
                self.log(f"Attempt {attempt + 1} failed: {e}")
                await self.async_cleanup()
                if attempt < max_retries:
                    sleep_time = random.uniform(5, 10)
                    self.log(f"Waiting {sleep_time:.2f} seconds before retrying...")
                    await asyncio.sleep(sleep_time)
                else:
                    self._notify("blocked", "Google Meet blocked the bot. Use the Chrome extension instead.")
                    self.stop()
                    raise RuntimeError("All Google Meet join attempts failed.")

    async def async_join(self):
        self.playwright = await async_playwright().start()
        
        bot_name = os.getenv("BOT_NAME", "VibeNote Bot")
        
        # Locate system chromium inside Linux containers if available
        exec_path = "/usr/bin/chromium" if os.path.exists("/usr/bin/chromium") else None
        
        # Launch Chromium with anti-detection and media settings
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            executable_path=exec_path,
            args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                "--disable-blink-features=AutomationControlled",
                "--exclude-switches=enable-automation",
                "--disable-automation",
                "--disable-features=IsolateOrigins,site-per-process",
                "--flag-switches-begin",
                "--flag-switches-end",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--window-size=1280,720"
            ]
        )
        
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        
        await self.context.add_init_script("""
          // Remove webdriver flag
          Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
          
          // Fake plugins array (real Chrome has plugins)
          Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
          });
          
          // Fake languages
          Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
          });
          
          // Fake chrome object
          window.chrome = {
            runtime: {},
            loadTimes: function(){},
            csi: function(){},
            app: {}
          };
          
          // Fix permissions
          const originalQuery = window.navigator.permissions.query;
          window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
              ? Promise.resolve({state: Notification.permission})
              : originalQuery(parameters);
        """)
        
        self.page = await self.context.new_page()
        
        self.log(f"Navigating to Meet: {self.url}")
        await self.page.goto(self.url)
        await _random_delay(1000, 2000)
        
        try:
            dismiss_buttons = [
                "button:has-text('Got it')",
                "button:has-text('Dismiss')",
                "[aria-label='Close']"
            ]
            for selector in dismiss_buttons:
                if await self.page.locator(selector).is_visible():
                    await self.page.click(selector, timeout=2000)
        except Exception:
            pass

        try:
            name_input_selector = "input[type='text'], [placeholder='Your name']"
            await self.page.wait_for_selector(name_input_selector, timeout=15000)
            await _random_delay(500, 1000)
            
            await _human_type(self.page, name_input_selector, bot_name)
            self.log(f"Filled name: {bot_name}")
            await _random_delay(800, 1500)
        except Exception as e:
            raise RuntimeError(f"Could not find name input field on Google Meet page: {e}")
            
        try:
            join_btn_selector = "button:has-text('Ask to join'), button:has-text('Join now'), [aria-label='Ask to join'], [aria-label='Join now']"
            await _random_delay(200, 500)
            await _human_move_and_click(self.page, join_btn_selector)
            self.log("Clicked Join button.")
        except Exception as e:
            raise RuntimeError(f"Could not find or click join button: {e}")
            
        self.status = "lobby"
        self.log("In lobby")
        self.lobby_entered_at = time.time()
        
        while self.running:
            # Check if blocked or denied entry
            if await self.page.locator("text=You can't join this call, text=Someone in the meeting has denied your request").is_visible():
                self._notify("blocked", "Google Meet blocked the bot. Use the Chrome extension instead.")
                self.stop()
                break
                
            # Check if admitted
            if await self.page.locator("[aria-label='Leave call'], button:has-text('Leave'), [aria-label='More options']").is_visible():
                self.status = "live"
                self._notify("admitted", "Bot successfully admitted to Google Meet.")
                self.log("Live")
                break
                
            # If still waiting in lobby, check timeout
            self._check_lobby_timeout()
            
            # Sleep 10 seconds in small intervals to stay responsive to stop signals
            for _ in range(10):
                if not self.running:
                    break
                await self.page.wait_for_timeout(1000)

    def capture_audio(self):
        self.loop.run_until_complete(self.async_capture_audio())

    async def async_capture_audio(self):
        def handle_chunk(float_list):
            if not self.running:
                return
            arr = np.array(float_list, dtype=np.float32)
            wav_bytes = float32_pcm_to_wav_bytes(arr)
            self._send_audio_chunk(wav_bytes)
            
        await self.page.expose_function("sendAudioChunk", handle_chunk)
        
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
        await self.page.evaluate(js_script)
        
        while self.running:
            await self.page.wait_for_timeout(1000)

    def leave(self):
        try:
            self.loop.run_until_complete(self.async_leave())
        finally:
            self.loop.close()

    async def async_leave(self):
        self.log("Leaving Google Meet meeting...")
        try:
            if self.page:
                leave_btn = self.page.locator("[aria-label='Leave call']")
                if await leave_btn.is_visible():
                    await leave_btn.click()
        except Exception:
            pass
            
        await self.async_cleanup()

    async def async_cleanup(self):
        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
            
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
