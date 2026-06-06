document.addEventListener('DOMContentLoaded', async () => {
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const serverUrlInput = document.getElementById('serverUrl');
    const industrySelect = document.getElementById('industry');
    const tabUrlEl = document.getElementById('tabUrl');
    const dashboardLink = document.getElementById('dashboardLink');

    // 1. Query active tab to show URL
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs && tabs.length > 0) {
            const currentTab = tabs[0];
            if (tabUrlEl) {
                tabUrlEl.textContent = currentTab.url.substring(0, 45) + (currentTab.url.length > 45 ? '...' : '');
            }
        }
    });

    // 2. Restore previous settings and state
    chrome.storage.local.get(['isCapturing', 'serverUrl', 'industry', 'statusText'], (res) => {
        if (res.serverUrl) serverUrlInput.value = res.serverUrl;
        if (res.industry) industrySelect.value = res.industry;
        
        if (res.isCapturing) {
            setUIState('Live');
        } else {
            setUIState(res.statusText || 'Stopped');
        }
    });

    // 3. Listen for clicks
    startBtn.addEventListener('click', () => {
        const serverUrl = serverUrlInput.value.trim();
        const industry = industrySelect.value;

        // Save preferences
        chrome.storage.local.set({ serverUrl, industry });

        setUIState('Connecting');

        // Send start message to background
        chrome.runtime.sendMessage({
            action: "START_CAPTURE",
            serverUrl: serverUrl,
            industry: industry
        }, (response) => {
            if (response && response.status === 'started') {
                setUIState('Live');
            } else {
                setUIState('Stopped');
                alert(response?.error || "Failed to start capture. Make sure you are on a live meeting page and have approved tab capture permissions.");
            }
        });
    });

    stopBtn.addEventListener('click', () => {
        setUIState('Stopped');
        chrome.runtime.sendMessage({ action: "STOP_CAPTURE" });
    });

    // 4. Update UI Status Function
    function setUIState(status) {
        chrome.storage.local.set({ statusText: status, isCapturing: (status === 'Live') });
        statusText.textContent = status;

        if (status === 'Live') {
            startBtn.style.display = 'none';
            stopBtn.style.display = 'block';
            statusDot.className = 'status-dot active';
            statusDot.style.background = '#10b981'; // green
        } else if (status === 'Connecting') {
            startBtn.style.display = 'none';
            stopBtn.style.display = 'block';
            statusDot.className = 'status-dot';
            statusDot.style.background = '#fbbf24'; // amber
        } else {
            startBtn.style.display = 'block';
            stopBtn.style.display = 'none';
            statusDot.className = 'status-dot';
            statusDot.style.background = '#ef4444'; // red
        }
    }
});
