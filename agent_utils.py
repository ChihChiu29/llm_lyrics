import os
import re
import sys
import json
import glob
import requests
import threading
import time
import datetime
from prompt_toolkit import prompt
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings

OLLAMA_API_URL = "http://localhost:11434/api"

class Spinner:
    def __init__(self, message="制作人正在思考"):
        self.message = message
        self.stop_spinner = False
        self.thread = None
        self.C_CYAN = "\033[36m"
        self.C_RESET = "\033[0m"

    def _spin(self):
        chars = ["|", "/", "-", "\\"]
        idx = 0
        while not self.stop_spinner:
            sys.stdout.write(f"\r{self.C_CYAN}[{self.message}... {chars[idx % len(chars)]}]{self.C_RESET}")
            sys.stdout.flush()
            time.sleep(0.1)
            idx += 1
        sys.stdout.write("\r" + " " * 75 + "\r")
        sys.stdout.flush()

    def start(self):
        self.stop_spinner = False
        self.thread = threading.Thread(target=self._spin)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.stop_spinner = True
        if self.thread:
            self.thread.join(timeout=2.0)

class OllamaClient:
    def __init__(self, model=""):
        self.model = model

    def get_models(self):
        try:
            resp = requests.get(f"{OLLAMA_API_URL}/tags", timeout=5)
            resp.raise_for_status()
            return [m['name'] for m in resp.json().get('models', [])]
        except:
            return []

    def call(self, prompt_text, system_prompt="", stream=True, temperature=0.7, spinner=None):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_text}
            ],
            "stream": stream,
            "options": {"temperature": temperature}
        }
        try:
            if spinner: spinner.start()
            resp = requests.post(f"{OLLAMA_API_URL}/chat", json=payload, stream=stream, timeout=120)
            resp.raise_for_status()

            if not stream:
                if spinner: spinner.stop()
                return resp.json().get('message', {}).get('content', '').strip()

            full_content = ""
            is_first_chunk = True
            for line in resp.iter_lines():
                if not line: continue
                chunk = json.loads(line)
                message = chunk.get('message', {})
                content = message.get('content', '')
                reasoning = message.get('reasoning_content', '')

                if (content or reasoning) and spinner:
                    spinner.stop()

                if reasoning:
                    if is_first_chunk:
                        print("\033[90m[逻辑分析中...]\033[0m", end='', flush=True)
                        is_first_chunk = False
                    continue

                if content:
                    if is_first_chunk:
                        print("\033[32m[制作人回复]:\033[0m ", end='', flush=True)
                        is_first_chunk = False
                    full_content += content
                    print(content, end='', flush=True)
            
            if spinner: spinner.stop()
            print()
            return full_content
        except Exception as e:
            if spinner: spinner.stop()
            print(f"\n\033[33m错误: {e}\033[0m")
            return ""

    def check_intent(self, user_input, song_title, stage_desc):
        normalized = user_input.lower().strip(" .!！?？。")
        # 显式拦截
        if normalized.startswith(("/c ", "/chat ")):
            return "CHAT", user_input.split(' ', 1)[1]
        if normalized in ["/c", "/chat"]: return "CHAT", ""
        
        # 基础匹配
        approvals = ['ok', 'go', 'yes', 'y', 'fine', 'good', '好的', '可以', '成了', '满意', '批准', '通过']
        if normalized in approvals: return "APPROVE", user_input
        
        chat_keywords = ['吗', '呢', '呗', '为什么', '如何', '评价', '分析', '觉得', '理由']
        if any(word in normalized for word in chat_keywords) and ('?' in user_input or '？' in user_input):
            return "CHAT", user_input

        # LLM 判定
        check_prompt = f"判断意图。歌曲:《{song_title}》。当前处于: {stage_desc}。输入: '{user_input}'。仅仅回答单词: CHAT, MODIFY 或 APPROVE。"
        result = self.call(check_prompt, stream=False, temperature=0)
        if "APPROVE" in result.upper(): return "APPROVE", user_input
        if "MODIFY" in result.upper(): return "MODIFY", user_input
        return "CHAT", user_input

def handle_rich_input(prompt_text, multiline=True):
    # 如果不是终端，回退到基础 input()
    if not sys.stdin.isatty():
        try:
            print(f"\033[32m{prompt_text}\033[0m", end=" ", flush=True)
            return sys.stdin.readline().strip()
        except (KeyboardInterrupt, EOFError):
            return "/quit"

    kb = KeyBindings()
    @kb.add('enter')
    def _(event): event.current_buffer.validate_and_handle()
    @kb.add('c-j')
    def _(event): event.current_buffer.insert_text('\n')
    
    pt_prompt = ANSI(f"\033[32m{prompt_text}\033[0m ")
    try:
        user_input = prompt(pt_prompt, multiline=multiline, key_bindings=kb).strip()
        return user_input
    except (KeyboardInterrupt, EOFError):
        return "/quit"
