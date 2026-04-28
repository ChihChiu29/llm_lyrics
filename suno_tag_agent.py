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

class SunoTagAgent:
    def __init__(self):
        self.model = ""
        self.state = "INIT"
        self.lyrics_original = ""
        self.song_title = ""
        self.safe_title = ""
        self.tagged_lyrics = ""
        self.style_suggestions = ""
        self.version = 0
        self.s_version = 0
        self.in_model_selection = False
        self.stop_spinner = False
        
        # 预设颜色 (ANSI)
        self.C_GRAY = "\033[90m"
        self.C_GREEN = "\033[32m"
        self.C_YELLOW = "\033[33m"
        self.C_CYAN = "\033[36m"
        self.C_RESET = "\033[0m"

    def run(self):
        print(f"{self.C_CYAN}=== SUNO 歌词标注助手 (Ultimate Edition) ==={self.C_RESET}")
        print("提示: 随时输入 /help 查看可用命令")
        print(f"{self.C_GRAY}交互提示: Enter 提交，Ctrl-J 换行，支持方向键移动。{self.C_RESET}")
        
        if not os.path.exists("lyrics_tagged"):
            os.makedirs("lyrics_tagged")
            
        self.resume_workflow()
        
        try:
            while True:
                if self.state == "INIT":
                    self.handle_init()
                elif self.state == "INPUT_TITLE":
                    self.handle_input_title()
                elif self.state == "INPUT_LYRICS":
                    self.handle_input_lyrics()
                elif self.state == "TAGGING":
                    self.handle_tagging()
                elif self.state == "STYLE_DISCUSSION":
                    self.handle_style_discussion()
                elif self.state == "ENDING":
                    self.handle_ending()
        except KeyboardInterrupt:
            self.stop_spinner = True
            print(f"\n\n{self.C_YELLOW}[中断]{self.C_RESET} 程序已安全退出。")
            sys.exit(0)

    def spinner_task(self, message="制作人正在思考"):
        chars = ["|", "/", "-", "\\"]
        idx = 0
        while not self.stop_spinner:
            sys.stdout.write(f"\r{self.C_CYAN}[{message}... {chars[idx % len(chars)]}]{self.C_RESET}")
            sys.stdout.flush()
            time.sleep(0.1)
            idx += 1
        sys.stdout.write("\r" + " " * 75 + "\r")
        sys.stdout.flush()

    def handle_input(self, prompt_text, multiline=True):
        pt_prompt = ANSI(f"{self.C_GREEN}{prompt_text}{self.C_RESET} ")
        kb = KeyBindings()
        
        @kb.add('enter')
        def _(event):
            event.current_buffer.validate_and_handle()

        @kb.add('c-j')
        def _(event):
            event.current_buffer.insert_text('\n')

        while True:
            try:
                user_input = prompt(pt_prompt, multiline=multiline, key_bindings=kb).strip()
            except (KeyboardInterrupt, EOFError):
                return "/quit"

            if not user_input:
                return ""
            
            lines = user_input.split('\n')
            first_line = lines[0].lower().strip()
            
            if first_line == "/quit":
                sys.exit(0)
            if first_line == "/help":
                self.show_help()
                continue
            if first_line == "/model":
                if not self.in_model_selection:
                    self.select_model()
                    if self.song_title:
                        self.save_init()
                    continue
            if first_line == "/new":
                return "/new"
            
            return user_input

    def call_ollama(self, prompt_text, system_prompt="", stream=True, temperature=0.7):
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
            self.stop_spinner = False
            spinner_thread = threading.Thread(target=self.spinner_task)
            spinner_thread.daemon = True
            spinner_thread.start()

            resp = requests.post(f"{OLLAMA_API_URL}/chat", json=payload, stream=stream, timeout=60)
            resp.raise_for_status()
            
            if not stream:
                self.stop_spinner = True
                spinner_thread.join(timeout=1.0)
                return resp.json().get('message', {}).get('content', '').strip()

            full_content = ""
            is_first_chunk = True
            
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                message = chunk.get('message', {})
                
                content = message.get('content', '')
                reasoning = message.get('reasoning_content', '')
                
                # 关键修复：在打印任何内容前，确保动画线程已完全停止并清理
                if (content or reasoning) and not self.stop_spinner:
                    self.stop_spinner = True
                    spinner_thread.join(timeout=2.0) # 等待动画线程退出并清行

                if reasoning:
                    if is_first_chunk:
                        print(f"{self.C_GRAY}[逻辑分析中...]{self.C_RESET}", end='', flush=True)
                        is_first_chunk = False
                    continue

                if content:
                    if is_first_chunk:
                        print(f"{self.C_GREEN}[制作人回复]:{self.C_RESET} ", end='', flush=True)
                        is_first_chunk = False
                    full_content += content
                    print(content, end='', flush=True)
            
            self.stop_spinner = True
            print()
            return full_content
        except Exception as e:
            self.stop_spinner = True
            print(f"\n{self.C_YELLOW}错误: {e}{self.C_RESET}")
            return ""

    def check_intent(self, user_input, stage="内容确认"):
        normalized = user_input.lower().strip(" .!！?？。")
        if normalized.startswith(("/c ", "/chat ")):
            parts = user_input.split(' ', 1)
            return "CHAT", parts[1] if len(parts) > 1 else ""
        if normalized in ["/c", "/chat"]:
            return "CHAT", ""
        
        approvals = ['ok', 'go', 'yes', 'y', 'fine', 'good', '好的', '可以', '成了', '满意', '批准', '通过']
        if normalized in approvals:
            return "APPROVE", user_input
        
        chat_keywords = ['吗', '呢', '呗', '为什么', '如何', '怎么', '评价', '分析', '解释', '觉得', '理由', '建议']
        if any(word in normalized for word in chat_keywords) and ('?' in user_input or '？' in user_input):
            return "CHAT", user_input
        
        check_prompt = f"判断意图。阶段：{stage}。输入: '{user_input}'。仅仅回答: CHAT, MODIFY 或 APPROVE。"
        result = self.call_ollama(check_prompt, stream=False, temperature=0).strip().upper()
        if "APPROVE" in result:
            return "APPROVE", user_input
        if "MODIFY" in result:
            return "MODIFY", user_input
        return "CHAT", user_input

    def show_header(self, title):
        print(f"\n{self.C_CYAN}{'='*40}\n [阶段: {title}] \n{'='*40}{self.C_RESET}")

    def show_help(self):
        print(f"\n{self.C_CYAN}--- SUNO 标注助手: 指令与快捷键手册 ---{self.C_RESET}")
        print(f"\n{self.C_YELLOW}[基础指令]{self.C_RESET}")
        print("  /help          - 显示此详细帮助信息")
        print("  /model         - 随时调出模型列表并进行切换")
        print("  /new           - 放弃当前所有进度，开启一首新歌")
        print("  /quit          - 立即安全退出程序")
        print(f"\n{self.C_YELLOW}[交互快捷键]{self.C_RESET}")
        print("  Enter          - 提交/发送当前输入框中的所有内容")
        print("  Ctrl-J         - 在输入框光标处插入换行")
        print("  方向键         - 在文本中自由移动光标编辑")
        print(f"\n{self.C_YELLOW}[版本回退 (后悔药)]{self.C_RESET}")
        print("  vX  (如 v1)    - 跳回到特定的标注版本 (支持在风格阶段执行)")
        print("  svX (如 sv2)   - 跳回到特定的风格版本")
        print(f"\n{self.C_GRAY}------------------------------------------{self.C_RESET}\n")

    def clear_tmp_files(self):
        for f in glob.glob("tmp_tag_*"):
            try:
                os.remove(f)
            except:
                pass
        self.song_title = ""
        self.safe_title = ""
        self.version = 0
        self.s_version = 0

    def select_model(self):
        try:
            resp = requests.get(f"{OLLAMA_API_URL}/tags", timeout=5)
            resp.raise_for_status()
            models = [m['name'] for m in resp.json().get('models', [])]
        except:
            print(f"{self.C_YELLOW}无法连接 Ollama。{self.C_RESET}")
            return
        if not models:
            return
        print(f"\n{self.C_GRAY}可用模型:{self.C_RESET}")
        for i, m in enumerate(models):
            tag = f"{self.C_CYAN}(当前){self.C_RESET}" if m == self.model else ""
            print(f"{i+1}. {m} {tag}")
        self.in_model_selection = True
        choice = self.handle_input(f"\n选择模型编号 (回车默认/当前): ", multiline=False)
        self.in_model_selection = False
        if choice in ["/new", "/quit"]:
            return
        if not choice:
            if not self.model:
                self.model = models[0]
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                self.model = models[idx]
                print(f"切换至: {self.C_GREEN}{self.model}{self.C_RESET}")
        except:
            if not self.model:
                self.model = models[0]

    def save_init(self):
        with open("tmp_tag_init.md", 'w', encoding='utf-8') as f:
            f.write(f"Model: {self.model}\nTitle: {self.song_title}\n")

    def resume_workflow(self):
        if os.path.exists("tmp_tag_init.md"):
            with open("tmp_tag_init.md", 'r', encoding='utf-8') as f:
                content = f.read()
                m = re.search(r"Model: (.*)", content)
                last_model = m.group(1).strip() if m else ""
                t = re.search(r"Title: (.*)", content)
                if t: 
                    self.song_title = t.group(1).strip()
                    self.safe_title = re.sub(r'[\\/*?:"<>|]', "", self.song_title).replace(" ", "_")
            if last_model:
                print(f"\n{self.C_CYAN}--- 待处理歌曲: {self.C_RESET}{self.song_title}")
                confirm = self.handle_input(f"是否继续使用模型 {self.C_YELLOW}{last_model}{self.C_RESET}? (y/n): ", multiline=False)
                if confirm.lower() in ['y', 'yes', '']:
                    self.model = last_model
                else:
                    self.select_model()
                    self.save_init()

        if self.safe_title:
            v0_file = f"tmp_tag_{self.safe_title}_v00.txt"
            if os.path.exists(v0_file):
                with open(v0_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    parts = content.split('\n\n', 1)
                    self.lyrics_original = parts[1] if len(parts) > 1 else parts[0]
            
            style_files = sorted(glob.glob(f"tmp_tag_{self.safe_title}_styles_v*.txt"), key=lambda x: int(re.search(r'_styles_v(\d+)', x).group(1)))
            if style_files:
                self.s_version = int(re.search(r'_styles_v(\d+)', style_files[-1]).group(1))
                with open(style_files[-1], 'r', encoding='utf-8') as f:
                    self.style_suggestions = f.read()
                self.state = "STYLE_DISCUSSION"
            
            tag_files = sorted(glob.glob(f"tmp_tag_{self.safe_title}_v*.txt"), key=lambda x: int(re.search(r'_v(\d+)', x).group(1)))
            tag_files = [f for f in tag_files if "_styles_" not in f]
            if tag_files:
                self.version = int(re.search(r'_v(\d+)', tag_files[-1]).group(1))
                with open(tag_files[-1], 'r', encoding='utf-8') as f:
                    self.tagged_lyrics = f.read()
                if self.state != "STYLE_DISCUSSION":
                    self.state = "TAGGING"
                print(f"{self.C_GREEN}已成功恢复!{self.C_RESET}")
                return
            else:
                self.state = "INPUT_LYRICS"
                return
        self.state = "INIT"

    def handle_init(self):
        self.show_header("初始化设置")
        self.select_model()
        if not self.model:
            sys.exit(1)
        self.state = "INPUT_TITLE"

    def handle_input_title(self):
        self.show_header("歌曲标题")
        title = self.handle_input("请输入歌曲标题:", multiline=False)
        if title == "/new":
            self.clear_tmp_files()
            return
        if title == "/quit":
            sys.exit(0)
        if not title:
            return
        self.song_title = title
        self.safe_title = re.sub(r'[\\/*?:"<>|\r\n\t]', "", self.song_title).replace(" ", "_")[:40]
        
        save_path = os.path.join("lyrics_tagged", f"{self.safe_title}.txt")
        if os.path.exists(save_path):
            print(f"\n{self.C_CYAN}--- 发现已有记录: {self.C_RESET}{self.song_title}")
            load_confirm = self.handle_input("是否加载并重做? (y/n): ", multiline=False)
            if load_confirm.lower() in ['y', 'yes', '']:
                with open(save_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                parts = content.split("\n\n=== Suggested Styles ===\n\n")
                self.tagged_lyrics = parts[0].strip()
                self.style_suggestions = parts[1].strip() if len(parts) > 1 else ""
                self.lyrics_original = re.sub(r'^\[.*?\]\n?', '', self.tagged_lyrics, flags=re.MULTILINE)
                self.version = 1
                self.s_version = 1 if self.style_suggestions else 0
                self.save_init()
                with open(f"tmp_tag_{self.safe_title}_v00.txt", 'w', encoding='utf-8') as f:
                    f.write(f"{self.song_title}\n\n{self.lyrics_original}")
                with open(f"tmp_tag_{self.safe_title}_v01.txt", 'w', encoding='utf-8') as f:
                    f.write(self.tagged_lyrics)
                if self.style_suggestions:
                    with open(f"tmp_tag_{self.safe_title}_styles_v01.txt", 'w', encoding='utf-8') as f:
                        f.write(self.style_suggestions)
                print(f"{self.C_GREEN}已成功加载旧版本。{self.C_RESET}")
                self.state = "TAGGING"
                return

        self.save_init()
        self.state = "INPUT_LYRICS"

    def handle_input_lyrics(self):
        self.show_header("输入歌词")
        print(f"{self.C_GRAY}当前: {self.C_CYAN}{self.song_title}{self.C_RESET}")
        lyrics_input = self.handle_input("请粘贴歌词内容:")
        if lyrics_input == "/new":
            self.clear_tmp_files()
            self.state = "INIT"
            return
        if lyrics_input == "/quit":
            sys.exit(0)
        if not lyrics_input:
            return
        self.lyrics_original = lyrics_input
        self.version = 0
        with open(f"tmp_tag_{self.safe_title}_v00.txt", 'w', encoding='utf-8') as f:
            f.write(f"{self.song_title}\n\n{lyrics_input}")
        self.state = "TAGGING"

    def handle_tagging(self):
        self.show_header("歌词标注")
        system_prompt = (
            "你是一位专业的 SUNO AI 音乐总监。你的任务是为歌词添加专业的 Meta Tags。\n\n"
            "【禁止修改歌词】严禁修改任何原文。只能在段落正上方添加标注。\n"
            "【格式要求】中括号 [] 内只能含英文。合并为一对 [] 并用逗号分隔。标注必须独立占行。"
        )
        just_streamed = False
        if self.version == 0:
            print(f"\n正在生成初始标注...")
            full_text = f"{self.song_title}\n\n{self.lyrics_original}"
            result = self.call_ollama(full_text, system_prompt=system_prompt)
            if result:
                self.tagged_lyrics = result
                self.version = 1
                with open(f"tmp_tag_{self.safe_title}_v01.txt", 'w', encoding='utf-8') as f:
                    f.write(self.tagged_lyrics)
                just_streamed = True
            else:
                retry = self.handle_input("\n生成失败，是否重试? (y/n): ", multiline=False)
                if retry.lower() not in ['y', 'yes', '']:
                    self.state = "INPUT_LYRICS"
                return
                
        if not just_streamed:
            print(f"\n--- {self.C_CYAN}当前标注 (v{self.version:02d}){self.C_RESET} ---")
            print(self.tagged_lyrics)
            print(f"---{'-'*20}---")
        
        suggestion = self.handle_input("\n标注建议 (ok 批准, vX 回退, /c 仅讨论):")
        if suggestion == "/new":
            self.clear_tmp_files()
            self.state = "INIT"
            return
        if suggestion == "/quit":
            sys.exit(0)
        
        back_match = re.search(r"back to v(\d+)", suggestion.lower()) or re.search(r"^v(\d+)$", suggestion.lower())
        if back_match:
            v = int(back_match.group(1))
            back_file = f"tmp_tag_{self.safe_title}_v{v:02d}.txt"
            if os.path.exists(back_file) and "_styles_" not in back_file:
                self.version = v
                with open(back_file, 'r', encoding='utf-8') as f:
                    self.tagged_lyrics = f.read()
                print(f"已回退 v{v:02d}")
                return

        intent, clean_input = self.check_intent(suggestion, "标注阶段")
        if intent == "APPROVE":
            self.state = "STYLE_DISCUSSION"
            self.s_version = 0
            return
        elif intent == "CHAT":
            print(f"\n{self.C_CYAN}[制作人见解]:{self.C_RESET}")
            self.call_ollama(f"咨询标注: '{clean_input}'\n内容:\n{self.tagged_lyrics}", 
                             system_prompt="你是一个专业的编曲家。直接回答用户，提供建议，不要重写歌词。")
        elif intent == "MODIFY":
            print(f"\n正在应用修改 (v{self.version:02d} -> v{self.version+1:02d})...")
            prompt_text = f"修改建议: '{clean_input}'\n保持歌词文字 100% 不变。更新标注。\n当前内容:\n{self.tagged_lyrics}"
            new_tagged = self.call_ollama(prompt_text, system_prompt=system_prompt)
            if new_tagged:
                self.tagged_lyrics = new_tagged
                self.version += 1
                with open(f"tmp_tag_{self.safe_title}_v{self.version:02d}.txt", 'w', encoding='utf-8') as f:
                    f.write(self.tagged_lyrics)

    def handle_style_discussion(self):
        self.show_header("风格建议")
        system_prompt = "你是一位资深风格策划师。为歌词策划 5 个详尽（15-25词）的 SUNO Style Prompts。加 '-' 开头，空行分隔。直接列表，不要解释。"
        just_streamed = False
        if self.s_version == 0:
            print(f"\n正在策划风格提示词...")
            result = self.call_ollama(f"为歌词《{self.song_title}》策划风格：\n\n{self.tagged_lyrics}", system_prompt=system_prompt)
            if result:
                self.style_suggestions = result
                self.s_version = 1
                with open(f"tmp_tag_{self.safe_title}_styles_v01.txt", 'w', encoding='utf-8') as f:
                    f.write(self.style_suggestions)
                just_streamed = True
            else:
                retry = self.handle_input("\n生成失败，是否重试? (y/n): ", multiline=False)
                if retry.lower() not in ['y', 'yes', '']:
                    self.state = "TAGGING"
                return

        if not just_streamed:
            print(f"\n--- {self.C_CYAN}当前风格 (sv{self.s_version:02d}){self.C_RESET} ---")
            print(self.style_suggestions)
            print(f"---{'-'*20}---")
        
        suggestion = self.handle_input("\n风格建议 (ok 批准, svX 回退本阶段, vX 跳回标注, /c 仅讨论):")
        if suggestion == "/new":
            self.clear_tmp_files()
            self.state = "INIT"
            return
        if suggestion == "/quit":
            sys.exit(0)
        
        # 1. 处理本阶段内部回退 (svX)
        back_match_sv = re.search(r"back to sv(\d+)", suggestion.lower()) or re.search(r"^sv(\d+)$", suggestion.lower())
        if back_match_sv:
            v = int(back_match_sv.group(1))
            back_file = f"tmp_tag_{self.safe_title}_styles_v{v:02d}.txt"
            if os.path.exists(back_file):
                self.s_version = v
                with open(back_file, 'r', encoding='utf-8') as f:
                    self.style_suggestions = f.read()
                print(f"已回退本阶段版本 sv{v:02d}")
                return

        # 2. 处理跨阶段跳回标注 (vX)
        back_match_v = re.search(r"back to v(\d+)", suggestion.lower()) or re.search(r"^v(\d+)$", suggestion.lower())
        if back_match_v:
            v = int(back_match_v.group(1))
            back_file = f"tmp_tag_{self.safe_title}_v{v:02d}.txt"
            if os.path.exists(back_file) and "_styles_" not in back_file:
                self.version = v
                with open(back_file, 'r', encoding='utf-8') as f:
                    self.tagged_lyrics = f.read()
                self.state = "TAGGING"
                print(f"已跳回【标注阶段】版本 v{v:02d}")
                return

        intent, clean_input = self.check_intent(suggestion, "风格阶段")
        if intent == "APPROVE":
            save_path = os.path.join("lyrics_tagged", f"{self.safe_title}.txt")
            import datetime
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            metadata = (
                f"\n\n=== Metadata ===\n"
                f"Model: {self.model}\n"
                f"Generated At: {now}\n"
            )
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(self.tagged_lyrics + "\n\n=== Suggested Styles ===\n\n" + self.style_suggestions + metadata)
            print(f"\n{self.C_GREEN}已完成保存到: {save_path}{self.C_RESET}")
            self.clear_tmp_files()
            self.state = "ENDING"
            return
        elif intent == "CHAT":
            print(f"\n{self.C_CYAN}[策划师见解]:{self.C_RESET}")
            self.call_ollama(f"咨询风格: '{clean_input}'\n建议内容:\n{self.style_suggestions}", system_prompt="你是策划师。直接回答用户，不要输出多方案。")
        elif intent == "MODIFY":
            print(f"\n正在应用修改 (sv{self.s_version:02d} -> sv{self.s_version+1:02d})...")
            new_styles = self.call_ollama(f"修改风格建议: '{clean_input}'\n当前建议:\n{self.style_suggestions}", system_prompt=system_prompt)
            if new_styles:
                self.style_suggestions = new_styles
                self.s_version += 1
                with open(f"tmp_tag_{self.safe_title}_styles_v{self.s_version:02d}.txt", 'w', encoding='utf-8') as f:
                    f.write(self.style_suggestions)

    def handle_ending(self):
        choice = self.handle_input("\n是否处理其他歌曲? (yes/no):", multiline=False)
        if choice.lower() in ['yes', 'y', '好的', '是']:
            self.state = "INIT"
        else:
            print("感谢使用，再见！")
            sys.exit(0)

if __name__ == "__main__":
    agent = SunoTagAgent()
    agent.run()
