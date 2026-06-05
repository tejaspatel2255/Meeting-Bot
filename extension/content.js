/**
 * VibeNote Extension Content Script
 * Acts as a secure communication bridge between the extension background service worker
 * and the dashboard page context.
 */

// Listen for messages from background.js
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    // Only forward VIBENOTE prefixed events
    if (message && message.type && message.type.startsWith("VIBENOTE_")) {
        window.postMessage(message, "*");
        sendResponse({ status: "relayed" });
    }
});
