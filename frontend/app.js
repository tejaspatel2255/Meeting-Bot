// API Base URL config (can point to docker backend port)
const BACKEND_URL = 'http://localhost:5000';

// Socket connection initialization
let socket;
try {
    socket = io(BACKEND_URL);
} catch (e) {
    console.error("SocketIO connection failed: ", e);
}

// Global Application State
let isRecording = false;
let mediaRecorder = null;
let audioStream = null;
let activeSessionId = null;
let emotionChart = null;

// DOM Selectors
const connectionStatusEl = document.getElementById('connectionStatus');
const meetingUrlInput = document.getElementById('meetingUrl');
const industrySelect = document.getElementById('industrySelect');
const startLiveBtn = document.getElementById('startLiveBtn');
const audioUploadInput = document.getElementById('audioUpload');
const uploadTriggerBtn = document.getElementById('uploadTriggerBtn');
const fileNameDisplay = document.getElementById('fileNameDisplay');
const transcriptFeed = document.getElementById('transcriptFeed');
const liveIndicator = document.getElementById('liveIndicator');
const topicCloud = document.getElementById('topicCloud');
const topicEmptyState = document.getElementById('topicEmptyState');
const summaryReport = document.getElementById('summaryReport');
const summaryEmptyState = document.getElementById('summaryEmptyState');
const emotionChartCanvas = document.getElementById('emotionChartCanvas');
const chartEmptyState = document.getElementById('chartEmptyState');

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', () => {
    setupSocketListeners();
    setupEventHandlers();
    initEmotionChart();
});

// Setup WebSockets
function setupSocketListeners() {
    if (!socket) return;

    socket.on('connect', () => {
        console.log('Connected to backend SocketIO server');
        connectionStatusEl.innerHTML = `
            <span class="status-dot connected"></span>
            <span class="status-text">Connected</span>
        `;
    });

    socket.on('disconnect', () => {
        console.log('Disconnected from backend SocketIO server');
        connectionStatusEl.innerHTML = `
            <span class="status-dot disconnected"></span>
            <span class="status-text">Disconnected</span>
        `;
    });

    // Real-Time Transcript Event
    socket.on('live_transcript', (data) => {
        removeEmptyState(transcriptFeed);
        appendTranscriptBubble(data.speaker, data.text, data.timestamp);
    });

    // Real-Time Topics Event
    socket.on('live_topics', (topics) => {
        renderTopicCloud(topics);
    });

    // Real-Time Emotions Event
    socket.on('live_emotions', (emotions) => {
        updateEmotionChart(emotions);
    });
}

// Setup Interactive Click & Upload Handlers
function setupEventHandlers() {
    // Start/Stop Live Recording
    startLiveBtn.addEventListener('click', toggleLiveSession);

    // Audio File Upload Trigger
    uploadTriggerBtn.addEventListener('click', () => {
        audioUploadInput.click();
    });

    // Handle File Selection
    audioUploadInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            fileNameDisplay.textContent = file.name;
            handleFileUpload(file);
        } else {
            fileNameDisplay.textContent = "No file chosen";
        }
    });
}

// Chart.js Emotional Spectrum Initialization
function initEmotionChart() {
    const ctx = emotionChartCanvas.getContext('2d');
    
    // Sleek dark palette color schemes
    const colors = {
        'Professional': 'hsla(265, 85%, 62%, 0.85)',
        'Urgent': 'hsla(0, 85%, 60%, 0.85)',
        'Concerned': 'hsla(35, 85%, 55%, 0.85)',
        'Relieved': 'hsla(145, 80%, 45%, 0.85)',
        'Calm': 'hsla(190, 90%, 45%, 0.85)',
        'Neutral': 'hsla(230, 12%, 58%, 0.85)',
        'Focused': 'hsla(200, 70%, 50%, 0.85)',
        'Stressed': 'hsla(320, 80%, 60%, 0.85)'
    };

    emotionChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: [],
                borderColor: 'rgba(25, 27, 38, 0.6)',
                borderWidth: 2,
                hoverOffset: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#c2c6d6',
                        font: {
                            family: 'Outfit',
                            size: 11
                        },
                        boxWidth: 10,
                        padding: 10
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return ` ${context.label}: ${context.raw}%`;
                        }
                    }
                }
            },
            cutout: '65%'
        }
    });
}

// Update Emotion Chart Data
function updateEmotionChart(emotionsData) {
    if (!emotionChart) return;
    
    chartEmptyState.classList.add('hidden');
    emotionChartCanvas.style.opacity = '1';

    const labels = Object.keys(emotionsData);
    const data = Object.values(emotionsData);
    
    // Map HSL colors
    const colors = {
        'Professional': 'hsla(265, 85%, 62%, 0.85)',
        'Urgent': 'hsla(0, 85%, 60%, 0.85)',
        'Concerned': 'hsla(35, 85%, 55%, 0.85)',
        'Relieved': 'hsla(145, 80%, 45%, 0.85)',
        'Calm': 'hsla(190, 90%, 45%, 0.85)',
        'Neutral': 'hsla(230, 12%, 58%, 0.85)',
        'Focused': 'hsla(200, 70%, 50%, 0.85)',
        'Stressed': 'hsla(320, 80%, 60%, 0.85)',
        'Apprehensive': 'hsla(35, 80%, 50%, 0.85)',
        'Satisfied': 'hsla(145, 75%, 40%, 0.85)'
    };

    const bgColors = labels.map(label => colors[label] || 'hsla(265, 85%, 62%, 0.85)');

    emotionChart.data.labels = labels;
    emotionChart.data.datasets[0].data = data;
    emotionChart.data.datasets[0].backgroundColor = bgColors;
    emotionChart.update();
}

// Reset Charts and UI
function resetDashboardUI() {
    transcriptFeed.innerHTML = '';
    
    // Reset topics
    topicCloud.innerHTML = '';
    topicCloud.appendChild(topicEmptyState);
    topicEmptyState.classList.remove('hidden');

    // Reset summary
    summaryReport.innerHTML = '';
    summaryReport.appendChild(summaryEmptyState);
    summaryEmptyState.classList.remove('hidden');

    // Reset Chart
    if (emotionChart) {
        emotionChart.data.labels = [];
        emotionChart.data.datasets[0].data = [];
        emotionChart.update();
    }
    chartEmptyState.classList.remove('hidden');
    emotionChartCanvas.style.opacity = '0';
}

// Toggle Live Session Lifecycle
async function toggleLiveSession() {
    if (isRecording) {
        // Stop recording
        stopLiveAudioStream();
    } else {
        // Start recording
        resetDashboardUI();
        const success = await startLiveAudioStream();
        if (!success) {
            alert("Microphone access is required to run live sessions.");
        }
    }
}

// Start Microphones and Join Socket Room
async function startLiveAudioStream() {
    const meetingUrl = meetingUrlInput.value.trim() || 'http://localhost';
    const industry = industrySelect.value;

    try {
        // Step 1: Call API to join/create session
        const response = await fetch(`${BACKEND_URL}/api/join`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: meetingUrl, industry: industry })
        });
        const data = await response.json();
        
        if (data.status !== 'success') {
            throw new Error(data.message || 'Failed to initialize session');
        }
        
        activeSessionId = data.session_id;
        console.log(`Active Session Created: ${activeSessionId}`);

        // Join room in Socket
        if (socket && socket.connected) {
            socket.emit('join_session', { session_id: activeSessionId });
        }

        // Step 2: Request microphone
        audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        // Start MediaRecorder (send audio chunks every 1 second)
        mediaRecorder = new MediaRecorder(audioStream, { mimeType: 'audio/webm' });
        mediaRecorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0 && socket && socket.connected) {
                const reader = new FileReader();
                reader.onloadend = () => {
                    // Extract base64 representation of audio chunk
                    const base64Audio = reader.result.split(',')[1];
                    socket.emit('audio_chunk', {
                        session_id: activeSessionId,
                        chunk: base64Audio
                    });
                };
                reader.readAsDataURL(event.data);
            }
        };

        mediaRecorder.start(1000); // 1000ms chunk sizes
        
        // Update UI Button State
        isRecording = true;
        startLiveBtn.innerHTML = `<i class="fa-solid fa-square"></i> Stop Live Session`;
        startLiveBtn.classList.add('recording');
        liveIndicator.classList.remove('hidden');
        
        console.log("Live audio stream recording started...");
        return true;
    } catch (err) {
        console.error("Error launching live session:", err);
        return false;
    }
}

// Stop Audio Stream and Finalize Session
async function stopLiveAudioStream() {
    console.log("Stopping audio stream...");
    
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }
    
    if (audioStream) {
        audioStream.getTracks().forEach(track => track.stop());
    }

    // Update UI Button State
    isRecording = false;
    startLiveBtn.innerHTML = `<i class="fa-solid fa-microphone"></i> Start Live Session`;
    startLiveBtn.classList.remove('recording');
    liveIndicator.classList.add('hidden');

    if (!activeSessionId) return;

    // Call End API to get final summary and diagnostics
    try {
        startLiveBtn.disabled = true;
        startLiveBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Finalizing...`;
        
        const response = await fetch(`${BACKEND_URL}/api/end`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: activeSessionId })
        });
        
        const data = await response.json();
        if (data.status === 'success') {
            displayFinalReport(data);
        }
    } catch (err) {
        console.error("Error finalizing session:", err);
    } finally {
        startLiveBtn.disabled = false;
        startLiveBtn.innerHTML = `<i class="fa-solid fa-microphone"></i> Start Live Session`;
        activeSessionId = null;
    }
}

// Handle Batch Recording File Upload
async function handleFileUpload(file) {
    const industry = industrySelect.value;
    
    // Update Button/UI state for progress indication
    uploadTriggerBtn.disabled = true;
    uploadTriggerBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processing...`;
    resetDashboardUI();

    const formData = new FormData();
    formData.append('file', file);
    formData.append('industry', industry);

    try {
        const response = await fetch(`${BACKEND_URL}/api/upload`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            displayFinalReport(data);
        } else {
            alert("Error: " + data.message);
        }
    } catch (e) {
        console.error("Upload error:", e);
        alert("An error occurred during audio processing.");
    } finally {
        uploadTriggerBtn.disabled = false;
        uploadTriggerBtn.innerHTML = `<i class="fa-solid fa-cloud-arrow-up"></i> Upload Recording`;
    }
}

// Display final compiled reports on page
function displayFinalReport(data) {
    // 1. Populate Transcript
    transcriptFeed.innerHTML = '';
    if (data.transcript && data.transcript.length > 0) {
        data.transcript.forEach((bubble, idx) => {
            appendTranscriptBubble(bubble.speaker, bubble.text, bubble.timestamp, idx % 2 !== 0);
        });
    }

    // 2. Render Topics
    renderTopicCloud(data.topics);

    // 3. Render Emotions Chart
    updateEmotionChart(data.emotions);

    // 4. Render Summary Report Markdown
    renderExecutiveSummary(data.summary);
}

// Append bubble to transcript feed
function appendTranscriptBubble(speaker, text, timestamp, isAlt = false) {
    const bubble = document.createElement('div');
    bubble.className = `transcript-bubble ${isAlt ? 'speaker-alt' : ''}`;
    
    bubble.innerHTML = `
        <div class="bubble-meta">
            <span class="bubble-speaker">${speaker}</span>
            <span class="bubble-time">${timestamp}</span>
        </div>
        <div class="bubble-text">${text}</div>
    `;
    
    transcriptFeed.appendChild(bubble);
    
    // Auto-scroll transcript container to bottom
    transcriptFeed.scrollTop = transcriptFeed.scrollHeight;
}

// Render dynamic colored tag cloud
function renderTopicCloud(topics) {
    if (!topics || topics.length === 0) return;
    
    topicEmptyState.classList.add('hidden');
    topicCloud.innerHTML = '';
    
    topics.forEach(topic => {
        const tag = document.createElement('span');
        tag.className = 'topic-tag';
        tag.textContent = topic.text;
        
        // Dynamically size fonts based on relevancy metric
        const sizeVal = 0.75 + (topic.value / 100) * 0.5; 
        tag.style.fontSize = `${sizeVal}rem`;
        
        // Assign random subtle borders for color depth
        const hue = 180 + Math.random() * 90; // cyan-purple spectrum
        tag.style.borderColor = `hsla(${hue}, 80%, 50%, 0.3)`;
        
        topicCloud.appendChild(tag);
    });
}

// Clean UI Utility
function removeEmptyState(container) {
    const emptyState = container.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }
}

// Render Markdown to HTML in Summary Panel
function renderExecutiveSummary(markdownText) {
    if (!markdownText) return;
    summaryEmptyState.classList.add('hidden');
    
    // Custom Mini-Markdown Compiler
    let html = markdownText;
    
    // Headers
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
    
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Unordered lists
    const lines = html.split('\n');
    let inList = false;
    let resultLines = [];
    
    for (let line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('- ')) {
            if (!inList) {
                resultLines.push('<ul>');
                inList = true;
            }
            const itemText = trimmed.substring(2);
            resultLines.push(`<li>${itemText}</li>`);
        } else {
            if (inList) {
                resultLines.push('</ul>');
                inList = false;
            }
            resultLines.push(line);
        }
    }
    if (inList) {
        resultLines.push('</ul>');
    }
    
    summaryReport.innerHTML = resultLines.join('\n');
}

// =========================================================
// CHROME EXTENSION WEB BRIDGE EVENT LISTENERS
// =========================================================
window.addEventListener('message', async (event) => {
    const data = event.data;
    if (!data || !data.type) return;

    if (data.type === 'VIBENOTE_START_SESSION') {
        console.log("Extension requested session start. Details:", data);
        resetDashboardUI();
        
        // Update dashboard options matching extension settings
        if (data.url) meetingUrlInput.value = data.url;
        if (data.industry) industrySelect.value = data.industry;

        try {
            // Step 1: Create active session on backend
            const response = await fetch(`${BACKEND_URL}/api/join`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: data.url, industry: data.industry })
            });
            const resData = await response.json();
            
            if (resData.status === 'success') {
                activeSessionId = resData.session_id;
                
                // Connect/Join SocketIO room
                if (socket && socket.connected) {
                    socket.emit('join_session', { session_id: activeSessionId });
                }

                // Update UI state to recording
                isRecording = true;
                startLiveBtn.innerHTML = `<i class="fa-solid fa-square"></i> Stop Live Session`;
                startLiveBtn.classList.add('recording');
                liveIndicator.classList.remove('hidden');
                console.log(`Extension Session Initiated: ${activeSessionId}`);
            }
        } catch (e) {
            console.error("Failed to start session from extension request:", e);
        }
    } 
    
    else if (data.type === 'VIBENOTE_AUDIO_CHUNK') {
        if (isRecording && activeSessionId && socket && socket.connected) {
            // Forward chunk from extension to WebSocket server
            socket.emit('audio_chunk', {
                session_id: activeSessionId,
                chunk: data.chunk
            });
        }
    } 
    
    else if (data.type === 'VIBENOTE_END_SESSION') {
        console.log("Extension requested session end.");
        if (isRecording) {
            isRecording = false;
            startLiveBtn.innerHTML = `<i class="fa-solid fa-microphone"></i> Start Live Session`;
            startLiveBtn.classList.remove('recording');
            liveIndicator.classList.add('hidden');

            if (activeSessionId) {
                try {
                    startLiveBtn.disabled = true;
                    startLiveBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Finalizing...`;
                    
                    const response = await fetch(`${BACKEND_URL}/api/end`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ session_id: activeSessionId })
                    });
                    
                    const resData = await response.json();
                    if (resData.status === 'success') {
                        displayFinalReport(resData);
                    }
                } catch (err) {
                    console.error("Error ending session from extension request:", err);
                } finally {
                    startLiveBtn.disabled = false;
                    startLiveBtn.innerHTML = `<i class="fa-solid fa-microphone"></i> Start Live Session`;
                    activeSessionId = null;
                }
            }
        }
    }
});

