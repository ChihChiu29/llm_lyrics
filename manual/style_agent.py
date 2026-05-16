import os
import re
import sys
import glob
import datetime
from agent_utils import Spinner, OllamaClient, handle_rich_input

class StyleAgent:
    def __init__(self):
        self.ollama = OllamaClient()
        self.state = "INIT"
        self.lyrics_text = ""
        self.song_title = ""
        self.safe_title = ""
        self.styles_content = ""
        self.version = 0
        
        # Predefined colors
        self.C_CYAN = "\033[36m"
        self.C_GRAY = "\033[90m"
        self.C_YELLOW = "\033[33m"
        self.C_GREEN = "\033[32m"
        self.C_RESET = "\033[0m"

        # Load predefined styles
        self.premade_styles = ""
        if os.path.exists("song_style_prompts.md"):
            with open("song_style_prompts.md", 'r', encoding='utf-8') as f:
                self.premade_styles = f.read()

    def run(self):
        print(f"{self.C_CYAN}=== SUNO 风格策划助手 ==={self.C_RESET}")
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
                elif self.state == "STYLE_DISCUSSION":
                    self.handle_style_discussion()
                elif self.state == "ENDING":
                    self.handle_ending()
        except KeyboardInterrupt:
            print(f"\n\n{self.C_YELLOW}[中断]{self.C_RESET} 程序已安全退出。")
            sys.exit(0)

    def show_header(self, title):
        print(f"\n{self.C_CYAN}{'='*40}\n [阶段: {title}] \n{'='*40}{self.C_RESET}")

    def show_help(self):
        print(f"\n{self.C_CYAN}--- SUNO 风格助手: 指令手册 ---{self.C_RESET}")
        print("  /help   - 显示此详细帮助")
        print("  /model  - 切换 Ollama 模型")
        print("  /new    - 开启新任务")
        print("  /quit   - 立即退出程序")
        print("\n  Enter: 提交内容 | Ctrl-J: 换行")
        print("  vX (版本号): 回退到特定版本")
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
            tag = f"{self.C_CYAN}(当前){self.C_RESET}" if m == self.ollama.model else ""
            print(f"{i+1}. {m} {tag}")
        
        choice = self.handle_common_input("\n选择模型编号 (回车当前): ", multiline=False)
        if choice == "/new":
            return
        if not choice:
            if not self.ollama.model:
                self.ollama.model = models[0]
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                self.ollama.model = models[idx]
                print(f"已切换至: {self.C_GREEN}{self.ollama.model}{self.C_RESET}")
        except:
            if not self.ollama.model:
                self.ollama.model = models[0]

    def save_init(self):
        with open("tmp_style_init.md", 'w', encoding='utf-8') as f:
            f.write(f"Model: {self.ollama.model}\nTitle: {self.song_title}\n")

    def resume_workflow(self):
        if os.path.exists("tmp_style_init.md"):
            with open("tmp_style_init.md", 'r', encoding='utf-8') as f:
                content = f.read()
                m = re.search(r"Model: (.*)", content)
                self.ollama.model = m.group(1).strip() if m else ""
                t = re.search(r"Title: (.*)", content)
                if t: 
                    self.song_title = t.group(1).strip()
                    self.safe_title = re.sub(r'[\\/*?:"<>|]', "", self.song_title).replace(" ", "_")
            if self.ollama.model:
                print(f"\n{self.C_CYAN}--- 待处理歌曲: {self.C_RESET}{self.song_title}")
                confirm = self.handle_common_input(f"是否继续使用模型 {self.ollama.model}? (y/n): ", multiline=False)
                if confirm.lower() not in ['y', 'yes', '']:
                    self.select_model()
                    self.save_init()

        if self.safe_title:
            v0_file = f"tmp_style_{self.safe_title}_v00.txt"
            if os.path.exists(v0_file):
                with open(v0_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    parts = content.split('\n\n', 1)
                    self.lyrics_text = parts[1] if len(parts) > 1 else parts[0]
            
            style_files = sorted(glob.glob(f"tmp_style_{self.safe_title}_v*.txt"), key=lambda x: int(re.search(r'_v(\d+)', x).group(1)))
            style_files = [f for f in style_files if "_v00" not in f]
            if style_files:
                self.version = int(re.search(r'_v(\d+)', style_files[-1]).group(1))
                with open(style_files[-1], 'r', encoding='utf-8') as f:
                    self.styles_content = f.read()
                self.state = "STYLE_DISCUSSION"
                print(f"{self.C_GREEN}已成功恢复!{self.C_RESET}")
                return
            elif self.song_title:
                self.state = "STYLE_DISCUSSION" if self.lyrics_text else "INPUT_LYRICS"
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
        title = self.handle_common_input("请输入歌曲标题 (输入后将尝试从 lyrics_tagged/ 目录读取):", multiline=False)
        if title == "/new":
            self.clear_tmp_files()
            return
        if not title:
            return
        self.song_title = title
        self.safe_title = re.sub(r'[\\/*?:"<>|\r\n\t]', "", self.song_title).replace(" ", "_")[:40]
        
        load_path = os.path.join("lyrics_tagged", f"{self.safe_title}.txt")
        if os.path.exists(load_path):
            print(f"\n{self.C_CYAN}--- 发现已存在的歌词文件: {self.C_RESET}{load_path}")
            if self.handle_common_input("是否加载该歌词文件? (y/n): ", multiline=False).lower() in ['y', 'yes', '']:
                with open(load_path, 'r', encoding='utf-8') as f:
                    self.lyrics_text = f.read()
                self.save_init()
                self.version = 0
                with open(f"tmp_style_{self.safe_title}_v00.txt", 'w', encoding='utf-8') as f:
                    f.write(f"{self.song_title}\n\n{self.lyrics_text}")
                self.state = "STYLE_DISCUSSION"
                return
        
        self.save_init()
        self.state = "INPUT_LYRICS"

    def handle_input_lyrics(self):
        self.show_header("输入歌词内容")
        print(f"{self.C_GRAY}当前: {self.C_CYAN}{self.song_title}{self.C_RESET}")
        lyrics_input = self.handle_common_input("请粘贴歌词全文 (直接从终端输入):")
        if lyrics_input == "/new":
            self.clear_tmp_files()
            self.state = "INIT"
            return
        if not lyrics_input:
            return
        self.lyrics_text = lyrics_input
        self.version = 0
        with open(f"tmp_style_{self.safe_title}_v00.txt", 'w', encoding='utf-8') as f:
            f.write(f"{self.song_title}\n\n{lyrics_input}")
        self.state = "STYLE_DISCUSSION"

    def handle_style_discussion(self):
        self.show_header("风格策划")
        system_prompt = (
            "资深风格策划师。直接输出列表，绝不解释，不要任何废话。\n"
            "输出必须包含两部分：\n\n"
            "=== Generated Styles ===\n"
            "生成 5 个详尽风格（15-25词）。每个风格必须是一串逗号分隔的英文标签（如 'Trap Metal, Dark, 120 BPM'）。加 '-' 开头，空行分隔。\n\n"
            "=== Selected Pre-made Styles ===\n"
            "从用户提供的预设列表中挑选最合适的 5 个。必须完全照抄原文。加 '-' 开头，空行分隔。"
        )
        
        just_streamed = False
        if self.version == 0:
            prompt_text = f"歌词内容：\n{self.lyrics_text}\n\n"
            if self.premade_styles:
                prompt_text += f"预设风格列表：\n{self.premade_styles}\n"
            
            self.styles_content = self.ollama.call(prompt_text, system_prompt=system_prompt, spinner=Spinner())
            if self.styles_content:
                self.version = 1
                with open(f"tmp_style_{self.safe_title}_v01.txt", 'w', encoding='utf-8') as f:
                    f.write(self.styles_content)
                just_streamed = True
            else:
                return

        if not just_streamed:
            print(f"\n--- {self.C_CYAN}当前风格 (v{self.version:02d}){self.C_RESET} ---")
            print(self.styles_content)
            print(f"---{'-'*20}---")

        suggestion = self.handle_common_input("\n风格建议 (ok 批准并保存, vX 回退, /c 仅讨论):")
        if suggestion == "/new":
            self.clear_tmp_files()
            self.state = "INIT"
            return

        back_match = re.search(r"back to v(\d+)", suggestion.lower()) or re.search(r"^v(\d+)$", suggestion.lower())
        if back_match:
            v = int(back_match.group(1))
            back_file = f"tmp_style_{self.safe_title}_v{v:02d}.txt"
            if os.path.exists(back_file):
                self.version = v
                with open(back_file, 'r', encoding='utf-8') as f:
                    self.styles_content = f.read()
                print(f"已回退 v{v:02d}")
                return

        intent, clean_input = self.ollama.check_intent(suggestion, self.song_title, "风格阶段")
        if intent == "APPROVE":
            if not os.path.exists("song_styles_output"):
                os.makedirs("song_styles_output")
            save_path = os.path.join("song_styles_output", f"{self.safe_title}_styles.txt")
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(f"Song: {self.song_title}\n\n")
                f.write(f"{self.styles_content}\n\n")
                f.write(f"=== Metadata ===\nModel: {self.ollama.model}\nSaved At: {now}\n")
            print(f"\n{self.C_GREEN}已保存到: {save_path}{self.C_RESET}")
            self.clear_tmp_files()
            self.state = "ENDING"
            return
        elif intent == "CHAT":
            print(f"\n{self.C_CYAN}[策划师见解]:{self.C_RESET}")
            self.ollama.call(f"咨询风格建议：'{clean_input}'\n内容：\n{self.styles_content}", 
                             system_prompt="你是风格策划师。直接回答用户，不输出方案，不输出列表。", spinner=Spinner())
        elif intent == "MODIFY":
            print(f"\n正在修改 (v{self.version:02d} -> v{self.version+1:02d})...")
            
            prompt_text = f"修改建议：'{clean_input}'\n当前风格：\n{self.styles_content}\n\n"
            if self.premade_styles:
                prompt_text += f"参考的预设风格列表(只能从中挑选作为'Selected Pre-made Styles')：\n{self.premade_styles}\n"

            new_styles = self.ollama.call(prompt_text, system_prompt=system_prompt, spinner=Spinner())
            if new_styles:
                self.styles_content = new_styles
                self.version += 1
                with open(f"tmp_style_{self.safe_title}_v{self.version:02d}.txt", 'w', encoding='utf-8') as f:
                    f.write(self.styles_content)

    def handle_ending(self):
        if self.handle_common_input("\n是否继续处理其他歌曲? (y/n):", multiline=False).lower() in ['y', 'yes', '']:
            self.state = "INIT"
        else:
            print("再见！")
            sys.exit(0)

    def clear_tmp_files(self):
        for f in glob.glob("tmp_style_*"):
            try:
                os.remove(f)
            except:
                pass
        self.song_title = ""
        self.safe_title = ""
        self.version = 0

if __name__ == "__main__":
    agent = StyleAgent()
    agent.run()
