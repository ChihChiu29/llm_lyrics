// content.js

const SERVER_URL = 'http://localhost:8080';

// Note: These selectors are speculative and might need updates based on DeepSeek's exact DOM structure.
const SELECTORS = {
  chatInput: '#chat-input', // Update this based on actual DeepSeek UI
  sendButton: '.ds-icon-button', // Update this based on actual DeepSeek UI (the send icon)
  responseBlocks: '.ds-markdown', // Update this based on actual DeepSeek UI
  stopGeneratingButton: '.ds-stop-generating' // To detect if it's still running
};

let currentInteraction = null;
let checkInterval = null;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'process_interaction') {
    currentInteraction = message.interaction;
    processInteraction(currentInteraction);
    sendResponse({ received: true });
  }
  return true;
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

    // 2. Input text into DeepSeek UI
    const inputArea = document.querySelector(SELECTORS.chatInput);
    if (!inputArea) {
      throw new Error('Chat input not found');
    }

    // Set value and trigger input event for React/Vue to pick it up
    inputArea.value = interaction.input_string;
    inputArea.dispatchEvent(new Event('input', { bubbles: true }));

    // Wait a brief moment before clicking send
    setTimeout(() => {
      const sendButton = document.querySelector(SELECTORS.sendButton);
      if (sendButton && !sendButton.disabled) {
        sendButton.click();
        
        // 3. Periodically check if response is ready (every 10 seconds)
        checkInterval = setInterval(checkResponseReady, 10000);
      } else {
        throw new Error('Send button not found or disabled');
      }
    }, 500);

  } catch (error) {
    console.error('Error during processing:', error);
    failInteraction();
  }
}

function checkResponseReady() {
  // A heuristic to check if it's still generating:
  // Usually there's a "stop generating" button or the send button is disabled.
  const isGenerating = document.querySelector(SELECTORS.stopGeneratingButton) !== null;
  const sendButton = document.querySelector(SELECTORS.sendButton);
  const isSendDisabled = sendButton && sendButton.disabled;
  
  // If it's not generating and the send button is available again, it should be done.
  if (!isGenerating && !isSendDisabled) {
    clearInterval(checkInterval);
    extractAndSubmitResponse();
  }
}

async function extractAndSubmitResponse() {
  try {
    // Get all response blocks
    const responseBlocks = document.querySelectorAll(SELECTORS.responseBlocks);
    if (responseBlocks.length === 0) {
      throw new Error('No responses found on the page');
    }

    // Extract the text from the last response block
    const lastResponse = responseBlocks[responseBlocks.length - 1];
    const responseText = lastResponse.innerText;

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
