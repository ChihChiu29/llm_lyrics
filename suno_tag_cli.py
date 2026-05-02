import os
import re
import sys
import datetime
from agent_utils import Spinner, OllamaClient, handle_rich_input

class SunoTagCLI:
    def __init__(self):
        self.ollama = OllamaClient()
        self.C_CYAN = "\033[36m"
        self.C_GRAY = "\033[90m"
        self.C_YELLOW = "\033[33m"
        self.C_GREEN = "\033[32m"
        self.C_RESET = "\033[0m"
        
        # Load prompt templates
        self.tagging_prompt = self._load_prompt("prompts/tagging_system.md", "你是一位专业的 SUNO AI 音乐总监。为歌词添加专业的 Meta Tags。严禁修改歌词文字。")
        self.style_prompt = self._load_prompt("prompts/style_system.md", "你是一位资深风格策划师。为歌词策划 5 个详尽的 SUNO Style Prompts。")

    def _load_prompt(self, path, default):
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except:
                return default
        return default

    def select_model(self):
        models = self.ollama.get_models()
        if not models:
            print(f"{self.C_YELLOW}无法连接 Ollama。{self.C_RESET}")
            sys.exit(1)
        
        print(f"\n{self.C_GRAY}可用模型:{self.C_RESET}")
        for i, m in enumerate(models):
            print(f"{i+1}. {m}")
        
        while True:
            choice = handle_rich_input("\n请选择模型编号: ", multiline=False)
            if choice == "/quit": sys.exit(0)
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(models):
                    self.ollama.model = models[idx]
                    print(f"已选择模型: {self.C_GREEN}{self.ollama.model}{self.C_RESET}")
                    break
            except:
                pass
            print(f"{self.C_YELLOW}无效输入，请重新输入编号。{self.C_RESET}")

    def run(self):
        print(f"{self.C_CYAN}=== SUNO 歌词标注命令行版 ==={self.C_RESET}")
        
        if not os.path.exists("lyrics_tagged"):
            os.makedirs("lyrics_tagged")
            
        self.select_model()
        
        while True:
            print(f"\n{self.C_CYAN}--- 新歌曲任务 ---{self.C_RESET}")
            print(f"{self.C_CYAN}请输入歌曲信息 (第一行为标题，后面为歌词):{self.C_RESET}")
            print(f"{self.C_GRAY}(输入 /quit 退出，按下 Ctrl-J 换行，Enter 提交){self.C_RESET}")
            
            user_input = handle_rich_input(">")
            if user_input == "/quit" or not user_input:
                print("程序已退出。")
                break
                
            lines = user_input.split('\n')
            song_title = lines[0].strip()
            lyrics_original = "\n".join(lines[1:]).strip()
            
            if not song_title or not lyrics_original:
                print(f"{self.C_YELLOW}错误: 标题和歌词都不能为空。{self.C_RESET}")
                continue
                
            safe_title = re.sub(r'[\\/*?:"<>|\r\n\t]', "", song_title).replace(" ", "_")[:40]
            
            # 1. Tagging
            print(f"\n{self.C_CYAN}正在生成标注建议...{self.C_RESET}")
            full_text = f"{song_title}\n\n{lyrics_original}"
            tagged_lyrics = self.ollama.call(full_text, system_prompt=self.tagging_prompt, spinner=Spinner("正在标注"))
            
            if not tagged_lyrics:
                print(f"{self.C_YELLOW}标注生成失败，请重试。{self.C_RESET}")
                continue
                
            # 2. Styles
            print(f"\n{self.C_CYAN}正在策划风格提示词...{self.C_RESET}")
            style_suggestions = self.ollama.call(f"为歌词策划风格：\n\n{tagged_lyrics}", system_prompt=self.style_prompt, spinner=Spinner("正在策划"))
            
            if not style_suggestions:
                print(f"{self.C_YELLOW}风格策划失败，请重试。{self.C_RESET}")
                continue
                
            # 3. Save
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            save_path = os.path.join("lyrics_tagged", f"{today}_{safe_title}.txt")
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(tagged_lyrics + "\n\n=== Suggested Styles ===\n\n" + style_suggestions + f"\n\n=== Metadata ===\nModel: {self.ollama.model}\nSaved At: {now}\n")
                
            print(f"\n{self.C_GREEN}处理完成!{self.C_RESET}")
            print(f"保存路径: {save_path}")

if __name__ == "__main__":
    try:
        cli = SunoTagCLI()
        cli.run()
    except KeyboardInterrupt:
        print("\n已退出。")
        sys.exit(0)
