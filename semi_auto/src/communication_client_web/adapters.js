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
    
    // 1. Check for Stop/Generating icon (Square or Pause shape)
    // DeepSeek uses M2 4.88 for the square stop button
    if (html.includes('M2 4.88') || html.includes('ds-loading')) {
      return true;
    }
    
    // 2. Check for Send/Idle icon (Up Arrow)
    // DeepSeek uses M8.3125 or M1.29297 for the up arrow
    if (html.includes('M8.3125') || html.includes('M1.29297')) {
      return false;
    }

    // 3. Fallback: if we see cursors or loading markers in the message area
    const lastMarkdown = document.querySelector('.ds-markdown:last-of-type');
    if (lastMarkdown && (lastMarkdown.querySelector('.ds-markdown-cursor') || lastMarkdown.querySelector('.ds-loading'))) {
      return true;
    }

    // If we are not sure, we'll keep waiting (returning true) 
    // unless we see an explicit Send button icon.
    return true; 
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
    
    // Explicit stop button
    if (sendButton.classList.contains('stop-button') || sendButton.innerText.includes('停止') || sendButton.innerText.includes('Stop')) return true;
    
    // Explicit send button
    if (sendButton.classList.contains('send-button') && !sendButton.disabled) return false;

    // Loading dots or similar
    if (document.querySelector('.ant-spin, .loading-dots')) return true;

    const disabled = sendButton.disabled || sendButton.hasAttribute('disabled');
    return disabled;
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
