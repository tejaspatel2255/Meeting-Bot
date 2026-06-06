/**
 * VibeNote Extension Content Script
 * 1. Performs DOM-based active speaker detection on Google Meet, Zoom, and Teams.
 * 2. Acts as a secure communication bridge for the localhost dashboard.
 */

let lastActiveSpeaker = null;

// Periodically check for active speaker changes in the page DOM
setInterval(() => {
    try {
        const activeSpeaker = detectActiveSpeaker();
        if (activeSpeaker && activeSpeaker !== lastActiveSpeaker) {
            lastActiveSpeaker = activeSpeaker;
            chrome.runtime.sendMessage({
                action: "SPEAKER_CHANGE",
                speaker: activeSpeaker
            });
            console.log("[VibeNote Content] Speaker changed to:", activeSpeaker);
        }
    } catch (e) {
        // Silent catch to prevent errors disrupting host pages
    }
}, 1000);

// Detect active speaker name based on current web platform
function detectActiveSpeaker() {
    const url = window.location.href.toLowerCase();

    // 1. Google Meet active speaker detection
    if (url.includes("meet.google.com")) {
        // Look for participant elements that indicate audio/speaking activity
        const talkingIndicators = document.querySelectorAll('[data-visual-talking="true"], .n71d0c');
        for (const indicator of talkingIndicators) {
            // Find participant name adjacent/inside the active element
            const nameEl = indicator.querySelector('[data-self-name]') || 
                           indicator.querySelector('.P9GL63') || 
                           indicator.querySelector('.ZjO1Wc') ||
                           indicator.closest('[data-participant-id]')?.querySelector('.P9GL63');
            
            if (nameEl) {
                const name = nameEl.textContent || nameEl.getAttribute('data-self-name');
                if (name && name.trim()) return name.trim();
            }
        }
    }

    // 2. Zoom web client active speaker detection
    else if (url.includes("zoom.us")) {
        const activeSpeakerEl = document.querySelector('.active-speaker-name, .speaker-name, .avatar-name');
        if (activeSpeakerEl && activeSpeakerEl.textContent && activeSpeakerEl.textContent.trim()) {
            return activeSpeakerEl.textContent.trim();
        }
        
        // Check for participant talking indicator class
        const talkingItem = document.querySelector('.talking, .is-talking');
        if (talkingItem) {
            const nameEl = talkingItem.querySelector('.participant-name, .name');
            if (nameEl && nameEl.textContent && nameEl.textContent.trim()) {
                return nameEl.textContent.trim();
            }
        }
    }

    // 3. Microsoft Teams web active speaker detection
    else if (url.includes("teams.microsoft.com") || url.includes("teams.live.com")) {
        const activeSpeakerEl = document.querySelector('[data-tid="active-speaker"], .active-speaker-card, .speaker-name');
        if (activeSpeakerEl && activeSpeakerEl.textContent && activeSpeakerEl.textContent.trim()) {
            return activeSpeakerEl.textContent.trim();
        }
        
        // Teams often highlights participant container border when speaking
        const speakingCard = document.querySelector('.speaking, .is-speaking');
        if (speakingCard) {
            const nameEl = speakingCard.querySelector('.participant-name, [data-tid="participant-name"]');
            if (nameEl && nameEl.textContent && nameEl.textContent.trim()) {
                return nameEl.textContent.trim();
            }
        }
    }

    return null;
}

// Relaying dashboard communication bridge messages (VIBENOTE prefixed events)
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message && message.type && message.type.startsWith("VIBENOTE_")) {
        window.postMessage(message, "*");
        sendResponse({ status: "relayed" });
    }
});
