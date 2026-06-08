import os
import re
import sys
import glob
import datetime
from agent_utils import Spinner, OllamaClient, handle_rich_input

class SimpleLyricAgent:
    def __init__(self):
        self.ollama = OllamaClient()
        self.style = ""
        self.state = "INIT"
        self.gen_version = 0
        self.song_title = ""
        self.safe_title = ""
        self.generated_content = ""
        
        # 预设颜色
        self.C_CYAN = "\033[36m"
        self.C_GRAY = "\033[90m"
        self.C_YELLOW = "\033[33m"
        self.C_GREEN = "\033[32m"
        self.C_RED = "\033[31m"
        self.C_RESET = "\033[0m"

        # 加载提示词模板
        self.critic_system_prompt = self._load_prompt("prompts/critic_system.md", "你是一位严苛的音乐制作人。")
        self.writer_system_prompt = self._load_prompt("prompts/writer_system.md", "你是一位专业的歌词创作人。")
        self.gen_template = self._load_prompt("prompts/simple_gen.md", "创作歌曲: {style}")
        self.improve_template = self._load_prompt("prompts/simple_improve.md", "根据反馈修改: {feedback}")
        
        # 增强批评家：增加风格与歌词匹配度的审查
        self.critic_system_prompt += "\n\n5. **风格匹配度**：特别审查给出的 Style Prompts 是否能完美支撑歌词的情感和节奏。标注与风格提示词是否统一。"

    def _load_prompt(self, path, default):
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except:
                return default
        return default

    def get_critic_feedback(self, content, context=""):
        """让批评家对内容进行评价"""
        print(f"\n{self.C_YELLOW}[正在请制作人过目...]{self.C_RESET}")
        full_prompt = f"【背景上下文】\n{context}\n\n【待评审内容 (包含歌词与风格提示词)】\n{content}"
        feedback = self.ollama.call(full_prompt, 
                                     system_prompt=self.critic_system_prompt, 
                                     spinner=Spinner("制作人正在审阅"))
        return feedback

    def auto_improve_with_critic(self, content, max_rounds=50, context=""):
        """自动根据批评意见进行迭代优化"""
        current_content = content
        for i in range(max_rounds):
            feedback = self.get_critic_feedback(current_content, context=context)
            
            score = 0
            score_match = re.search(r"【得分：(\d+(?:\.\d+)?)/10】", feedback)
            if score_match:
                score = float(score_match.group(1))
                print(f"{self.C_CYAN}>>> 制作人评分: {self.C_YELLOW}{score}/10{self.C_RESET}")
                
                if score >= 9.5:
                    print(f"{self.C_GREEN}[制作人评分达到 {score}，批准通过！]{self.C_RESET}")
                    return current_content

            if i < max_rounds - 1:
                print(f"{self.C_YELLOW}[得分未达标 ({score}/10)，正在进行第 {i+1} 轮优化...]{self.C_RESET}")
            else:
                print(f"{self.C_RED}[已达到最大优化轮数，输出当前版本。]{self.C_RESET}")
                return current_content
            
            mod_prompt = self.improve_template.format(context=context, feedback=feedback, content=current_content)
            current_content = self.ollama.call(mod_prompt, system_prompt=self.writer_system_prompt, spinner=Spinner("制作人正在指挥修改"))
            self.gen_version += 1
            with open(f"tmp_simple_gen_{self.gen_version:02d}.md", 'w', encoding='utf-8') as f:
                f.write(current_content)
                    
        return current_content

    def run(self):
        print(f"{self.C_CYAN}=== 极简歌词与风格创作助手 ==={self.C_RESET}")
        
        try:
            while True:
                if self.state == "INIT":
                    self.handle_init()
                elif self.state == "GENERATION":
                    self.handle_generation()
                elif self.state == "ENDING":
                    self.handle_ending()
        except KeyboardInterrupt:
            print(f"\n\n{self.C_YELLOW}[中断]{self.C_RESET} 程序已安全退出。")
            sys.exit(0)

    def handle_init(self):
        # 模型选择
        models = self.ollama.get_models()
        if not models:
            print(f"{self.C_YELLOW}无法连接 Ollama。{self.C_RESET}")
            sys.exit(1)
        print(f"\n{self.C_GRAY}可用模型:{self.C_RESET}")
        for i, m in enumerate(models):
            print(f"{i+1}. {m}")
        
        choice = handle_rich_input("\n选择模型编号: ", multiline=False)
        try:
            idx = int(choice) - 1
            self.ollama.model = models[idx]
        except:
            self.ollama.model = models[0]
        print(f"使用模型: {self.C_GREEN}{self.ollama.model}{self.C_RESET}")

        # 风格选择
        styles = []
        if os.path.exists("song_styles.md"):
            with open("song_styles.md", 'r', encoding='utf-8') as f:
                styles = [line.strip().lstrip("- ").strip() for line in f if line.strip().startswith("-")]
        
        if styles:
            print(f"\n{self.C_GRAY}可用风格建议:{self.C_RESET}")
            for i, s in enumerate(styles[:10]):
                print(f"{i+1}. {s}")
        
        self.style = handle_rich_input("\n请输入歌曲核心风格/意境: ", multiline=False)
        if not self.style and styles:
            self.style = styles[0]
        
        self.state = "GENERATION"

    def handle_generation(self):
        print(f"\n{self.C_CYAN}正在全速生成歌词与风格方案...{self.C_RESET}")
        
        gen_prompt = self.gen_template.format(style=self.style)
        
        content = self.ollama.call(gen_prompt, system_prompt=self.writer_system_prompt, spinner=Spinner("正在创作"))
        if not content:
            return

        self.generated_content = self.auto_improve_with_critic(content, context=f"核心风格要求：{self.style}")
        
        print(f"\n{self.C_GREEN}=== 创作完成 (最终预览) ==={self.C_RESET}")
        print(self.generated_content)
        
        # 提取标题
        title_match = re.search(r"歌曲标题：(.*?)\n", self.generated_content)
        if title_match:
            self.song_title = title_match.group(1).strip()
        else:
            # 如果提取失败，请模型取一个
            print(f"\n{self.C_GRAY}正在生成歌曲标题...{self.C_RESET}")
            self.song_title = self.ollama.call(f"为以下内容取个简洁标题（10字内，仅输出标题）：\n{self.generated_content}", stream=False, spinner=Spinner("正在命名")).strip().replace('"', '')
        
        self.safe_title = re.sub(r'[\\/*?:"<>|\r\n\t]', "", self.song_title).replace(" ", "_")[:40]
        if not self.safe_title: self.safe_title = f"Untitled_{datetime.datetime.now().strftime('%H%M%S')}"
        
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        save_path = os.path.join("lyrics", f"{today}_{self.safe_title}.txt")
        if not os.path.exists("lyrics"): os.makedirs("lyrics")
        
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(self.generated_content + f"\n\n=== Metadata ===\nModel: {self.ollama.model}\nStyle: {self.style}\n")
        
        print(f"\n{self.C_GREEN}已保存到: {save_path}{self.C_RESET}")
        self.state = "ENDING"

    def handle_ending(self):
        choice = handle_rich_input("\n是否继续创作? (y/n): ", multiline=False)
        if choice.lower() in ['y', 'yes', '']:
            self.gen_version = 0
            self.state = "INIT"
            # 清理临时文件
            for f in glob.glob("tmp_simple_gen_*"):
                try: os.remove(f)
                except: pass
        else:
            sys.exit(0)

if __name__ == "__main__":
    agent = SimpleLyricAgent()
    agent.run()
