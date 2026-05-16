// background.js

const SERVER_URL = 'http://localhost:8080';
let isProcessing = false;

chrome.runtime.onInstalled.addListener(() => {
  // Poll every 1 minute
  chrome.alarms.create('pollServer', { periodInMinutes: 1 });
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'pollServer') {
    pollServer();
  }
});

async function pollServer() {
  if (isProcessing) {
    console.log('Currently processing, skip polling.');
    return;
  }

  try {
    const response = await fetch(`${SERVER_URL}/api/interaction/next`);
    if (response.ok) {
      const data = await response.json();
      if (data && data.status === 'PENDING') {
        console.log('Found new interaction:', data);
        startProcessing(data);
      }
    }
  } catch (error) {
    console.error('Error polling server:', error);
  }
}

async function startProcessing(interaction) {
  isProcessing = true;
  
  // Find DeepSeek tab
  chrome.tabs.query({ url: "*://chat.deepseek.com/*" }, (tabs) => {
    if (tabs.length === 0) {
      console.error('DeepSeek tab not found. Cannot process interaction.');
      isProcessing = false;
      return;
    }
    
    const tabId = tabs[0].id;
    chrome.tabs.sendMessage(tabId, {
      action: 'process_interaction',
      interaction: interaction
    }, (response) => {
      if (chrome.runtime.lastError) {
        console.error('Error sending message to content script:', chrome.runtime.lastError);
        isProcessing = false;
      }
    });
  });
}

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'interaction_completed') {
    console.log('Interaction completed successfully.');
    isProcessing = false;
    // Check for another interaction immediately
    pollServer();
    sendResponse({ success: true });
  } else if (message.action === 'interaction_failed') {
    console.error('Interaction failed.');
    isProcessing = false;
    sendResponse({ success: true });
  }
  return true;
});
