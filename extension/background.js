const isPopup = typeof window !== 'undefined' && window.document;

if (isPopup) {
    // ==========================================
    // POPUP CONTEXT LOGIC
    // ==========================================
    let mediaRecorder = null;
    let audioStream = null;
    let activeTabId = null;

    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const serverUrlInput = document.getElementById('serverUrl');
    const industrySelect = document.getElementById('industry');

    document.addEventListener('DOMContentLoaded', async () => {
        // Restore previous states if any
        chrome.storage.local.get(['isCapturing', 'serverUrl', 'industry'], (res) => {
            if (res.serverUrl) serverUrlInput.value = res.serverUrl;
            if (res.industry) industrySelect.value = res.industry;
            
            if (res.isCapturing) {
                setUIState(true);
            }
        });

        startBtn.addEventListener('click', startCapture);
        stopBtn.addEventListener('click', stopCapture);
    });

    async function startCapture() {
        const serverUrl = serverUrlInput.value.trim();
        const industry = industrySelect.value;

        // Save preferences
        chrome.storage.local.set({ serverUrl, industry });

        // Query active tab
        const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tabs.length === 0) return;
        const currentTab = tabs[0];
        activeTabId = currentTab.id;

        // Request tab capture
        chrome.tabCapture.capture({ audio: true, video: false }, (stream) => {
            if (!stream) {
                console.error("Tab capture failed or denied:", chrome.runtime.lastError);
                alert("Could not capture tab audio. Make sure you are on a live web page and have approved permissions.");
                return;
            }

            audioStream = stream;

            // Keep playing the audio in the popup/user tab so they can hear it
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioContext.createMediaStreamSource(stream);
            source.connect(audioContext.destination);

            // Notify VibeNote Dashboard to start a session
            chrome.runtime.sendMessage({
                action: "notify_start_session",
                url: currentTab.url,
                industry: industry,
                serverUrl: serverUrl
            });

            // Start recording audio chunks (1 second timeslices)
            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            mediaRecorder.ondataavailable = (event) => {
                if (event.data && event.data.size > 0) {
                    const reader = new FileReader();
                    reader.onloadend = () => {
                        const base64Audio = reader.result.split(',')[1];
                        chrome.runtime.sendMessage({
                            action: "stream_chunk",
                            chunk: base64Audio
                        });
                    };
                    reader.readAsDataURL(event.data);
                }
            };

            mediaRecorder.start(1000);
            setUIState(true);
            chrome.storage.local.set({ isCapturing: true });
        });
    }

    function stopCapture() {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }

        if (audioStream) {
            audioStream.getTracks().forEach(track => track.stop());
        }

        chrome.runtime.sendMessage({ action: "notify_end_session" });

        setUIState(false);
        chrome.storage.local.set({ isCapturing: false });
    }

    function setUIState(capturing) {
        if (capturing) {
            startBtn.style.display = 'none';
            stopBtn.style.display = 'block';
            statusDot.classList.add('active');
            statusText.textContent = 'Capturing';
        } else {
            startBtn.style.display = 'block';
            stopBtn.style.display = 'none';
            statusDot.classList.remove('active');
            statusText.textContent = 'Idle';
        }
    }

} else {
    // ==========================================
    // SERVICE WORKER CONTEXT LOGIC
    // ==========================================
    let dashboardTabId = null;

    // Listen for events from the popup
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.action === "notify_start_session") {
            findDashboardTab((tabId) => {
                if (tabId) {
                    dashboardTabId = tabId;
                    chrome.tabs.sendMessage(tabId, {
                        type: "VIBENOTE_START_SESSION",
                        url: message.url,
                        industry: message.industry,
                        serverUrl: message.serverUrl
                    });
                }
            });
        }
        
        else if (message.action === "stream_chunk") {
            if (dashboardTabId) {
                chrome.tabs.sendMessage(dashboardTabId, {
                    type: "VIBENOTE_AUDIO_CHUNK",
                    chunk: message.chunk
                });
            }
        }
        
        else if (message.action === "notify_end_session") {
            if (dashboardTabId) {
                chrome.tabs.sendMessage(dashboardTabId, {
                    type: "VIBENOTE_END_SESSION"
                });
            }
        }
    });

    // Helper to find VibeNote dashboard tab
    function findDashboardTab(callback) {
        // Query for tabs with VibeNote in title or local dev URLs
        chrome.tabs.query({}, (tabs) => {
            const dashboardTab = tabs.find(t => 
                t.url.includes("localhost") || 
                t.title.toLowerCase().includes("vibenote")
            );
            if (dashboardTab) {
                callback(dashboardTab.id);
            } else {
                console.warn("VibeNote dashboard tab not found. Open the dashboard page to connect extension.");
                callback(null);
            }
        });
    }
}
