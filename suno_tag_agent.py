import os
import re
import sys
import glob
import datetime
import requests
import threading
import time
from prompt_toolkit import prompt
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings
from agent_utils import Spinner, OllamaClient, handle_rich_input

class SunoTagAgent:
    def __init__(self):
        self.ollama = OllamaClient()
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
        
        # 提示词模板加载
        self.tagging_prompt = self._load_prompt("prompts/tagging_system.md", "你是一位专业的 SUNO AI 音乐总监。为歌词添加专业的 Meta Tags。严禁修改歌词文字。")
        self.style_prompt = self._load_prompt("prompts/style_system.md", "你是一位资深风格策划师。为歌词策划 5 个详尽的 SUNO Style Prompts。")

        self.C_CYAN = "\033[36m"
        self.C_GRAY = "\033[90m"
        self.C_YELLOW = "\033[33m"
        self.C_GREEN = "\033[32m"
        self.C_RESET = "\033[0m"

    def _load_prompt(self, path, default):
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        return default

    def run(self):
        print(f"{self.C_CYAN}=== SUNO 歌词标注助手 (Ultimate Edition) ==={self.C_RESET}")
        print("提示: 随时输入 /help 查看可用命令")
        
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

    def show_header(self, title):
        print(f"\n{self.C_CYAN}{'='*40}")
        print(f" [阶段: {title}] ")
        print(f"{'='*40}{self.C_RESET}")

    def show_help(self):
        print(f"\n{self.C_CYAN}--- SUNO 标注助手: 指令手册 ---{self.C_RESET}")
        print("  /help   - 显示此详细帮助")
        print("  /model  - 切换 Ollama 模型")
        print("  /new    - 开启新任务")
        print("  /quit   - 立即退出程序")
        print("\n  Enter: 提交内容 | Ctrl-J: 换行")
        print("  vX (标注版本), svX (风格版本): 回退版本")
        print("-" * 30 + "\n")

    def handle_common_input(self, prompt_text, multiline=True):
        while True:
            user_input = handle_rich_input(prompt_text, multiline=multiline)
            if user_input == "/quit":
                sys.exit(0)
            if not user_input:
                return ""
            first_line = user_input.split('\n')[0].lower().strip()
            if first_line == "/help":
                self.show_help()
                continue
            if first_line == "/model":
                self.select_model()
                if self.song_title:
                    self.save_init()
                continue
            if first_line == "/new":
                return "/new"
            return user_input

    def select_model(self):
        models = self.ollama.get_models()
        if not models:
            print(f"{self.C_YELLOW}无法连接 Ollama。{self.C_RESET}")
            return
        print(f"\n{self.C_GRAY}可用模型:{self.C_RESET}")
        for i, m in enumerate(models):
            tag = ""
            if m == self.ollama.model:
                tag = f"{self.C_CYAN}(当前){self.C_RESET}"
            print(f"{i+1}. {m} {tag}")
        
        self.in_model_selection = True
        choice = self.handle_common_input("\n选择模型编号 (回车当前): ", multiline=False)
        self.in_model_selection = False
        
        if choice == "/new":
            return
        if not choice:
            if not self.ollama.model:
                if models:
                    self.ollama.model = models[0]
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                self.ollama.model = models[idx]
                print(f"已切换至: {self.C_GREEN}{self.ollama.model}{self.C_RESET}")
        except:
            if not self.ollama.model:
                if models:
                    self.ollama.model = models[0]

    def save_init(self):
        with open("tmp_tag_init.md", 'w', encoding='utf-8') as f:
            f.write(f"Model: {self.ollama.model}\nTitle: {self.song_title}\n")

    def resume_workflow(self):
        if os.path.exists("tmp_tag_init.md"):
            with open("tmp_tag_init.md", 'r', encoding='utf-8') as f:
                content = f.read()
                m = re.search(r"Model: (.*)", content)
                if m:
                    self.ollama.model = m.group(1).strip()
                t = re.search(r"Title: (.*)", content)
                if t: 
                    self.song_title = t.group(1).strip()
                    self.safe_title = re.sub(r'[\\/*?:"<>|]', "", self.song_title).replace(" ", "_")
            
            if self.ollama.model:
                print(f"\n{self.C_CYAN}--- 待处理歌曲: {self.C_RESET}{self.song_title}")
                prompt_txt = f"是否继续使用模型 {self.ollama.model}? (y/n): "
                confirm = self.handle_common_input(prompt_txt, multiline=False)
                if confirm.lower() not in ['y', 'yes', '']:
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
            elif self.song_title:
                self.state = "INPUT_LYRICS"
                return
        self.state = "INIT"

    def handle_init(self):
        self.show_header("初始化设置")
        self.select_model()
        if not self.ollama.model:
            sys.exit(1)
        self.state = "INPUT_TITLE"

    def handle_input_title(self):
        self.show_header("歌曲标题")
        title = self.handle_common_input("请输入歌曲标题:", multiline=False)
        if title == "/new":
            self.clear_tmp_files()
            return
        if not title:
            return
        self.song_title = title
        self.safe_title = re.sub(r'[\\/*?:"<>|\r\n\t]', "", self.song_title).replace(" ", "_")[:40]
        
        found_file = None
        for f in glob.glob("lyrics_tagged/*.txt"):
            filename = os.path.basename(f)
            if filename.endswith(f"_{self.safe_title}.txt"):
                found_file = f
                break

        if found_file:
            print(f"\n{self.C_CYAN}--- 发现已有记录: {self.C_RESET}{os.path.basename(found_file)}")
            confirm = self.handle_common_input("是否加载并重做? (y/n): ", multiline=False)
            if confirm.lower() in ['y', 'yes', '']:
                with open(found_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                parts = content.split("\n\n=== Suggested Styles ===\n\n")
                self.tagged_lyrics = parts[0].strip()
                if len(parts) > 1:
                    self.style_suggestions = parts[1].strip()
                else:
                    self.style_suggestions = ""
                self.lyrics_original = re.sub(r'^\[.*?\]\n?', '', self.tagged_lyrics, flags=re.MULTILINE)
                self.version = 1
                if self.style_suggestions:
                    self.s_version = 1
                else:
                    self.s_version = 0
                self.save_init()
                with open(f"tmp_tag_{self.safe_title}_v00.txt", 'w', encoding='utf-8') as f:
                    f.write(f"{self.song_title}\n\n{self.lyrics_original}")
                with open(f"tmp_tag_{self.safe_title}_v01.txt", 'w', encoding='utf-8') as f:
                    f.write(self.tagged_lyrics)
                if self.style_suggestions:
                    with open(f"tmp_tag_{self.safe_title}_styles_v01.txt", 'w', encoding='utf-8') as f:
                        f.write(self.style_suggestions)
                self.state = "TAGGING"
                return
        
        self.save_init()
        self.state = "INPUT_LYRICS"

    def handle_input_lyrics(self):
        self.show_header("输入歌词内容")
        print(f"{self.C_GRAY}当前: {self.C_CYAN}{self.song_title}{self.C_RESET}")
        lyrics_input = self.handle_common_input("请粘贴歌词全文:")
        if lyrics_input == "/new":
            self.clear_tmp_files()
            self.state = "INIT"
            return
        if not lyrics_input:
            return
        self.lyrics_original = lyrics_input
        self.version = 0
        with open(f"tmp_tag_{self.safe_title}_v00.txt", 'w', encoding='utf-8') as f:
            f.write(f"{self.song_title}\n\n{lyrics_input}")
        self.state = "TAGGING"

    def handle_tagging(self):
        self.show_header("歌词标注建议")
        system_prompt = (
            "你是一位专业的 SUNO AI 音乐总监。你的任务是为歌词添加专业的 Meta Tags。\n\n"
            "【禁止修改歌词】严禁修改任何原文。只能在段落正上方添加标注。\n"
            "【格式要求】中括号 [] 内只能含英文。合并为一对 [] 并用逗号分隔。标注必须独立占行。"
        )
        just_streamed = False
        if self.version == 0:
            full_text = f"{self.song_title}\n\n{self.lyrics_original}"
            self.tagged_lyrics = self.ollama.call(full_text, system_prompt=system_prompt, spinner=Spinner())
            if self.tagged_lyrics:
                self.version = 1
                with open(f"tmp_tag_{self.safe_title}_v01.txt", 'w', encoding='utf-8') as f:
                    f.write(self.tagged_lyrics)
                just_streamed = True
            else:
                return
        
        if not just_streamed:
            print(f"\n--- {self.C_CYAN}当前预览 (v{self.version:02d}){self.C_RESET} ---")
            print(self.tagged_lyrics)
            print(f"---{'-'*20}---")
            
        suggestion = self.handle_common_input("\n标注建议 (ok 批准进入风格, vX 回退, /c 讨论):")
        if suggestion == "/new":
            self.clear_tmp_files()
            self.state = "INIT"
            return

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

        intent, clean_input = self.ollama.check_intent(suggestion, self.song_title, "标注阶段")
        if intent == "APPROVE":
            self.state = "STYLE_DISCUSSION"
            self.s_version = 0
            return
        elif intent == "CHAT":
            print(f"\n{self.C_CYAN}[制作人见解]:{self.C_RESET}")
            self.ollama.call(f"咨询关于《{self.song_title}》的标注：'{clean_input}'\n内容：\n{self.tagged_lyrics}", 
                             system_prompt="你是制作人。直接回答建议，不输出方案，不重写歌词。", spinner=Spinner())
        elif intent == "MODIFY":
            print(f"\n正在修改 (v{self.version:02d} -> v{self.version+1:02d})...")
            new_tagged = self.ollama.call(f"修改建议：'{clean_input}'\n当前：\n{self.tagged_lyrics}", system_prompt=system_prompt, spinner=Spinner())
            if new_tagged:
                self.tagged_lyrics = new_tagged
                self.version += 1
                with open(f"tmp_tag_{self.safe_title}_v{self.version:02d}.txt", 'w', encoding='utf-8') as f:
                    f.write(self.tagged_lyrics)

    def handle_style_discussion(self):
        self.show_header("风格提示词策划")
        system_prompt = "资深风格策划师。策划 5 个详尽（15-25词）SUNO Style Prompts。加 '-' 开头，空行分隔。直接列表，不要解释。"
        just_streamed = False
        if self.s_version == 0:
            self.style_suggestions = self.ollama.call(f"为歌词策划风格：\n\n{self.tagged_lyrics}", system_prompt=system_prompt, spinner=Spinner())
            if self.style_suggestions:
                self.s_version = 1
                with open(f"tmp_tag_{self.safe_title}_styles_v01.txt", 'w', encoding='utf-8') as f:
                    f.write(self.style_suggestions)
                just_streamed = True
            else:
                return

        if not just_streamed:
            print(f"\n--- {self.C_CYAN}当前风格 (sv{self.s_version:02d}){self.C_RESET} ---")
            print(self.style_suggestions)
            print(f"---{'-'*20}---")
            
        suggestion = self.handle_common_input("\n风格建议 (ok 批准并保存, svX 回退, /c 讨论):")
        if suggestion == "/new":
            self.clear_tmp_files()
            self.state = "INIT"
            return
            
        back_match = re.search(r"back to sv(\d+)", suggestion.lower()) or re.search(r"^sv(\d+)$", suggestion.lower())
        if back_match:
            v = int(back_match.group(1))
            back_file = f"tmp_tag_{self.safe_title}_styles_v{v:02d}.txt"
            if os.path.exists(back_file):
                self.s_version = v
                with open(back_file, 'r', encoding='utf-8') as f:
                    self.style_suggestions = f.read()
                print(f"已回退 sv{v:02d}")
                return

        intent, clean_input = self.ollama.check_intent(suggestion, self.song_title, "风格阶段")
        if intent == "APPROVE":
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            save_path = os.path.join("lyrics_tagged", f"{today}_{self.safe_title}.txt")
            for f in glob.glob(f"lyrics_tagged/*_{self.safe_title}.txt"):
                try: os.remove(f)
                except: pass
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(self.tagged_lyrics + "\n\n=== Suggested Styles ===\n\n" + self.style_suggestions + f"\n\n=== Metadata ===\nModel: {self.ollama.model}\nSaved At: {now}\n")
            print(f"\n{self.C_GREEN}已完成保存到: {save_path}{self.C_RESET}")
            self.clear_tmp_files()
            self.state = "ENDING"
            return
        elif intent == "CHAT":
            print(f"\n{self.C_CYAN}[策划师见解]:{self.C_RESET}")
            self.ollama.call(f"咨询风格建议：'{clean_input}'\n内容：\n{self.style_suggestions}", system_prompt="你是风格策划师。直接回答用户，不输出方案，不输出列表。", spinner=Spinner())
        elif intent == "MODIFY":
            print(f"\n正在修改 (sv{self.s_version:02d} -> sv{self.s_version+1:02d})...")
            new_styles = self.ollama.call(f"修改建议：'{clean_input}'\n当前：\n{self.style_suggestions}", system_prompt=system_prompt, spinner=Spinner())
            if new_styles:
                self.style_suggestions = new_styles
                self.s_version += 1
                with open(f"tmp_tag_{self.safe_title}_styles_v{self.s_version:02d}.txt", 'w', encoding='utf-8') as f:
                    f.write(self.style_suggestions)

    def handle_ending(self):
        confirm = self.handle_input("\n是否继续处理其他歌曲? (y/n):", multiline=False)
        if confirm.lower() in ['y', 'yes']:
            self.state = "INIT"
        else:
            print("再见！")
            sys.exit(0)

if __name__ == "__main__":
    agent = SunoTagAgent()
    agent.run()
