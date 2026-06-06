// VibeNote Offscreen Document Script
// Handles WebRTC stream capture and MediaRecorder slice processing.

let mediaRecorder = null;
let audioStream = null;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log("Offscreen received action:", message.action);

    if (message.action === 'start_capture') {
        const streamId = message.streamId;
        
        navigator.mediaDevices.getUserMedia({
            audio: {
                mandatory: {
                    chromeMediaSource: 'tabCapture',
                    chromeMediaSourceId: streamId
                }
            },
            video: false
        }).then((stream) => {
            audioStream = stream;

            // Maintain loopback so user can still hear their tab audio
            try {
                const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const source = audioContext.createMediaStreamSource(stream);
                source.connect(audioContext.destination);
            } catch (err) {
                console.error("Audio Context Loopback failed:", err);
            }

            // Start recording audio slices (1 second durations)
            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            mediaRecorder.ondataavailable = (event) => {
                if (event.data && event.data.size > 0) {
                    const reader = new FileReader();
                    reader.onloadend = () => {
                        const base64Audio = reader.result.split(',')[1];
                        
                        // Send chunk back to service worker background.js
                        chrome.runtime.sendMessage({
                            action: "audio_chunk",
                            chunk: base64Audio
                        });
                    };
                    reader.readAsDataURL(event.data);
                }
            };
            
            mediaRecorder.start(1000);
            console.log("MediaRecorder successfully started on tab stream.");
        }).catch((err) => {
            console.error("navigator.mediaDevices.getUserMedia failed in offscreen:", err);
        });
    }
    
    else if (message.action === 'stop_capture') {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
        if (audioStream) {
            audioStream.getTracks().forEach(track => track.stop());
        }
        console.log("MediaRecorder and streams stopped.");
    }
});
