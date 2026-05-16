// adapters.js

class DeepSeekAdapter {
  constructor() {
    this.name = 'DeepSeek';
  }

  getChatInput() {
    return document.querySelector('textarea.ds-scroll-area, textarea[placeholder*="DeepSeek"], textarea[name="search"]');
  }

  getSendButton(inputArea) {
    const parent = inputArea.closest('div').parentElement;
    if (parent) {
      const buttons = parent.querySelectorAll('div[role="button"]');
      return buttons.length ? buttons[buttons.length - 1] : null;
    }
    return null;
  }

  isGenerating(inputArea, sendButton) {
    if (!sendButton) return false;
    const html = sendButton.innerHTML;
    if (html.includes('M2 4.88') || html.includes('ds-loading')) return true;
    const blocks = document.querySelectorAll('.ds-markdown');
    if (blocks.length) {
      const last = blocks[blocks.length - 1];
      if (last.querySelector('.ds-markdown-cursor, .blinking-cursor')) return true;
    }
    if (html.includes('M8.3125')) return false;
    const disabled = sendButton.disabled || sendButton.classList.contains('ds-icon-button--disabled') || sendButton.hasAttribute('disabled');
    return !disabled && inputArea.value.trim() === '';
  }

  extractResponse() {
    const blocks = document.querySelectorAll('div.ds-markdown.ds-assistant-message-main-content, .ds-markdown');
    if (!blocks.length) throw new Error('No responses found on the page');
    return blocks[blocks.length - 1].innerText;
  }
}

class QwenAdapter {
  constructor() {
    this.name = 'Qwen';
  }

  getChatInput() {
    return document.querySelector('textarea.message-input-textarea');
  }

  getSendButton(inputArea) {
    const parent = inputArea.closest('div').parentElement;
    if (parent) {
      const btn = parent.querySelector('button.send-button') || parent.querySelector('button.stop-button');
      return btn || null;
    }
    return null;
  }

  isGenerating(inputArea, sendButton) {
    if (!sendButton) return false;
    if (sendButton.classList.contains('stop-button')) return true;
    const disabled = sendButton.disabled || sendButton.hasAttribute('disabled');
    return !disabled && inputArea.value.trim() === '';
  }

  extractResponse() {
    const blocks = document.querySelectorAll('.qwen-chat-message-assistant');
    if (!blocks.length) throw new Error('No responses found on the page');
    return blocks[blocks.length - 1].innerText;
  }
}

// Expose adapters to content script
window.LLM_ADAPTERS = [
  { matches: (hostname) => hostname.includes('chat.deepseek.com'), AdapterClass: DeepSeekAdapter },
  { matches: (hostname) => hostname.includes('qwen.ai'), AdapterClass: QwenAdapter }
];
