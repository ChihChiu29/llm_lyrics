import os
import re
import sys
import json
import glob
import requests
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
        self.version = 0
        self.in_model_selection = False
        
        # 预设颜色 (ANSI)
        self.C_GRAY = "\033[90m"
        self.C_GREEN = "\033[32m"
        self.C_YELLOW = "\033[33m"
        self.C_CYAN = "\033[36m"
        self.C_RESET = "\033[0m"

    def run(self):
        print(f"{self.C_CYAN}=== SUNO 歌词标注助手 (Ultimate Edition) ==={self.C_RESET}")
        print("提示: 随时输入 /help 查看可用命令")
        print(f"{self.C_GRAY}多行模式提示: 输入内容后，按 Alt+Enter 或 Esc后按Enter 提交。{self.C_RESET}")
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
                elif self.state == "ENDING":
                    self.handle_ending()
        except KeyboardInterrupt:
            print(f"\n\n{self.C_YELLOW}[中断]{self.C_RESET} 程序已由用户手动中断。")
            sys.exit(0)

    def show_header(self, title):
        print(f"\n{self.C_CYAN}{'='*30}")
        print(f" [阶段: {title}] ")
        print(f"{'='*30}{self.C_RESET}")

    def show_help(self):
        print(f"\n{self.C_GRAY}" + "-"*20)
        print(" 可用命令清单 ")
        print("-"*20)
        print("/help          - 显示此帮助信息")
        print("/model         - 切换当前使用的模型")
        print("/m, /multiline - 手动开启多行模式")
        print("/new           - 彻底开启新任务")
        print("/quit          - 退出程序")
        print("-" * 20 + f"{self.C_RESET}\n")

    def handle_input(self, prompt_text, multiline=False):
        """使用 prompt_toolkit 统一处理输入"""
        pt_prompt = ANSI(f"{self.C_GREEN}{prompt_text}{self.C_RESET} ")
        
        while True:
            try:
                user_input = prompt(pt_prompt, multiline=multiline).strip()
            except KeyboardInterrupt:
                print(f"\n{self.C_YELLOW}[取消当前输入]{self.C_RESET}")
                return "/quit"
            except EOFError:
                return "/quit"

            if not user_input:
                return ""

            cmd = user_input.lower()
            first_line = user_input.split('\n')[0].lower().strip()
            
            if first_line == "/quit":
                print("再见！")
                sys.exit(0)
            if first_line == "/help":
                self.show_help()
                if multiline: return self.handle_input(prompt_text, multiline=True)
                continue
            if first_line == "/model":
                if not self.in_model_selection:
                    self.select_model()
                    if self.song_title: self.save_init()
                    if multiline: return self.handle_input(prompt_text, multiline=True)
                    continue
                else:
                    print("已经在模型选择界面了。")
                    continue
            if first_line in ["/m", "/multiline"]:
                return self.handle_input(prompt_text, multiline=True)
            if first_line == "/new":
                return "/new"
            
            return user_input

    def call_ollama(self, prompt, system_prompt="", stream=True, temperature=0.7):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": stream,
            "options": {"temperature": temperature}
        }
        try:
            resp = requests.post(f"{OLLAMA_API_URL}/chat", json=payload, stream=stream)
            resp.raise_for_status()
            
            if not stream:
                return resp.json().get('message', {}).get('content', '').strip()

            full_content = ""
            current_is_reasoning = False
            try:
                for line in resp.iter_lines():
                    if not line: continue
                    chunk = json.loads(line)
                    message = chunk.get('message', {})
                    reasoning = message.get('reasoning_content', '')
                    if reasoning:
                        if not current_is_reasoning:
                            print(f"\n{self.C_GRAY}[思考中...]", end='', flush=True)
                            current_is_reasoning = True
                        print(reasoning, end='', flush=True)
                        continue
                    if current_is_reasoning:
                        print(f"{self.C_RESET}\n{self.C_GREEN}[回复]:{self.C_RESET} ", end='', flush=True)
                        current_is_reasoning = False
                    content = message.get('content', '')
                    full_content += content
                    print(content, end='', flush=True)
            except KeyboardInterrupt:
                print(f"\n{self.C_YELLOW}[中断] 生成已停止。{self.C_RESET}")
                return full_content
            print()
            return full_content
        except Exception as e:
            if stream: print(f"\n{self.C_YELLOW}API 错误: {e}{self.C_RESET}")
            return ""

    def check_intent(self, user_input):
        """判断用户意图：批准、修改还是纯讨论"""
        normalized = user_input.lower().strip(" .!！。")
        
        # 1. 指令强制判断
        if normalized.startswith(("/c ", "/chat ")):
            parts = user_input.split(' ', 1)
            return "CHAT", parts[1] if len(parts) > 1 else ""
        if normalized in ["/c", "/chat"]:
            return "CHAT", ""

        # 2. 基础白名单 (批准)
        approvals = ['ok', 'go', 'yes', 'y', 'fine', 'good', '好的', '可以', '成了', '满意', '批准', '通过']
        if normalized in approvals:
            return "APPROVE", user_input

        # 3. 基础黑名单 (明确的修改请求)
        rejections = ['不行', '修改', '建议', '换', '重写', '再来', '重新', 'again', 'retry', 're-', 'bad', 'wrong', 'back to']
        if any(word in normalized for word in rejections):
            return "MODIFY", user_input

        # 4. LLM 深度判断 (Silent)
        check_prompt = (
            f"请判断用户输入意图。用户输入: '{user_input}'\n\n"
            "分类：\n"
            "- APPROVE: 满意并通过。\n"
            "- MODIFY: 要求对现有的标注进行实质改动。\n"
            "- CHAT: 提问、探讨建议、询问见解，而非【立即】修改。\n\n"
            "仅仅回答一个单词: APPROVE, MODIFY 或 CHAT。"
        )
        result = self.call_ollama(check_prompt, stream=False, temperature=0).strip().upper()
        if "APPROVE" in result: return "APPROVE", user_input
        if "MODIFY" in result: return "MODIFY", user_input
        return "CHAT", user_input

    def clear_tmp_files(self):
        for f in glob.glob("tmp_tag_*"):
            try: os.remove(f)
            except: pass
        self.song_title = ""
        self.safe_title = ""
        self.version = 0

    def select_model(self):
        try:
            resp = requests.get(f"{OLLAMA_API_URL}/tags")
            resp.raise_for_status()
            models = [m['name'] for m in resp.json().get('models', [])]
        except:
            print(f"{self.C_YELLOW}无法获取模型列表，请检查 Ollama 是否启动。{self.C_RESET}")
            return
        if not models:
            print(f"{self.C_YELLOW}Ollama 中未发现任何模型。{self.C_RESET}")
            return
        print(f"\n{self.C_GRAY}可用模型列表:{self.C_RESET}")
        for i, m in enumerate(models):
            tag = f"{self.C_CYAN}(当前){self.C_RESET}" if m == self.model else ""
            print(f"{i+1}. {m} {tag}")
        self.in_model_selection = True
        choice = self.handle_input(f"\n请选择模型编号 (直接回车保持当前/默认): ")
        self.in_model_selection = False
        if choice in ["/new", "/quit"]: return
        if not choice:
            if not self.model: self.model = models[0]
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                self.model = models[idx]
                print(f"已成功切换为: {self.C_GREEN}{self.model}{self.C_RESET}")
            else: raise ValueError
        except:
            print(f"{self.C_YELLOW}选择无效。{self.C_RESET}")
            if not self.model: self.model = models[0]

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
                print(f"\n{self.C_CYAN}--- 发现未完成的任务: {self.C_RESET}{self.song_title}")
                confirm = self.handle_input(f"是否继续使用上次的模型 {self.C_YELLOW}{last_model}{self.C_RESET}? (y/n): ")
                if confirm.lower() in ['y', 'yes', '']: self.model = last_model
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
            files = sorted(glob.glob(f"tmp_tag_{self.safe_title}_v*.txt"), key=lambda x: int(re.search(r'_v(\d+)', x).group(1)))
            if files:
                latest_file = files[-1]
                self.version = int(re.search(r'_v(\d+)', latest_file).group(1))
                with open(latest_file, 'r', encoding='utf-8') as f: self.tagged_lyrics = f.read()
                self.state = "TAGGING"
                print(f"{self.C_GREEN}已成功恢复进度!{self.C_RESET} (版本 {self.version:02d})")
                return
            else:
                self.state = "INPUT_LYRICS"
                print(f"{self.C_GREEN}已准备好继续任务。{self.C_RESET}")
                return
        self.state = "INIT"

    def handle_init(self):
        self.show_header("初始化设置")
        if not self.model: self.select_model()
        if not self.model: sys.exit(1)
        self.state = "INPUT_TITLE"

    def handle_input_title(self):
        self.show_header("输入歌曲标题")
        title = self.handle_input("请输入歌曲标题:")
        if title == "/new": self.clear_tmp_files(); return
        if title == "/quit": return
        if not title: return
        self.song_title = title
        self.safe_title = re.sub(r'[\\/*?:"<>|\r\n\t]', "", self.song_title).replace(" ", "_")[:40]
        if not self.safe_title: self.safe_title = "unnamed_song"
        self.save_init()
        self.state = "INPUT_LYRICS"

    def handle_input_lyrics(self):
        self.show_header("输入歌词内容")
        print(f"{self.C_GRAY}当前歌曲: {self.C_CYAN}{self.song_title}{self.C_RESET}")
        lyrics_input = self.handle_input("请粘贴歌词内容:", multiline=True)
        if lyrics_input == "/new": self.clear_tmp_files(); self.state = "INIT"; return
        if lyrics_input == "/quit": return
        if not lyrics_input: return
        self.lyrics_original = lyrics_input
        self.version = 0
        with open(f"tmp_tag_{self.safe_title}_v00.txt", 'w', encoding='utf-8') as f:
            f.write(f"{self.song_title}\n\n{lyrics_input}")
        self.state = "TAGGING"

    def handle_tagging(self):
        self.show_header("生成标注建议")
        system_prompt = (
            "你是一位专业的 SUNO AI 音乐总监和编曲专家。你的任务是为歌词添加专业的 Meta Tags。\n\n"
            "【格式禁令 - 违反将导致解析失败】\n"
            "1. **严禁中括号内包含中文或歌词**：中括号 [] 内必须且只能包含英文描述词。绝对不能出现歌词文字。\n"
            "   - 错误：[这段要大声唱, Fast Rap]\n"
            "   - 正确：[Fast Rap, Aggressive Vocals]\n"
            "2. **严禁使用 Markdown 加粗标题**：禁止输出如 **(Verse)** 或 **(Bridge)** 这种文本。SUNO 无法识别。\n"
            "3. **独立占行**：所有标注必须单独占据一行，放在对应歌词段落的正上方。\n\n"
            "【标注逻辑】\n"
            "- **标签合并**：同一位置的所有描述合并在同一对 [] 内，用逗号 ',' 分隔。\n"
            "- **详尽描述**：包含结构、节奏、乐器演奏法、人声特质（如 [Chorus, anthemic, heavy rock guitar, high-pitched vocals]）。\n"
            "- **歌词完整性**：必须输出完整的原始歌词，不得删减或修改文字。"
        )
        just_streamed = False
        if self.version == 0:
            print(f"\n正在为 '{self.song_title}' 生成初始标注...")
            full_text = f"{self.song_title}\n\n{self.lyrics_original}"
            self.tagged_lyrics = self.call_ollama(f"请为这首歌进行专业标注：\n\n{full_text}", system_prompt=system_prompt)
            if self.tagged_lyrics:
                self.version = 1
                with open(f"tmp_tag_{self.safe_title}_v{self.version:02d}.txt", 'w', encoding='utf-8') as f: f.write(self.tagged_lyrics)
                just_streamed = True
            else: return

        if not just_streamed:
            print(f"\n--- {self.C_CYAN}当前标注预览 (v{self.version:02d}){self.C_RESET} ---")
            print(self.tagged_lyrics)
            print(f"---{'-'*20}---")

        suggestion = self.handle_input("\n输入建议/问题 (ok 批准, vX 回退, /c 仅讨论):")
        if suggestion == "/new": self.clear_tmp_files(); self.state = "INIT"; return
        if suggestion == "/quit": return

        # 处理回退逻辑
        back_match = re.search(r"back to v(\d+)", suggestion.lower()) or re.search(r"v(\d+)", suggestion.lower())
        if back_match and "v" in suggestion.lower():
            v = int(back_match.group(1))
            back_file = f"tmp_tag_{self.safe_title}_v{v:02d}.txt"
            if os.path.exists(back_file):
                self.version = v
                with open(back_file, 'r', encoding='utf-8') as f: self.tagged_lyrics = f.read()
                print(f"已回退到版本 {v:02d}")
                return
            else:
                print(f"版本 {v:02d} 不存在。")
                return

        # 意图识别
        intent, clean_input = self.check_intent(suggestion)

        if intent == "APPROVE":
            if not os.path.exists("lyrics_tagged"): os.makedirs("lyrics_tagged")
            save_path = os.path.join("lyrics_tagged", f"{self.safe_title}.txt")
            with open(save_path, 'w', encoding='utf-8') as f: f.write(self.tagged_lyrics)
            print(f"\n{self.C_GREEN}全部完成！{self.C_RESET} 已保存到: {save_path}")
            self.clear_tmp_files()
            self.state = "ENDING"
            return

        elif intent == "CHAT":
            print(f"\n{self.C_CYAN}[制作人见解]:{self.C_RESET}")
            chat_prompt = (
                f"作为制作人，用户咨询关于《{self.song_title}》标注的问题：\n"
                f"'{clean_input}'\n\n"
                f"当前标注版本(v{self.version:02d})如下：\n{self.tagged_lyrics}\n\n"
                "请给出你的专业见解，但【不要】输出修改后的歌词。保持对话。"
            )
            self.call_ollama(chat_prompt, system_prompt="你是一个乐于交流的专业编曲家。只提供对话，不输出完整歌词。")
            return

        elif intent == "MODIFY":
            print(f"\n正在应用修改 (v{self.version:02d} -> v{self.version+1:02d})...")
            prompt = (
                f"基于建议修改《{self.song_title}》的标注：\n'{clean_input}'\n\n"
                f"当前版本内容：\n{self.tagged_lyrics}\n\n"
                "请先简要说明修改点，然后输出修改后的完整标注歌词。"
            )
            new_tagged = self.call_ollama(prompt, system_prompt=system_prompt)
            if new_tagged:
                self.tagged_lyrics = new_tagged
                self.version += 1
                with open(f"tmp_tag_{self.safe_title}_v{self.version:02d}.txt", 'w', encoding='utf-8') as f: f.write(self.tagged_lyrics)

    def handle_ending(self):
        choice = self.handle_input("\n是否继续处理其他歌曲? (yes/no):")
        if choice.lower() in ['yes', 'y', '好的', '是']:
            self.state = "INIT"
        else:
            print("感谢使用，再见！")
            sys.exit(0)

if __name__ == "__main__":
    agent = SunoTagAgent()
    agent.run()
