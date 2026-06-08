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

class LyricAgent:
    def __init__(self):
        self.ollama = OllamaClient()
        self.style = ""
        self.state = "INIT"
        self.description_index = 0
        self.lyrics_index = 0
        self.s_version = 0
        self.song_title = ""
        self.safe_title = ""
        self.current_lyrics = ""
        self.style_suggestions = ""
        
        # 预设颜色
        self.C_CYAN = "\033[36m"
        self.C_GRAY = "\033[90m"
        self.C_YELLOW = "\033[33m"
        self.C_GREEN = "\033[32m"
        self.C_RED = "\033[31m"
        self.C_RESET = "\033[0m"

        # 加载批评家系统提示词
        self.critic_system_prompt = ""
        if os.path.exists("prompts/critic_system.md"):
            with open("prompts/critic_system.md", 'r', encoding='utf-8') as f:
                self.critic_system_prompt = f.read()

    def get_critic_feedback(self, content, context=""):
        """让批评家对内容进行评价"""
        print(f"\n{self.C_YELLOW}[正在请制作人过目...]{self.C_RESET}")
        full_prompt = f"【背景上下文】\n{context}\n\n【待评审内容】\n{content}" if context else f"请评审以下内容：\n\n{content}"
        feedback = self.ollama.call(full_prompt, 
                                     system_prompt=self.critic_system_prompt, 
                                     spinner=Spinner("制作人正在审阅"))
        return feedback

    def auto_improve_with_critic(self, content, stage="LYRICS", max_rounds=50, context=""):
        """自动根据批评意见进行迭代优化，直到得分达到 8 分或以上"""
        current_content = content
        for i in range(max_rounds):
            feedback = self.get_critic_feedback(current_content, context=context)
            
            # 尝试提取分数并高亮显示
            score = 0
            score_match = re.search(r"【得分：(\d+(?:\.\d+)?)/10】", feedback)
            if score_match:
                score = float(score_match.group(1))
                print(f"{self.C_CYAN}>>> 制作人评分: {self.C_YELLOW}{score}/10{self.C_RESET}")
                
                if score >= 8:
                    print(f"{self.C_GREEN}[制作人评分达到 {score}，批准通过！]{self.C_RESET}")
                    return current_content

            # 如果没到 8 分，或者没找到分数，继续优化
            if i < max_rounds - 1:
                print(f"{self.C_YELLOW}[得分未达标 ({score}/10)，正在进行第 {i+1} 轮优化...]{self.C_RESET}")
            else:
                print(f"{self.C_RED}[已达到最大优化轮数 ({max_rounds})，尽管得分仅为 {score}/10，仍将呈现给用户。]{self.C_RESET}")
                return current_content
            
            if stage == "LYRICS":
                improve_template = ""
                if os.path.exists("prompts/critic_improve_lyrics.md"):
                    with open("prompts/critic_improve_lyrics.md", 'r', encoding='utf-8') as f:
                        improve_template = f.read()
                mod_prompt = improve_template.format(feedback=feedback, content=current_content, context=context) if improve_template else f"背景信息：\n{context}\n\n制作人意见：\n{feedback}\n\n当前歌词：\n{current_content}"
                current_content = self.ollama.call(mod_prompt, spinner=Spinner("正在根据意见修改歌词"))
                self.lyrics_index += 1
                with open(f"tmp_song_lyrics_{self.lyrics_index:02d}.md", 'w', encoding='utf-8') as f:
                    f.write(current_content)
            elif stage == "STYLE":
                improve_template = ""
                if os.path.exists("prompts/critic_improve_style.md"):
                    with open("prompts/critic_improve_style.md", 'r', encoding='utf-8') as f:
                        improve_template = f.read()
                mod_prompt = improve_template.format(feedback=feedback, content=current_content, context=context) if improve_template else f"背景信息：\n{context}\n\n制作人意见：\n{feedback}\n\n当前风格：\n{current_content}"
                res = self.ollama.call(mod_prompt, spinner=Spinner("正在根据意见修改风格"))
                current_content = self._strict_clean_styles(res)
                self.s_version += 1
                with open(f"tmp_song_styles_v{self.s_version:02d}.txt", 'w', encoding='utf-8') as f:
                    f.write(current_content)
                    
        return current_content

    def run(self):
        print(f"{self.C_CYAN}=== 中文歌词创作助手 (Ultimate Edition) ==={self.C_RESET}")
        print("提示: 随时输入 /help 查看可用命令")
        self.resume_workflow()
        
        try:
            while True:
                if self.state == "INIT":
                    self.handle_init()
                elif self.state == "SONG_DESCRIPTION":
                    self.handle_song_description()
                elif self.state == "SONG_LYRICS":
                    self.handle_song_lyrics()
                elif self.state == "STYLE_DISCUSSION":
                    self.handle_style_discussion()
                elif self.state == "ENDING":
                    self.handle_ending()
        except KeyboardInterrupt:
            self.stop_spinner = True
            print(f"\n\n{self.C_YELLOW}[中断]{self.C_RESET} 程序已安全退出。")
            sys.exit(0)

    def show_header(self, title):
        print(f"\n{self.C_CYAN}{'='*40}\n [阶段: {title}] \n{'='*40}{self.C_RESET}")

    def show_help(self):
        print(f"\n{self.C_CYAN}--- 创作助手: 指令手册 ---{self.C_RESET}")
        print("  /help   - 显示此详细帮助")
        print("  /model  - 切换 Ollama 模型")
        print("  /new    - 开启新创作")
        print("  /quit   - 退出程序")
        print("\n  Enter: 提交内容 | Ctrl-J: 换行")
        print("  vX: (如 v1) 回退歌词版本")
        print("  svX: (如 sv1) 回退风格版本")
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
                if self.state != "INIT":
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
        with open("tmp_init.md", 'w', encoding='utf-8') as f:
            f.write(f"Model: {self.ollama.model}\nStyle: {self.style}\nTitle: {self.song_title}\n")

    def resume_workflow(self):
        if os.path.exists("tmp_init.md"):
            with open("tmp_init.md", 'r', encoding='utf-8') as f:
                content = f.read()
                m = re.search(r"Model: (.*)", content)
                if m:
                    self.ollama.model = m.group(1).strip()
                s = re.search(r"Style: (.*)", content)
                if s:
                    self.style = s.group(1).strip()
                t = re.search(r"Title: (.*)", content)
                if t:
                    self.song_title = t.group(1).strip()
                    self.safe_title = re.sub(r'[\\/*?:"<>|]', "", self.song_title).replace(" ", "_")
            
            if self.ollama.model:
                print(f"\n{self.C_CYAN}--- 恢复任务: {self.C_RESET}{self.style if not self.song_title else self.song_title}")
                confirm = self.handle_common_input(f"是否继续使用模型 {self.ollama.model}? (y/n): ", multiline=False)
                if confirm.lower() not in ['y', 'yes', '']:
                    self.select_model()
                    self.save_init()

        style_files = sorted(glob.glob("tmp_song_styles_v*.txt"), key=lambda x: int(re.search(r'_v(\d+)', x).group(1)))
        if style_files:
            latest_style = style_files[-1]
            self.s_version = int(re.search(r'_v(\d+)', latest_style).group(1))
            with open(latest_style, 'r', encoding='utf-8') as f:
                self.style_suggestions = f.read()
            self.state = "STYLE_DISCUSSION"

        lyrics_files = sorted(glob.glob("tmp_song_lyrics_*.md"), key=lambda x: int(re.search(r'(\d+)', x).group(1)))
        if lyrics_files and os.path.exists("tmp_song_approved.md"):
            latest_lyrics = lyrics_files[-1]
            self.lyrics_index = int(re.search(r'(\d+)', latest_lyrics).group(1))
            with open(latest_lyrics, 'r', encoding='utf-8') as f:
                self.current_lyrics = f.read()
            if self.state != "STYLE_DISCUSSION":
                self.state = "SONG_LYRICS"
            print(f"{self.C_GREEN}已成功恢复!{self.C_RESET}")
            return

        if os.path.exists("tmp_song_approved.md"):
            self.state = "SONG_LYRICS"
            return

        desc_files = sorted(glob.glob("tmp_song_description_*.md"), key=lambda x: int(re.search(r'(\d+)', x).group(1)))
        if desc_files:
            latest_desc = desc_files[-1]
            self.description_index = int(re.search(r'(\d+)', latest_desc).group(1))
            self.state = "SONG_DESCRIPTION"
            return
        
        self.state = "INIT"

    def handle_init(self):
        self.show_header("初始设置")
        self.select_model()
        if not self.ollama.model:
            sys.exit(1)
        
        styles = []
        if os.path.exists("song_styles.md"):
            with open("song_styles.md", 'r', encoding='utf-8') as f:
                styles = [line.strip().lstrip("- ").strip() for line in f if line.strip().startswith("-")]
        
        if not styles:
            print("找不到 song_styles.md")
            sys.exit(1)
            
        print(f"\n{self.C_GRAY}可用风格:{self.C_RESET}")
        for i, s in enumerate(styles):
            print(f"{i+1}. {s}")
        
        choice = self.handle_common_input("\n选择风格编号或输入自定义 (回车默认1): ", multiline=False)
        if choice == "/new":
            return
        if not choice:
            self.style = styles[0]
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(styles):
                    self.style = styles[idx]
                else:
                    self.style = choice
            except:
                self.style = choice

        self.save_init()
        self.state = "SONG_DESCRIPTION"

    def handle_song_description(self):
        self.show_header("场景描述")
        if self.description_index == 0:
            gen_template = ""
            if os.path.exists("prompts/desc_gen.md"):
                with open("prompts/desc_gen.md", 'r', encoding='utf-8') as f:
                    gen_template = f.read()
            prompt = gen_template.format(style=self.style) if gen_template else f"为风格为 '{self.style}' 的中文歌曲创作独特背景。要有画面感。"
            desc = self.ollama.call(prompt, temperature=1.3, spinner=Spinner("正在构思场景"))
            if desc:
                self.description_index = 1
                with open(f"tmp_song_description_{self.description_index:02d}.md", 'w', encoding='utf-8') as f:
                    f.write(desc)
            else:
                return
        else:
            with open(f"tmp_song_description_{self.description_index:02d}.md", 'r', encoding='utf-8') as f:
                desc = f.read()

        print(f"\n--- {self.C_CYAN}场景预览 (v{self.description_index:02d}){self.C_RESET} ---\n{desc}\n{'-'*20}")
        suggestion = self.handle_common_input("\n建议 (ok 批准进入歌词, vX 回退, /c 讨论):")
        if suggestion == "/new":
            self.clear_tmp_files()
            self.state = "INIT"
            return

        back_match = re.search(r"back to v(\d+)", suggestion.lower()) or re.search(r"^v(\d+)$", suggestion.lower())
        if back_match:
            v = int(back_match.group(1))
            back_file = f"tmp_song_description_{v:02d}.md"
            if os.path.exists(back_file):
                self.description_index = v
                print(f"已回退 v{v:02d}")
                return

        intent, clean_input = self.ollama.check_intent(suggestion, self.style, "描述确认")
        if intent == "APPROVE":
            with open("tmp_song_approved.md", 'w', encoding='utf-8') as f:
                f.write(desc)
            self.state = "SONG_LYRICS"
            self.lyrics_index = 0
            return
        elif intent == "CHAT":
            self.ollama.call(f"讨论：'{clean_input}'\n内容：\n{desc}", system_prompt="你是顾问。只分析不输出完整内容。", spinner=Spinner())
        elif intent == "MODIFY":
            print(f"\n正在修改场景 (v{self.description_index:02d} -> v{self.description_index+1:02d})...")
            new_desc = self.ollama.call(f"建议：'{clean_input}'\n当前：\n{desc}", spinner=Spinner())
            if new_desc:
                self.description_index += 1
                with open(f"tmp_song_description_{self.description_index:02d}.md", 'w', encoding='utf-8') as f:
                    f.write(new_desc)

    def handle_song_lyrics(self):
        self.show_header("歌词创作")
        with open("tmp_song_approved.md", 'r', encoding='utf-8') as f:
            approved_desc = f.read()
        
        if self.lyrics_index == 0:
            gen_template = ""
            if os.path.exists("prompts/lyric_gen.md"):
                with open("prompts/lyric_gen.md", 'r', encoding='utf-8') as f:
                    gen_template = f.read()
            prompt = gen_template.format(desc=approved_desc, style=self.style) if gen_template else f"根据场景创作歌词，并添加专业的 SUNO Meta Tags（如 [Verse], [Chorus] 等）：\n{approved_desc}\n\n风格：{self.style}\n要求：标注独立占行，置于段落上方，使用英文中括号 []。"
            lyrics = self.ollama.call(prompt, spinner=Spinner("正在谱写带标注的歌词"))
            if lyrics:
                self.lyrics_index = 1
                with open(f"tmp_song_lyrics_{self.lyrics_index:02d}.md", 'w', encoding='utf-8') as f:
                    f.write(lyrics)
                
                # 自动请批评家优化
                lyrics = self.auto_improve_with_critic(lyrics, stage="LYRICS", context=f"风格：{self.style}\n场景：{approved_desc}")
                self.current_lyrics = lyrics
            else:
                return
        else:
            with open(f"tmp_song_lyrics_{self.lyrics_index:02d}.md", 'r', encoding='utf-8') as f:
                lyrics = f.read()
                self.current_lyrics = lyrics

        print(f"\n--- {self.C_CYAN}歌词预览 (v{self.lyrics_index:02d}){self.C_RESET} ---\n{lyrics}\n{'-'*20}")
        suggestion = self.handle_common_input("\n建议 (ok 批准进入风格, vX 回退, /c 讨论):")
        if suggestion == "/new":
            self.clear_tmp_files()
            self.state = "INIT"
            return

        back_match = re.search(r"back to v(\d+)", suggestion.lower()) or re.search(r"^v(\d+)$", suggestion.lower())
        if back_match:
            v = int(back_match.group(1))
            back_file = f"tmp_song_lyrics_{v:02d}.md"
            if os.path.exists(back_file):
                self.lyrics_index = v
                print(f"已回退 v{v:02d}")
                return

        intent, clean_input = self.ollama.check_intent(suggestion, self.style, "歌词确认")
        if intent == "APPROVE":
            title_p = f"为歌词取个简洁标题（10字内，仅标题）：\n{lyrics}"
            self.song_title = self.ollama.call(title_p, stream=False, spinner=Spinner("正在命名")).strip().replace('"', '')
            self.safe_title = re.sub(r'[\\/*?:"<>|\r\n\t]', "", self.song_title)[:40] or f"song_{self.lyrics_index}"
            self.save_init()
            self.state = "STYLE_DISCUSSION"
            self.s_version = 0
            return
        elif intent == "CHAT":
            self.ollama.call(f"讨论：'{clean_input}'\n内容：\n{lyrics}", system_prompt="你是顾问。不输出完整歌词。", spinner=Spinner())
        elif intent == "MODIFY":
            print(f"\n正在修改歌词 (v{self.lyrics_index:02d} -> v{self.lyrics_index+1:02d})...")
            new_lyrics = self.ollama.call(f"建议：'{clean_input}'\n当前：\n{lyrics}", spinner=Spinner())
            if new_lyrics:
                self.lyrics_index += 1
                self.current_lyrics = new_lyrics
                with open(f"tmp_song_lyrics_{self.lyrics_index:02d}.md", 'w', encoding='utf-8') as f:
                    f.write(new_lyrics)

    def _strict_clean_styles(self, res):
        """核心修复：物理剥离所有干扰字符"""
        res = res.replace("**", "")
        res = re.sub(r'\(.*?\)', '', res)
        lines = res.split('\n')
        cleaned = []
        for line in lines:
            s = line.strip()
            if s.startswith("###") or s.startswith("-"):
                cleaned.append(s)
            elif re.match(r'^\d+\.', s):
                cleaned.append("- " + re.sub(r'^\d+\.\s*', '', s))
        return "\n".join(cleaned).strip()

    def handle_style_discussion(self):
        self.show_header("风格策划")
        just_streamed = False
        if self.s_version == 0:
            print(f"\n正在策划风格提示词...")
            given_pool = ""
            if os.path.exists("song_style_prompts.md"):
                with open("song_style_prompts.md", 'r', encoding='utf-8') as f:
                    given_pool = f.read()
            
            system_template = ""
            if os.path.exists("prompts/style_gen_system.md"):
                with open("prompts/style_gen_system.md", 'r', encoding='utf-8') as f:
                    system_template = f.read()
            system_prompt = system_template if system_template else "资深风格策划师。直接输出列表。"

            user_template = ""
            if os.path.exists("prompts/style_gen_user.md"):
                with open("prompts/style_gen_user.md", 'r', encoding='utf-8') as f:
                    user_template = f.read()
            prompt = user_template.format(lyrics=self.current_lyrics, pool=given_pool) if user_template else f"FILL_TEMPLATE:\nINPUT_LYRICS: {self.current_lyrics}\nPOOL: {given_pool}"
            
            res = self.ollama.call(prompt, system_prompt=system_prompt, spinner=Spinner("正在策划风格"))
            if res:
                self.style_suggestions = self._strict_clean_styles(res)
                self.s_version = 1
                with open(f"tmp_song_styles_v{self.s_version:02d}.txt", 'w', encoding='utf-8') as f:
                    f.write(self.style_suggestions)
                
                # 自动请批评家优化
                critic_context = f"用户选择的初始风格：{self.style}\n\n歌曲完整歌词：\n{self.current_lyrics}"
                self.style_suggestions = self.auto_improve_with_critic(self.style_suggestions, stage="STYLE", context=critic_context)
                just_streamed = True
            else:
                return

        if not just_streamed:
            print(f"\n--- {self.C_CYAN}风格建议 (sv{self.s_version:02d}){self.C_RESET} ---\n{self.style_suggestions}\n{'-'*20}")
        suggestion = self.handle_common_input("\n建议 (ok 批准保存, svX 回退本阶段, vX 跳回歌词, /c 讨论):")
        if suggestion == "/new":
            self.clear_tmp_files()
            self.state = "INIT"
            return
        
        back_match_v = re.search(r"back to v(\d+)", suggestion.lower()) or re.search(r"^v(\d+)$", suggestion.lower())
        if back_match_v:
            v = int(back_match_v.group(1))
            if v == 0:
                v = 1
            back_file = f"tmp_song_lyrics_{v:02d}.md"
            if os.path.exists(back_file):
                self.lyrics_index = v
                self.state = "SONG_LYRICS"
                with open(back_file, 'r', encoding='utf-8') as f:
                    self.current_lyrics = f.read()
                print(f"已跳回歌词 v{v:02d}")
                return
        
        back_match_sv = re.search(r"back to sv(\d+)", suggestion.lower()) or re.search(r"^sv(\d+)$", suggestion.lower())
        if back_match_sv:
            v = int(back_match_sv.group(1))
            back_file = f"tmp_song_styles_v{v:02d}.txt"
            if os.path.exists(back_file):
                self.s_version = v
                with open(back_file, 'r', encoding='utf-8') as f:
                    self.style_suggestions = f.read()
                return

        intent, clean_input = self.ollama.check_intent(suggestion, self.song_title, "风格策划")
        if intent == "APPROVE":
            save_path = os.path.join("lyrics", f"{self.safe_title}.txt")
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(f"{self.song_title}\n\n{self.current_lyrics}\n\n=== Suggested Styles ===\n\n{self.style_suggestions}\n\n=== Metadata ===\nModel: {self.ollama.model}\nTime: {now}\n")
            print(f"\n{self.C_GREEN}已保存到: {save_path}{self.C_RESET}")
            self.clear_tmp_files()
            self.state = "ENDING"
            return
        elif intent == "CHAT":
            self.ollama.call(f"咨询：'{clean_input}'\n内容：\n{self.style_suggestions}", system_prompt="制作人身份。只对话，不输出列表。", spinner=Spinner())
        elif intent == "MODIFY":
            print(f"\n正在修改风格 (sv{self.s_version:02d} -> sv{self.s_version+1:02d})...")
            res = self.ollama.call(f"建议：'{clean_input}'\n当前：\n{self.style_suggestions}", spinner=Spinner())
            if res:
                self.style_suggestions = self._strict_clean_styles(res)
                self.s_version += 1
                with open(f"tmp_song_styles_v{self.s_version:02d}.txt", 'w', encoding='utf-8') as f:
                    f.write(self.style_suggestions)

    def handle_ending(self):
        choice = self.handle_common_input("\n是否创作新歌曲? (y/n):", multiline=False)
        if choice.lower() in ['y', 'yes', '']:
            self.state = "INIT"
        else:
            print("再见！")
            sys.exit(0)

    def clear_tmp_files(self):
        for f in glob.glob("tmp_*"):
            try:
                os.remove(f)
            except:
                pass
        self.description_index = 0
        self.lyrics_index = 0
        self.s_version = 0
        self.song_title = ""

if __name__ == "__main__":
    agent = LyricAgent()
    agent.run()
