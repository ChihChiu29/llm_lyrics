// background.js
console.log('LLM Communication Client: Background service worker started.');
const SERVER_URL = 'http://localhost:8080';
let isProcessing = false;
let processingTimeout = null;
let enabledTabIds = new Set();

const CLIENT_URL_MAP = {
  'deepseek': '*://chat.deepseek.com/*',
  'chatgpt': '*://chatgpt.com/*',
  'claude': '*://claude.ai/*',
  'qwen': '*://*.qwen.ai/*'
};

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
chrome.storage.local.get(['enabledTabIds'], (result) => {
  if (result.enabledTabIds) {
    enabledTabIds = new Set(result.enabledTabIds);
  }
  
  // Initialize badges for all active tabs
  chrome.tabs.query({}, (tabs) => {
    for (const tab of tabs) {
      updateBadge(tab.id);
    }
  });
  
  if (enabledTabIds.size > 0) {
    pollServer(); // Poll immediately on startup if any tabs are enabled
  }
});

function updateBadge(tabId) {
  const isEnabled = enabledTabIds.has(tabId);
  chrome.action.setBadgeText({ text: isEnabled ? "ON" : "OFF", tabId: tabId });
  chrome.action.setBadgeBackgroundColor({ color: isEnabled ? "#4CAF50" : "#F44336", tabId: tabId });
}

chrome.action.onClicked.addListener(async (tab) => {
  const tabId = tab.id;
  if (enabledTabIds.has(tabId)) {
    enabledTabIds.delete(tabId);
  } else {
    enabledTabIds.add(tabId);
  }
  
  await chrome.storage.local.set({ enabledTabIds: Array.from(enabledTabIds) });
  updateBadge(tabId);
  console.log(`Tab ${tabId} toggled. Now enabled = ${enabledTabIds.has(tabId)}`);
  
  if (enabledTabIds.has(tabId)) {
    pollServer(); // Kick off a poll immediately if a tab was turned on
  }
});

// Clean up closed tabs to prevent memory leaks in storage
chrome.tabs.onRemoved.addListener((tabId) => {
  if (enabledTabIds.has(tabId)) {
    enabledTabIds.delete(tabId);
    chrome.storage.local.set({ enabledTabIds: Array.from(enabledTabIds) });
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
  if (enabledTabIds.size > 0) {
    pollServer();
  }
}, 15000);

async function pollServer() {
  if (enabledTabIds.size === 0) {
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
  const targetClient = (interaction.client || 'deepseek').toLowerCase();
  const targetUrl = CLIENT_URL_MAP[targetClient];
  
  if (!targetUrl) {
    console.error(`Unknown client requested: ${targetClient}`);
    setProcessing(false);
    return;
  }
  
  // Find a supported tab for the requested client
  chrome.tabs.query({ url: [targetUrl] }, async (tabs) => {
    // Filter to only ENABLED tabs
    const activeTabs = tabs.filter(t => enabledTabIds.has(t.id));
    
    if (activeTabs.length === 0) {
      console.log('Waiting for a supported tab to be opened and ENABLED...');
      setProcessing(false);
      return;
    }
    
    // Try sending to tabs sequentially until one succeeds
    let success = false;
    for (const tab of activeTabs) {
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
