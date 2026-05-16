// background.js
console.log('LLM Communication Client: Background service worker started.');
const SERVER_URL = 'http://localhost:8080';
let isProcessing = false;
let processingTimeout = null;
let isEnabled = true;

function setProcessing(state) {
  isProcessing = state;
  if (state) {
    // Reset processing state after 5 minutes to prevent permanent hangs
    processingTimeout = setTimeout(() => {
      if (isProcessing) {
        console.warn('Processing timed out after 5 minutes. Resetting state.');
        isProcessing = false;
      }
    }, 5 * 60 * 1000);
  } else {
    if (processingTimeout) {
      clearTimeout(processingTimeout);
      processingTimeout = null;
    }
  }
}

// Initialize state from storage
chrome.storage.local.get(['isEnabled'], (result) => {
  if (result.isEnabled !== undefined) {
    isEnabled = result.isEnabled;
  }
  updateBadge();
  if (isEnabled) {
    pollServer(); // Poll immediately on startup
  }
});

function updateBadge() {
  const text = isEnabled ? "ON" : "OFF";
  const color = isEnabled ? "#4CAF50" : "#F44336"; // Green / Red
  chrome.action.setBadgeText({ text: text });
  chrome.action.setBadgeBackgroundColor({ color: color });
}

chrome.action.onClicked.addListener(async (tab) => {
  isEnabled = !isEnabled;
  await chrome.storage.local.set({ isEnabled: isEnabled });
  updateBadge();
  console.log(`Extension toggled. Now isEnabled = ${isEnabled}`);
  
  if (isEnabled) {
    pollServer(); // Kick off a poll immediately if turned back on
  }
});

chrome.runtime.onInstalled.addListener(() => {
  // Poll every 1 minute
  chrome.alarms.create('pollServer', { periodInMinutes: 1 });
  updateBadge();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'pollServer') {
    pollServer();
  }
});

// Set a 15-second interval for frequent polling while the service worker is awake.
// The 1-minute alarm above ensures the service worker wakes back up if Chrome suspends it.
setInterval(() => {
  if (isEnabled) {
    pollServer();
  }
}, 15000);

async function pollServer() {
  if (!isEnabled) {
    return;
  }

  if (isProcessing) {
    console.log('Currently processing, skip polling.');
    return;
  }

  try {
    const response = await fetch(`${SERVER_URL}/api/interaction/next`);
    if (response.ok) {
      const data = await response.json();
      if (data && data.status === 'PENDING') {
        console.log('Found interaction to process:', data);
        startProcessing(data);
      } else {
        console.log(`Polled server at ${new Date().toLocaleTimeString()}: No pending tasks.`);
      }
    }
  } catch (error) {
    console.error('Error polling server:', error);
  }
}

async function startProcessing(interaction) {
  setProcessing(true);
  
  // Find a supported tab. For now, we only have the DeepSeek adapter implemented.
  chrome.tabs.query({ url: ["*://chat.deepseek.com/*"] }, async (tabs) => {
    if (tabs.length === 0) {
      console.log('Waiting for a supported tab to be opened/enabled...');
      setProcessing(false);
      return;
    }
    
    // Try sending to tabs sequentially until one succeeds
    let success = false;
    for (const tab of tabs) {
      try {
        const response = await chrome.tabs.sendMessage(tab.id, {
          action: 'process_interaction',
          interaction: interaction
        });
        
        if (response && response.received) {
          console.log(`Successfully handed off to tab ${tab.id}`);
          success = true;
          break; // Stop after first successful handoff
        }
      } catch (err) {
        console.log(`Skipped tab ${tab.id}:`, err.message);
      }
    }

    if (!success) {
      console.log('Waiting for a supported tab to be fully loaded (content script not injected yet)...');
      setProcessing(false);
    }
  });
}

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'interaction_completed') {
    console.log('Interaction completed successfully.');
    setProcessing(false);
    // Check for another interaction immediately
    pollServer();
    sendResponse({ success: true });
  } else if (message.action === 'interaction_failed') {
    console.error('Interaction failed.');
    setProcessing(false);
    sendResponse({ success: true });
  }
  return true;
});
