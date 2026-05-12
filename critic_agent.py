import os
import re
import sys
import glob
import datetime
from agent_utils import Spinner, OllamaClient, handle_rich_input

class LyricCriticAgent:
    def __init__(self):
        self.ollama = OllamaClient()
        self.state = "INIT"
        self.lyrics_content = ""
        self.song_title = ""
        self.file_path = ""
        
        # 预设颜色
        self.C_CYAN = "\033[36m"
        self.C_GRAY = "\033[90m"
        self.C_YELLOW = "\033[33m"
        self.C_GREEN = "\033[32m"
        self.C_RED = "\033[31m"
        self.C_RESET = "\033[0m"

        # 加载系统提示词
        self.system_prompt = ""
        prompt_path = "prompts/critic_system.md"
        if os.path.exists(prompt_path):
            with open(prompt_path, 'r', encoding='utf-8') as f:
                self.system_prompt = f.read()

    def run(self):
        print(f"{self.C_CYAN}=== 资深音乐制作人批评家 (Producer Critic) ==={self.C_RESET}")
        print("提示: 随时输入 /help 查看可用命令")
        
        try:
            while True:
                if self.state == "INIT":
                    self.handle_init()
                elif self.state == "SELECT_FILE":
                    self.handle_select_file()
                elif self.state == "CRITIC_LOOP":
                    self.handle_critic_loop()
                elif self.state == "ENDING":
                    self.handle_ending()
        except KeyboardInterrupt:
            print(f"\n\n{self.C_YELLOW}[中断]{self.C_RESET} 程序已安全退出。")
            sys.exit(0)

    def show_header(self, title):
        print(f"\n{self.C_CYAN}{'='*40}\n [阶段: {title}] \n{'='*40}{self.C_RESET}")

    def show_help(self):
        print(f"\n{self.C_CYAN}--- 批评助手: 指令手册 ---{self.C_RESET}")
        print("  /help   - 显示此帮助")
        print("  /model  - 切换 Ollama 模型")
        print("  /new    - 重新选择歌曲")
        print("  /quit   - 退出程序")
        print("\n  Enter: 提交内容 | Ctrl-J: 换行")
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

    def handle_init(self):
        self.show_header("初始化")
        if not self.ollama.model:
            self.select_model()
        if not self.ollama.model:
            sys.exit(1)
        self.state = "SELECT_FILE"

    def handle_select_file(self):
        self.show_header("选择待评价歌曲")
        lyrics_dir = "lyrics"
        files = sorted(glob.glob(os.path.join(lyrics_dir, "*.txt")))
        
        if not files:
            print(f"{self.C_YELLOW}在 {lyrics_dir} 目录下未找到任何歌词文件。{self.C_RESET}")
            print("请输入原始歌词内容进行评价（或者将文件放入 lyrics 目录后重新启动）：")
            content = self.handle_common_input("歌词内容:")
            if content == "/new": return
            if not content: return
            self.lyrics_content = content
            self.song_title = "未命名歌曲"
            self.state = "CRITIC_LOOP"
            return

        print(f"{self.C_GRAY}找到以下歌词文件:{self.C_RESET}")
        for i, f in enumerate(files):
            print(f"{i+1}. {os.path.basename(f)}")
        
        choice = self.handle_common_input("\n选择文件编号 (或输入 /new 开启新任务): ", multiline=False)
        if choice == "/new":
            return
        if not choice:
            return
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(files):
                self.file_path = files[idx]
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.lyrics_content = f.read()
                self.song_title = os.path.basename(self.file_path)
                self.state = "CRITIC_LOOP"
            else:
                print(f"{self.C_RED}无效编号。{self.C_RESET}")
        except ValueError:
            print(f"{self.C_RED}请输入数字。{self.C_RESET}")

    def handle_critic_loop(self):
        self.show_header(f"制作人评审: {self.song_title}")
        
        # 第一次自动进行评审
        print(f"{self.C_GRAY}正在阅读并分析歌词与风格...{self.C_RESET}")
        criticism = self.ollama.call(f"请评审以下歌词和风格：\n\n{self.lyrics_content}", 
                                     system_prompt=self.system_prompt, 
                                     spinner=Spinner("制作人正在仔细审阅"))
        
        while True:
            suggestion = self.handle_common_input("\n继续追问制作人 (ok 结束本次评审, /new 换一首歌, /c 仅讨论):")
            if suggestion == "/new":
                self.state = "SELECT_FILE"
                return
            if suggestion.lower() in ['ok', 'done', '好的']:
                self.state = "ENDING"
                return
            
            intent, clean_input = self.ollama.check_intent(suggestion, self.song_title, "评审阶段")
            
            if intent == "APPROVE":
                self.state = "ENDING"
                return
            else:
                # 无论是 CHAT 还是 MODIFY (在这里 MODIFY 意味着对批评的追问或要求针对某点深入批评)
                self.ollama.call(f"针对《{self.song_title}》，用户追问：'{clean_input}'\n上下文歌词内容：\n{self.lyrics_content}", 
                                 system_prompt=self.system_prompt, 
                                 spinner=Spinner("制作人正在回应"))

    def handle_ending(self):
        choice = self.handle_common_input("\n是否评价其他歌曲? (y/n):", multiline=False)
        if choice.lower() in ['y', 'yes', '']:
            self.state = "SELECT_FILE"
        else:
            print(f"{self.C_CYAN}制作人甩手走出了录音棚。再见！{self.C_RESET}")
            sys.exit(0)

if __name__ == "__main__":
    agent = LyricCriticAgent()
    agent.run()
