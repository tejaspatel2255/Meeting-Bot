// VibeNote Service Worker (Manifest V3)

let ws = null;
let activeSessionId = null;
let selectedIndustry = "manufacturing";
let currentSpeaker = "Speaker 1";
let serverUrl = "http://localhost:5000";
let activeTabId = null;

// Listen for messages from popup, content scripts, and offscreen document
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log("Background received message:", message.action || message.type);

    if (message.action === "START_CAPTURE") {
        selectedIndustry = message.industry || "manufacturing";
        serverUrl = message.serverUrl || "http://localhost:5000";
        
        // 1. Query the active tab
        chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
            if (!tabs || tabs.length === 0) {
                sendResponse({ status: "error", error: "No active tab found" });
                return;
            }
            
            const currentTab = tabs[0];
            activeTabId = currentTab.id;
            
            try {
                // 2. Call /api/join to start a backend session
                const joinResponse = await fetch(`${serverUrl}/api/join`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: currentTab.url, industry: selectedIndustry })
                });
                
                const joinData = await joinResponse.json();
                activeSessionId = joinData.session_id || joinData.meeting_id;
                console.log("Created backend session:", activeSessionId);
                
                // 3. Obtain tab audio stream ID
                chrome.tabCapture.getMediaStreamId({ targetTabId: activeTabId }, async (streamId) => {
                    if (!streamId) {
                        console.error("Failed to get media stream ID");
                        sendResponse({ status: "error", error: "Tab capture permissions denied" });
                        return;
                    }
                    
                    // Connect WebSocket
                    connectWebSocket(serverUrl);
                    
                    // Create offscreen document to capture audio
                    await startOffscreenDocument(streamId);
                    
                    sendResponse({ status: "started", sessionId: activeSessionId });
                });
                
            } catch (err) {
                console.error("Error starting session:", err);
                sendResponse({ status: "error", error: err.message });
            }
        });
        return true; // Keep message channel open for async response
    }
    
    else if (message.action === "STOP_CAPTURE") {
        stopCapture();
        sendResponse({ status: "stopped" });
    }
    
    else if (message.action === "audio_chunk") {
        // Forward chunk received from offscreen document to WebSocket
        if (ws && ws.readyState === WebSocket.OPEN && activeSessionId) {
            const payload = {
                session_id: activeSessionId,
                audio: message.chunk,
                chunk: message.chunk,
                speaker: currentSpeaker,
                industry: selectedIndustry
            };
            // Format as Socket.IO event frame: 42["event_name", payload]
            ws.send(`42["audio_chunk", ${JSON.stringify(payload)}]`);
            console.log("Streamed audio chunk to WebSocket");
        }
    }
    
    else if (message.action === "SPEAKER_CHANGE") {
        currentSpeaker = message.speaker || "Speaker 1";
        console.log("Speaker changed to:", currentSpeaker);
    }
    
    // Relay events to the dashboard page if it is open (for page bridge compatibility)
    else if (message.type && message.type.startsWith("VIBENOTE_")) {
        findDashboardTab((tabId) => {
            if (tabId) {
                chrome.tabs.sendMessage(tabId, message);
            }
        });
    }
});

// WebSocket Socket.IO handshake/connection manager
function connectWebSocket(url) {
    try {
        const parsedUrl = new URL(url);
        const host = parsedUrl.host;
        const wsUrl = `ws://${host}/socket.io/?EIO=4&transport=websocket`;
        
        console.log("Connecting WebSocket to:", wsUrl);
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            console.log("WebSocket connection established.");
        };
        
        ws.onmessage = (event) => {
            const data = event.data;
            if (data.startsWith('0')) {
                // Engine.IO open packet, send Socket.IO connect packet (40)
                ws.send('40');
            } else if (data.startsWith('40')) {
                // Socket.IO connected. Join the session room
                if (activeSessionId) {
                    ws.send(`42["join_session", {"session_id": "${activeSessionId}"}]`);
                    console.log("Joined socket session room:", activeSessionId);
                }
            }
        };
        
        ws.onerror = (err) => {
            console.error("WebSocket error:", err);
        };
        
        ws.onclose = () => {
            console.log("WebSocket connection closed.");
        };
    } catch (e) {
        console.error("Failed to setup WebSocket:", e);
    }
}

// Start Offscreen Document in Manifest V3
async function startOffscreenDocument(streamId) {
    const hasDocument = await chrome.offscreen.hasDocument();
    if (hasDocument) {
        await chrome.offscreen.closeDocument();
    }
    
    console.log("Creating offscreen document...");
    await chrome.offscreen.createDocument({
        url: 'offscreen.html',
        reasons: ['USER_MEDIA'],
        justification: 'Capturing meeting tab audio to stream to transcription API'
    });
    
    // Give document a brief moment to load then send start capture message
    setTimeout(() => {
        chrome.runtime.sendMessage({
            action: "start_capture",
            streamId: streamId
        });
    }, 250);
}

// Stop all capture resources
async function stopCapture() {
    console.log("Stopping capture session...");
    
    // Close offscreen document (which stops the MediaRecorder and stream)
    const hasDoc = await chrome.offscreen.hasDocument();
    if (hasDoc) {
        chrome.runtime.sendMessage({ action: "stop_capture" });
        await chrome.offscreen.closeDocument();
    }
    
    // Close backend session
    if (activeSessionId && serverUrl) {
        try {
            await fetch(`${serverUrl}/api/end`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: activeSessionId })
            });
            console.log("Backend session closed successfully.");
        } catch (e) {
            console.error("Failed to close backend session:", e);
        }
    }
    
    // Close WebSocket
    if (ws) {
        ws.close();
        ws = null;
    }
    
    activeSessionId = null;
    currentSpeaker = "Speaker 1";
}

// Helper: search for dashboard page tab
function findDashboardTab(callback) {
    chrome.tabs.query({}, (tabs) => {
        const dashboardTab = tabs.find(t => 
            t.url.includes("localhost") || 
            t.title.toLowerCase().includes("vibenote")
        );
        if (dashboardTab) {
            callback(dashboardTab.id);
        } else {
            callback(null);
        }
    });
}
