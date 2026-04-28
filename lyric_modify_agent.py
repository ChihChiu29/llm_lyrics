import os
import re
import sys
import glob
import datetime
from agent_utils import Spinner, OllamaClient, handle_rich_input

class LyricModifyAgent:
    def __init__(self):
        self.ollama = OllamaClient()
        self.state = "INIT"
        self.lyrics_original = ""
        self.song_title = ""
        self.safe_title = ""
        self.modified_lyrics = ""
        self.version = 0
        
        # 预设颜色
        self.C_CYAN = "\033[36m"
        self.C_GRAY = "\033[90m"
        self.C_YELLOW = "\033[33m"
        self.C_GREEN = "\033[32m"
        self.C_RESET = "\033[0m"

    def run(self):
        print(f"{self.C_CYAN}=== 歌词修改助手 (Ultimate Edition) ==={self.C_RESET}")
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
                elif self.state == "MODIFY_LOOP":
                    self.handle_modify_loop()
                elif self.state == "ENDING":
                    self.handle_ending()
        except KeyboardInterrupt:
            print(f"\n\n{self.C_YELLOW}[中断]{self.C_RESET} 程序已安全退出。")
            sys.exit(0)

    def show_header(self, title):
        print(f"\n{self.C_CYAN}{'='*40}\n [阶段: {title}] \n{'='*40}{self.C_RESET}")

    def show_help(self):
        print(f"\n{self.C_CYAN}--- 歌词修改助手: 指令手册 ---{self.C_RESET}")
        print("  /help   - 显示此帮助")
        print("  /model  - 切换 Ollama 模型")
        print("  /new    - 开启新任务")
        print("  /quit   - 退出程序")
        print("\n  Enter: 提交内容 | Ctrl-J: 换行")
        print("  vX (如 v1): 在修改阶段跳回到特定版本")
        print("-" * 30 + "\n")

    def handle_common_input(self, prompt_text, multiline=True):
        """处理带有指令拦截的输入"""
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
            print(f"{self.C_YELLOW}未找到 Ollama 模型。{self.C_RESET}")
            return
        print(f"\n{self.C_GRAY}可用模型:{self.C_RESET}")
        for i, m in enumerate(models):
            tag = f"{self.C_CYAN}(当前){self.C_RESET}" if m == self.ollama.model else ""
            print(f"{i+1}. {m} {tag}")
        
        choice = self.handle_common_input("\n选择模型编号 (回车当前/默认): ", multiline=False)
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
        with open("tmp_mod_init.md", 'w', encoding='utf-8') as f:
            f.write(f"Model: {self.ollama.model}\nTitle: {self.song_title}\n")

    def resume_workflow(self):
        if os.path.exists("tmp_mod_init.md"):
            with open("tmp_mod_init.md", 'r', encoding='utf-8') as f:
                content = f.read()
                m = re.search(r"Model: (.*)", content)
                self.ollama.model = m.group(1).strip() if m else ""
                t = re.search(r"Title: (.*)", content)
                if t: 
                    self.song_title = t.group(1).strip()
                    self.safe_title = re.sub(r'[\\/*?:"<>|]', "", self.song_title).replace(" ", "_")
            
            if self.ollama.model:
                print(f"\n{self.C_CYAN}--- 发现未完成任务: {self.C_RESET}{self.song_title}")
                confirm = self.handle_common_input(f"是否继续使用模型 {self.ollama.model}? (y/n): ", multiline=False)
                if confirm.lower() not in ['y', 'yes', '']:
                    self.select_model()
                    self.save_init()

        if self.safe_title:
            v0_file = f"tmp_mod_{self.safe_title}_v00.txt"
            if os.path.exists(v0_file):
                with open(v0_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    parts = content.split('\n\n', 1)
                    self.lyrics_original = parts[1] if len(parts) > 1 else parts[0]
            
            mod_files = sorted(glob.glob(f"tmp_mod_{self.safe_title}_v*.txt"), key=lambda x: int(re.search(r'_v(\d+)', x).group(1)))
            if len(mod_files) > 1:
                self.version = int(re.search(r'_v(\d+)', mod_files[-1]).group(1))
                with open(mod_files[-1], 'r', encoding='utf-8') as f:
                    self.modified_lyrics = f.read()
                self.state = "MODIFY_LOOP"
                print(f"{self.C_GREEN}已成功恢复!{self.C_RESET} (版本 {self.version:02d})")
                return
            elif self.song_title:
                self.state = "INPUT_LYRICS"
                return
        self.state = "INIT"

    def handle_init(self):
        self.show_header("初始化设置")
        if not self.ollama.model:
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
        
        save_path = os.path.join("lyrics_modified", f"{self.safe_title}.txt")
        if os.path.exists(save_path):
            print(f"\n{self.C_CYAN}--- 发现已有修改记录: {self.C_RESET}{self.song_title}")
            if self.handle_common_input("是否加载并重修? (y/n): ", multiline=False).lower() in ['y', 'yes', '']:
                with open(save_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.modified_lyrics = content.strip()
                self.lyrics_original = self.modified_lyrics
                self.version = 1
                self.save_init()
                with open(f"tmp_mod_{self.safe_title}_v00.txt", 'w', encoding='utf-8') as f:
                    f.write(f"{self.song_title}\n\n{self.lyrics_original}")
                with open(f"tmp_mod_{self.safe_title}_v01.txt", 'w', encoding='utf-8') as f:
                    f.write(self.modified_lyrics)
                self.state = "MODIFY_LOOP"
                return
        self.save_init()
        self.state = "INPUT_LYRICS"

    def handle_input_lyrics(self):
        self.show_header("输入原始歌词")
        print(f"{self.C_GRAY}当前: {self.C_CYAN}{self.song_title}{self.C_RESET}")
        lyrics_input = self.handle_common_input("请粘贴需要修改的歌词内容:")
        if lyrics_input == "/new":
            self.clear_tmp_files()
            self.state = "INIT"
            return
        if not lyrics_input:
            return
        self.lyrics_original = lyrics_input
        self.modified_lyrics = lyrics_input
        self.version = 0
        with open(f"tmp_mod_{self.safe_title}_v00.txt", 'w', encoding='utf-8') as f:
            f.write(f"{self.song_title}\n\n{lyrics_input}")
        self.state = "MODIFY_LOOP"

    def handle_modify_loop(self):
        self.show_header("歌词修改与讨论")
        system_prompt = (
            "你是一位专业的歌词创作人和文学顾问。你的任务是根据用户的建议修改歌词。\n\n"
            "【修改原则】\n"
            "1. **韵律优化**：检查押韵是否顺滑，节奏是否适合演唱。\n"
            "2. **措辞打磨**：提升文字的文学性、画面感或力量感。\n"
            "3. **意境保持**：在不违背用户意图的前提下，深化歌词的主题。\n"
            "4. **结构完整**：输出必须包含歌曲标题和修改后的完整歌词全文。"
        )

        if self.version == 0:
            print(f"\n{self.C_GRAY}初始版本加载成功。你可以提出具体的修改建议。{self.C_RESET}")
            self.version = 1
            with open(f"tmp_mod_{self.safe_title}_v01.txt", 'w', encoding='utf-8') as f:
                f.write(self.modified_lyrics)

        print(f"\n--- {self.C_CYAN}当前歌词预览 (v{self.version:02d}){self.C_RESET} ---")
        print(self.modified_lyrics)
        print(f"---{'-'*20}---")
        
        suggestion = self.handle_common_input("\n建议/提问 (ok 批准并保存, vX 回退, /c 仅讨论):")
        if suggestion == "/new":
            self.clear_tmp_files()
            self.state = "INIT"
            return

        # 回退逻辑
        back_match = re.search(r"back to v(\d+)", suggestion.lower()) or re.search(r"^v(\d+)$", suggestion.lower())
        if back_match:
            v = int(back_match.group(1))
            back_file = f"tmp_mod_{self.safe_title}_v{v:02d}.txt"
            if os.path.exists(back_file):
                self.version = v
                with open(back_file, 'r', encoding='utf-8') as f:
                    self.modified_lyrics = f.read()
                print(f"已回退 v{v:02d}")
                return
            else:
                print(f"版本 v{v:02d} 不存在。")
                return

        intent, clean_input = self.ollama.check_intent(suggestion, self.song_title, "歌词修改阶段")
        if intent == "APPROVE":
            if not os.path.exists("lyrics_modified"):
                os.makedirs("lyrics_modified")
            save_path = os.path.join("lyrics_modified", f"{self.safe_title}.txt")
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(self.modified_lyrics + f"\n\n=== Metadata ===\nModel: {self.ollama.model}\nModified At: {now}\n")
            print(f"\n{self.C_GREEN}全部完成！{self.C_RESET} 已保存到: {save_path}")
            self.clear_tmp_files()
            self.state = "ENDING"
            return
        elif intent == "CHAT":
            print(f"\n{self.C_CYAN}[顾问建议]:{self.C_RESET}")
            self.ollama.call(f"咨询关于《{self.song_title}》的歌词建议：'{clean_input}'\n当前内容：\n{self.modified_lyrics}", 
                             system_prompt="你是文学顾问。直接回答建议，不要输出多方案，不要输出完整歌词。", spinner=Spinner())
        elif intent == "MODIFY":
            print(f"\n正在应用修改 (v{self.version:02d} -> v{self.version+1:02d})...")
            prompt_text = f"修改建议：'{clean_input}'\n当前版本内容：\n{self.modified_lyrics}\n请直接输出修改后的完整歌词（包含标题）。"
            new_lyrics = self.ollama.call(prompt_text, system_prompt=system_prompt, spinner=Spinner())
            if new_lyrics:
                self.modified_lyrics = new_lyrics
                self.version += 1
                with open(f"tmp_mod_{self.safe_title}_v{self.version:02d}.txt", 'w', encoding='utf-8') as f:
                    f.write(self.modified_lyrics)

    def handle_ending(self):
        choice = self.handle_common_input("\n是否继续处理其他歌曲? (y/n):", multiline=False)
        if choice.lower() in ['y', 'yes', '']:
            self.state = "INIT"
        else:
            print("感谢使用，再见！")
            sys.exit(0)

    def clear_tmp_files(self):
        for f in glob.glob("tmp_mod_*"):
            try:
                os.remove(f)
            except:
                pass
        self.song_title = ""
        self.safe_title = ""
        self.version = 0

if __name__ == "__main__":
    agent = LyricModifyAgent()
    agent.run()
