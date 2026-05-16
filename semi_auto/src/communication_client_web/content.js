// content.js
console.log('LLM Communication Client: Content script loaded and ready.');
const SERVER_URL = 'http://localhost:9223';

let currentInteraction = null;
let checkInterval = null;
let adapter = null;

// Initialize adapter
function initAdapter() {
  const hostname = window.location.hostname;
  const adapterDef = window.LLM_ADAPTERS.find(def => def.matches(hostname));
  if (adapterDef) {
    adapter = new adapterDef.AdapterClass();
    console.log(`Initialized adapter for ${adapter.name}`);
  } else {
    console.error('No suitable adapter found for this webpage.');
  }
}

initAdapter();

// Listen for messages from background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'process_interaction') {
    if (!adapter) {
      console.error('Cannot process interaction without an adapter.');
      sendResponse({ received: false, error: 'No adapter' });
      return;
    }
    // Ensure the interaction is intended for this client
    if (message.interaction && message.interaction.client &&
        message.interaction.client.toLowerCase() !== adapter.name.toLowerCase()) {
      console.warn('Interaction client mismatch (', message.interaction.client, ') vs adapter', adapter.name);
      sendResponse({ received: false, error: 'Client mismatch' });
      return;
    }
    currentInteraction = message.interaction;
    processInteraction(currentInteraction);
    sendResponse({ received: true });
  }
});

async function processInteraction(interaction) {
  console.log('Processing interaction:', interaction.id);

  try {
    // 1. Update status to RUNNING
    await fetch(`${SERVER_URL}/api/interaction/next`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'RUNNING' })
    });

    // 2. Input text into UI
    const inputArea = adapter.getChatInput();
    if (!inputArea) {
      throw new Error('Chat input not found');
    }

    // Set value and trigger input event for React/Vue to pick it up
    inputArea.value = interaction.input_string;
    inputArea.dispatchEvent(new Event('input', { bubbles: true }));

    // Wait at least 5 seconds before starting to check (as requested)
    setTimeout(() => {
      const sendButton = adapter.getSendButton(inputArea);
      if (sendButton) {
        sendButton.click();
        
        // 3. Periodically check if response is ready (every 5 seconds)
        console.log('Interaction sent. Waiting 5 seconds before first check...');
        setTimeout(() => {
           checkInterval = setInterval(checkResponseReady, 5000);
        }, 5000);
      } else {
        throw new Error('Send button not found');
      }
    }, 500);

  } catch (error) {
    console.error('Error during processing:', error);
    failInteraction();
  }
}

function checkResponseReady() {
  const inputArea = adapter.getChatInput();
  if (!inputArea) return;

  const sendButton = adapter.getSendButton(inputArea);

  if (!adapter.isGenerating(inputArea, sendButton)) {
    clearInterval(checkInterval);
    extractAndSubmitResponse();
  }
}

async function extractAndSubmitResponse() {
  try {
    const responseText = adapter.extractResponse();

    // 4. Update the interaction with the response and set status to COMPLETED
    await fetch(`${SERVER_URL}/api/interaction/next`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status: 'COMPLETED',
        output_string: responseText
      })
    });

    console.log('Successfully completed interaction:', currentInteraction.id);
    currentInteraction = null;
    chrome.runtime.sendMessage({ action: 'interaction_completed' });

  } catch (error) {
    console.error('Error extracting response:', error);
    failInteraction();
  }
}

async function failInteraction() {
  if (currentInteraction) {
    try {
      await fetch(`${SERVER_URL}/api/interaction/next`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'FAILED' })
      });
    } catch (e) {
      console.error('Failed to notify server of failure:', e);
    }
  }
  currentInteraction = null;
  chrome.runtime.sendMessage({ action: 'interaction_failed' });
}
