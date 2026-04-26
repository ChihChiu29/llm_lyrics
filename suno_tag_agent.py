import os
import re
import sys
import json
import glob
import requests

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
        
        # 预设颜色
        self.C_GRAY = "\033[90m"
        self.C_GREEN = "\033[32m"
        self.C_YELLOW = "\033[33m"
        self.C_CYAN = "\033[36m"
        self.C_RESET = "\033[0m"

    def run(self):
        print(f"{self.C_CYAN}=== SUNO 歌词标注助手 (Ultimate Edition) ==={self.C_RESET}")
        print("提示: 随时输入 /help 查看可用命令")
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

    # --- 核心抽象方法 ---

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
        print("/m, /multiline - 进入多行输入模式 (输入 'END' 结束)")
        print("/new           - 彻底开启新任务")
        print("/quit          - 退出程序")
        print("-" * 20 + f"{self.C_RESET}\n")

    def handle_input(self, prompt_text):
        while True:
            try:
                user_input = input(f"{self.C_GREEN}{prompt_text}{self.C_RESET}").strip()
            except KeyboardInterrupt:
                print(f"\n{self.C_YELLOW}[取消当前输入]{self.C_RESET}")
                return "/quit"

            cmd = user_input.lower()
            if cmd == "/quit":
                print("再见！")
                sys.exit(0)
            if cmd == "/help":
                self.show_help()
                continue
            if cmd == "/model":
                if not self.in_model_selection:
                    self.select_model()
                    if self.song_title: self.save_init()
                    continue
                else:
                    print("已经在模型选择界面了。")
                    continue
            if cmd in ["/m", "/multiline"]:
                print(f"{self.C_GRAY}--- 进入多行模式 (在独立一行输入 'END' 以结束) ---{self.C_RESET}")
                lines = []
                try:
                    while True:
                        line = input()
                        if line.strip().upper() == "END": break
                        lines.append(line)
                except KeyboardInterrupt:
                    print(f"\n{self.C_YELLOW}[已取消多行输入]{self.C_RESET}")
                    continue
                return "\n".join(lines).strip()
            if cmd == "/new":
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
            
            full_content = ""
            current_is_reasoning = False
            
            try:
                for line in resp.iter_lines():
                    if not line: continue
                    chunk = json.loads(line)
                    message = chunk.get('message', {})
                    
                    # 思考内容处理
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
            print(f"\n{self.C_YELLOW}API 错误: {e}{self.C_RESET}")
            return ""

    def check_approval(self, user_input, context_desc="内容批准"):
        normalized = user_input.lower().strip(" .!！。")
        
        approvals = ['ok', 'go', 'yes', 'y', 'fine', 'good', '好的', '可以', '成了', '满意', '批准', '通过']
        if normalized in approvals: return True
        
        rejections = ['不行', '修改', '建议', '换', '重写', '再来', '重新', 'again', 'retry', 're-', 'bad', 'wrong', 'back to']
        if any(word in normalized for word in rejections): return False
        
        check_prompt = f"场景：用户正在进行【{context_desc}】。判断意图：'满意批准' 还是 '提出修改/重来'。用户输入: '{user_input}'。仅仅回答 YES 或 NO。"
        result = self.call_ollama(check_prompt, stream=False, temperature=0).strip().upper()
        return result.startswith("YES")

    # --- 业务逻辑方法 ---

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

        print(f"\n{self.C_GRAY}可用模型列表:{self.C_RESET}")
        for i, m in enumerate(models):
            tag = f"{self.C_CYAN}(当前){self.C_RESET}" if m == self.model else ""
            print(f"{i+1}. {m} {tag}")
        
        self.in_model_selection = True
        choice = self.handle_input(f"\n请选择模型编号 (直接回车保持当前): ")
        self.in_model_selection = False
        
        if choice in ["/new", "/quit"]: return
        if choice:
            try:
                self.model = models[int(choice)-1]
                print(f"已成功切换为: {self.C_GREEN}{self.model}{self.C_RESET}")
            except:
                print(f"{self.C_YELLOW}选择无效。{self.C_RESET}")

    def save_init(self):
        with open("tmp_tag_init.md", 'w', encoding='utf-8') as f:
            f.write(f"Model: {self.model}\nTitle: {self.song_title}\n")

    def resume_workflow(self):
        if os.path.exists("tmp_tag_init.md"):
            with open("tmp_tag_init.md", 'r', encoding='utf-8') as f:
                content = f.read()
                m = re.search(r"Model: (.*)", content)
                if m: self.model = m.group(1).strip()
                t = re.search(r"Title: (.*)", content)
                if t: 
                    self.song_title = t.group(1).strip()
                    self.safe_title = re.sub(r'[\\/*?:"<>|]', "", self.song_title).replace(" ", "_")

        if self.safe_title:
            files = sorted(glob.glob(f"tmp_tag_{self.safe_title}_v*.txt"), key=lambda x: int(re.search(r'_v(\d+)', x).group(1)))
            if files:
                latest_file = files[-1]
                self.version = int(re.search(r'_v(\d+)', latest_file).group(1))
                with open(latest_file, 'r', encoding='utf-8') as f:
                    self.tagged_lyrics = f.read()
                self.state = "TAGGING"
                print(f"{self.C_GREEN}已自动恢复进度:{self.C_RESET} '{self.song_title}' (版本 {self.version:02d})")
                return
            else:
                self.state = "INPUT_LYRICS"
                print(f"{self.C_GREEN}已自动恢复任务:{self.C_RESET} '{self.song_title}'")
                return
        self.state = "INIT"

    def handle_init(self):
        self.show_header("初始化设置")
        if not self.model: self.select_model()
        if not self.model: sys.exit(1)
        self.state = "INPUT_TITLE"

    def handle_input_title(self):
        self.show_header("输入歌曲标题")
        title = self.handle_input("\n请输入歌曲标题: ")
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
        print(f"{self.C_GRAY}说明: 请粘贴歌词。建议输入 /m 开启多行粘贴。{self.C_RESET}")
        
        lyrics_input = self.handle_input("\n请输入歌词内容: ")
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
            "你是一位专业的 SUNO AI 编曲专家。为歌词添加创意详尽的 Meta Tags。\n"
            "结构：[Intro: cinematic], [Verse], [Chorus: energetic], [Bridge], [Outro]\n"
            "乐器：[Guitar Solo: crying], [808 Sub Bass], [Piano: staccato], [Full band explosion]\n"
            "演唱：[Rap Verse], [Fast Rap], [Mumble], [Whisper], [Melodic Hook]\n"
            "格式要求：段落前添加标注行。保持原歌词。以标题开头。禁止多余解释。"
        )

        if self.version == 0:
            print(f"\n正在生成初始标注...")
            full_text = f"{self.song_title}\n\n{self.lyrics_original}"
            self.tagged_lyrics = self.call_ollama(f"请标注：\n{full_text}", system_prompt=system_prompt)
            if self.tagged_lyrics:
                self.version = 1
                with open(f"tmp_tag_{self.safe_title}_v{self.version:02d}.txt", 'w', encoding='utf-8') as f:
                    f.write(self.tagged_lyrics)
            else: return

        print(f"\n--- {self.C_CYAN}当前标注预览 (v{self.version:02d}){self.C_RESET} ---")
        print(self.tagged_lyrics)
        print(f"---{'-'*20}---")

        suggestion = self.handle_input("\n请输入建议 (或 'ok' 批准, 'let's go back to vX' 回退): ")
        if suggestion == "/new": self.clear_tmp_files(); self.state = "INIT"; return
        if suggestion == "/quit": return

        # 处理回退逻辑
        back_match = re.search(r"back to v(\d+)", suggestion.lower())
        if back_match:
            v = int(back_match.group(1))
            back_file = f"tmp_tag_{self.safe_title}_v{v:02d}.txt"
            if os.path.exists(back_file):
                self.version = v
                with open(back_file, 'r', encoding='utf-8') as f:
                    self.tagged_lyrics = f.read()
                print(f"已回退到版本 {v:02d}")
                return
            else:
                print(f"版本 {v:02d} 不存在。")
                return

        if self.check_approval(suggestion, "标注批准"):
            if not os.path.exists("lyrics_tagged"): os.makedirs("lyrics_tagged")
            save_path = os.path.join("lyrics_tagged", f"{self.safe_title}.txt")
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(self.tagged_lyrics)
            print(f"\n{self.C_GREEN}全部完成！{self.C_RESET} 已保存到: {save_path}")
            self.clear_tmp_files()
            self.state = "ENDING"
            return

        print("\n正在根据建议修改...")
        new_tagged = self.call_ollama(f"建议：{suggestion}\n当前：\n{self.tagged_lyrics}", system_prompt=system_prompt)
        if new_tagged:
            self.tagged_lyrics = new_tagged
            self.version += 1
            with open(f"tmp_tag_{self.safe_title}_v{self.version:02d}.txt", 'w', encoding='utf-8') as f:
                f.write(self.tagged_lyrics)

    def handle_ending(self):
        choice = self.handle_input("\n是否继续处理其他歌曲? (yes/no): ")
        if choice.lower() in ['yes', 'y', '好的', '是']:
            self.state = "INIT"
        else:
            print("感谢使用，再见！")
            sys.exit(0)

if __name__ == "__main__":
    agent = SunoTagAgent()
    agent.run()
