// adapters.js

class DeepSeekAdapter {
  constructor() {
    this.name = 'DeepSeek';
  }

  getChatInput() {
    return document.querySelector('textarea.ds-scroll-area, textarea[placeholder*="DeepSeek"], textarea[name="search"]');
  }

  getSendButton(inputArea) {
    const parentContainer = inputArea.closest('div').parentElement;
    if (parentContainer) {
      const buttons = parentContainer.querySelectorAll('div[role="button"]');
      if (buttons.length > 0) {
        return buttons[buttons.length - 1];
      }
    }
    return null;
  }

  isGenerating(inputArea, sendButton) {
    // - Generating: Send button is ENABLED (acts as Stop button) and textarea is EMPTY.
    // - Finished: Send button is DISABLED (waiting for input) and textarea is EMPTY.
    const isSendDisabled = sendButton && (sendButton.disabled || sendButton.classList.contains('ds-icon-button--disabled'));
    
    // It's generating if it's NOT disabled and the textarea is empty
    return !isSendDisabled && inputArea.value.trim() === '';
  }

  extractResponse() {
    const responseBlocks = document.querySelectorAll('div.ds-markdown.ds-assistant-message-main-content, .ds-markdown');
    if (responseBlocks.length === 0) {
      throw new Error('No responses found on the page');
    }
    // Extract the text from the last response block
    const lastResponse = responseBlocks[responseBlocks.length - 1];
    return lastResponse.innerText;
  }
}

// Global window object to expose to content.js
window.LLM_ADAPTERS = [
  {
    matches: (hostname) => hostname.includes('chat.deepseek.com'),
    AdapterClass: DeepSeekAdapter
  }
];
