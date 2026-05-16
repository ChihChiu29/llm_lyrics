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

def _get_base_url():
    # 优先遵循官方 OLLAMA_HOST
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    # 如果只有主机名，补充协议
    if not host.startswith(("http://", "https://")):
        host = "http://" + host
    # 去掉尾部斜杠并补充 /api
    return host.rstrip("/") + "/api"

# 尝试从 .env 文件加载环境变量 (使用绝对路径确保可靠)
_current_dir = os.path.dirname(os.path.abspath(__file__))
_env_path = os.path.join(_current_dir, ".env")
if os.path.exists(_env_path):
    try:
        with open(_env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()
    except:
        pass

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", _get_base_url())
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")

class Spinner:
    # ... (remains unchanged)
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

OFFICIAL_OLLAMA_CLOUD_URL = "https://ollama.com/api"

class OllamaClient:
    def __init__(self, model=""):
        self.model = model
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if OLLAMA_API_KEY:
            self.headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"
            # 内部静默确认密钥已加载
            # print(f"DEBUG: Key loaded {OLLAMA_API_KEY[:5]}...") 

    def _get_target_url(self):
        """根据模型名称动态选择目标 URL"""
        if self.model and self.model.endswith(":cloud"):
            return OFFICIAL_OLLAMA_CLOUD_URL
        return OLLAMA_API_URL

    def get_models(self):
        """尝试获取本地模型列表。"""
        try:
            resp = requests.get(f"{OLLAMA_API_URL}/tags", headers=self.headers, timeout=5)
            if resp.status_code == 200:
                return [m['name'] for m in resp.json().get('models', [])]
            return []
        except:
            return []

    def call(self, prompt_text, system_prompt="", stream=True, temperature=0.7, spinner=None):
        target_url = self._get_target_url()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt_text}
            ],
            "stream": stream,
            "options": {"temperature": temperature}
        }
        
        # 调试输出（如果是云端且失败）
        try:
            if spinner: spinner.start()
            resp = requests.post(f"{target_url}/chat", json=payload, headers=self.headers, stream=stream, timeout=180)
            
            # 如果是 403/401，可能是需要通过 ollama cli 运行或缺少云端密钥
            if resp.status_code in [401, 403]:
                if spinner: spinner.stop()
                print(f"\n\033[33m提示: 访问受阻 ({resp.status_code})。目标: {target_url}")
                if target_url == OFFICIAL_OLLAMA_CLOUD_URL:
                    key_status = f"已加载(前5位: {OLLAMA_API_KEY[:5]})" if OLLAMA_API_KEY else "未找到(请检查 .env)"
                    print(f"云端认证状态: {key_status}")
                    print(f"请确保密钥有效且具有该模型的访问权限。")
                else:
                    print(f"如果你已通过 'ollama login' 登录，请确保设置了正确的 OLLAMA_HOST。\033[0m")
                return ""

            resp.raise_for_status()

            if not stream:
                if spinner: spinner.stop()
                return resp.json().get('message', {}).get('content', '').strip()

            full_content = ""
            is_first_chunk = True
            for line in resp.iter_lines():
                if not line: continue
                try:
                    chunk = json.loads(line)
                except:
                    continue
                    
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
