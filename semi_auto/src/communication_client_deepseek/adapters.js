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
    if (!sendButton) return false;
    
    const html = sendButton.innerHTML;
    
    // 1. Check if the button shows the "Stop" square icon (M2 4.88...) or a loading spinner
    if (html.includes('M2 4.88') || html.includes('ds-loading')) {
      return true;
    }
    
    // 2. Check if there's a blinking cursor in the last message block
    const responseBlocks = document.querySelectorAll('.ds-markdown');
    if (responseBlocks.length > 0) {
      const lastBlock = responseBlocks[responseBlocks.length - 1];
      if (lastBlock.querySelector('.ds-markdown-cursor, .blinking-cursor')) {
        return true;
      }
    }
    
    // 3. If the button shows the "Send" up-arrow (M8.3125...), it's definitely finished or idle
    if (html.includes('M8.3125')) {
      return false;
    }

    // Fallback: If not disabled and textarea is empty, it might still be generating
    const isSendDisabled = sendButton.disabled || sendButton.classList.contains('ds-icon-button--disabled') || sendButton.hasAttribute('disabled');
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
