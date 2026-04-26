import os
import re
import sys
import json
import glob
import requests

OLLAMA_API_URL = "http://localhost:11434/api"

class LyricAgent:
    def __init__(self):
        self.model = ""
        self.style = ""
        self.state = "INIT"
        self.history = []
        self.description_index = 0
        self.lyrics_index = 0

    def run(self):
        print("=== 中文说唱歌词创作助手 (v2) ===")
        self.resume_workflow()
        
        while True:
            if self.state == "INIT":
                self.handle_init()
            elif self.state == "SONG_DESCRIPTION":
                self.handle_song_description()
            elif self.state == "SONG_LYRICS":
                self.handle_song_lyrics()
            elif self.state == "ENDING":
                self.handle_ending()

    def handle_input(self, prompt_text):
        user_input = input(prompt_text).strip()
        if user_input.lower() == "/quit":
            print("再见！")
            sys.exit(0)
        elif user_input.lower() == "/new":
            self.clear_tmp_files()
            self.state = "INIT"
            return "/new"
        elif user_input.lower() == "/desc":
            if self.state == "SONG_LYRICS":
                if os.path.exists("tmp_song_approved.md"):
                    with open("tmp_song_approved.md", 'r', encoding='utf-8') as f:
                        print("\n--- 当前已批准的描述 (tmp_song_approved.md) ---")
                        print(f.read())
                        print("---------------------------------------")
                self.state = "SONG_DESCRIPTION"
                return "/desc"
            else:
                print("当前不在歌词创作阶段，无法返回描述阶段。")
        return user_input

    def clear_tmp_files(self):
        for f in glob.glob("tmp_*"):
            try:
                os.remove(f)
            except:
                pass

    def get_ollama_models(self):
        try:
            resp = requests.get(f"{OLLAMA_API_URL}/tags")
            resp.raise_for_status()
            models = [m['name'] for m in resp.json().get('models', [])]
            return models
        except Exception as e:
            print(f"获取模型列表失败: {e}")
            return []

    def call_ollama(self, prompt, system_prompt="", stream=True):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": stream
        }
        try:
            resp = requests.post(f"{OLLAMA_API_URL}/chat", json=payload, stream=stream)
            resp.raise_for_status()
            
            if not stream:
                return resp.json().get('message', {}).get('content', '')

            full_content = ""
            for line in resp.iter_lines():
                if line:
                    chunk = json.loads(line)
                    content = chunk.get('message', {}).get('content', '')
                    full_content += content
                    print(content, end='', flush=True)
                    if chunk.get('done'):
                        break
            print() # New line after stream ends
            return full_content
        except Exception as e:
            if stream: print(f"\nError: {e}")
            return f"Error: {e}"

    def check_approval(self, user_input):
        approvals = ['ok', 'go', 'yes', 'y', 'fine', 'good', 'looks good', '好的', '可以', '行', '批准', '没问题', '成了', '就这', '过']
        normalized = user_input.lower().strip(" .!！。")
        if normalized in approvals:
            return True
        
        # Quick LLM check for intent if not in list
        check_prompt = f"判断用户是否对当前内容满意并想要继续到下一步。用户输入: '{user_input}'。如果是肯定（如'go', '可以', '好', '满意'等），仅回答'YES'，否则回答'NO'。"
        result = self.call_ollama(check_prompt, stream=False).strip().upper()
        return "YES" in result

    def resume_workflow(self):
        # Determine state by looking at tmp files
        lyrics_files = sorted(glob.glob("tmp_song_lyrics_*.md"), key=lambda x: int(re.search(r'(\d+)', x).group(1)))
        if lyrics_files:
            self.lyrics_index = int(re.search(r'(\d+)', lyrics_files[-1]).group(1))
            self.state = "SONG_LYRICS"
            self.load_init()
            print(f"已恢复到歌词创作阶段 (版本 {self.lyrics_index})。")
            return

        if os.path.exists("tmp_song_approved.md"):
            self.state = "SONG_LYRICS"
            self.load_init()
            print("已恢复到歌词创作阶段 (已批准描述)。")
            return

        desc_files = sorted(glob.glob("tmp_song_description_*.md"), key=lambda x: int(re.search(r'(\d+)', x).group(1)))
        if desc_files:
            self.description_index = int(re.search(r'(\d+)', desc_files[-1]).group(1))
            self.state = "SONG_DESCRIPTION"
            self.load_init()
            print(f"已恢复到歌曲描述阶段 (版本 {self.description_index})。")
            return

        if os.path.exists("tmp_init.md"):
            self.state = "SONG_DESCRIPTION"
            self.load_init()
            print("已恢复到歌曲描述阶段。")
            return

        self.state = "INIT"

    def load_init(self):
        if os.path.exists("tmp_init.md"):
            with open("tmp_init.md", 'r', encoding='utf-8') as f:
                content = f.read()
                m = re.search(r"Model: (.*)", content)
                if m: self.model = m.group(1).strip()
                s = re.search(r"Style: (.*)", content)
                if s: self.style = s.group(1).strip()

    def handle_init(self):
        models = self.get_ollama_models()
        if not models:
            print("未找到 Ollama 模型。请确保 Ollama 正在运行。")
            sys.exit(1)
        
        print("\n可用模型:")
        for i, m in enumerate(models):
            print(f"{i+1}. {m}")
        
        choice = self.handle_input(f"\n请选择模型编号 (默认 1): ")
        if choice == "/new": return
        try:
            self.model = models[int(choice)-1] if choice else models[0]
        except:
            self.model = models[0]
        
        # Style
        styles = []
        if os.path.exists("song_styles.md"):
            with open("song_styles.md", 'r', encoding='utf-8') as f:
                styles = [line.strip().lstrip("- ").strip() for line in f if line.strip().startswith("-")]
        
        if not styles:
            print("song_styles.md 中未找到风格。")
            sys.exit(1)

        print("\n可用风格:")
        for i, s in enumerate(styles):
            print(f"{i+1}. {s}")
        
        choice = self.handle_input(f"\n请选择风格编号或直接输入自定义风格 (默认 1): ")
        if choice == "/new": return
        
        if not choice:
            self.style = styles[0]
        else:
            try:
                idx = int(choice)
                if 1 <= idx <= len(styles):
                    self.style = styles[idx-1]
                else:
                    self.style = choice
            except ValueError:
                self.style = choice

        with open("tmp_init.md", 'w', encoding='utf-8') as f:
            f.write(f"Model: {self.model}\nStyle: {self.style}\n")
        
        print(f"初始化完成。模型: {self.model}, 风格: {self.style}")
        self.state = "SONG_DESCRIPTION"

    def handle_song_description(self):
        if self.description_index == 0:
            print("\n正在生成歌曲描述/故事场景...")
            prompt = f"请为一首风格为 '{self.style}' 的中文歌曲，创作一个简短的描述、故事背景或捕捉的场景。"
            desc = self.call_ollama(prompt)
            self.description_index = 1
            filename = f"tmp_song_description_{self.description_index:02d}.md"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(desc)
        else:
            filename = f"tmp_song_description_{self.description_index:02d}.md"
            with open(filename, 'r', encoding='utf-8') as f:
                desc = f.read()

        print(f"\n--- 歌曲描述 (版本 {self.description_index:02d}) ---")
        print(desc)
        print("---------------------------------------")
        
        suggestion = self.handle_input("\n请输入修改建议 (或输入 'ok' 批准, 'let's go back to version x' 回退): ")
        if suggestion == "/new": return
        
        if self.check_approval(suggestion):
            with open("tmp_song_approved.md", 'w', encoding='utf-8') as f:
                f.write(desc)
            print("描述已批准。")
            self.state = "SONG_LYRICS"
            self.lyrics_index = 0
            return

        back_match = re.search(r"let's go back to version (\d+)", suggestion.lower())
        if back_match:
            v = int(back_match.group(1))
            back_file = f"tmp_song_description_{v:02d}.md"
            if os.path.exists(back_file):
                self.description_index = v
                print(f"已回退到版本 {v:02d}")
                return
            else:
                print(f"版本 {v:02d} 不存在。")
                return

        print("\n正在修改描述...")
        prompt = f"基于以下建议修改歌曲描述：\n建议：{suggestion}\n\n当前描述：\n{desc}"
        new_desc = self.call_ollama(prompt)
        self.description_index += 1
        new_filename = f"tmp_song_description_{self.description_index:02d}.md"
        with open(new_filename, 'w', encoding='utf-8') as f:
            f.write(new_desc)

    def handle_song_lyrics(self):
        approved_desc = ""
        if os.path.exists("tmp_song_approved.md"):
            with open("tmp_song_approved.md", 'r', encoding='utf-8') as f:
                approved_desc = f.read()
        else:
            print("找不到已批准的描述，返回描述阶段。")
            self.state = "SONG_DESCRIPTION"
            return

        instruction = ""
        if os.path.exists("song_lyrics_instruction.md"):
            with open("song_lyrics_instruction.md", 'r', encoding='utf-8') as f:
                instruction = f.read()

        if self.lyrics_index == 0:
            print("\n正在生成歌词...")
            prompt = f"根据以下描述创作歌词：\n{approved_desc}\n\n风格：{self.style}\n\n额外指令：\n{instruction}"
            lyrics = self.call_ollama(prompt)
            self.lyrics_index = 1
            filename = f"tmp_song_lyrics_{self.lyrics_index:02d}.md"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(lyrics)
        else:
            filename = f"tmp_song_lyrics_{self.lyrics_index:02d}.md"
            with open(filename, 'r', encoding='utf-8') as f:
                lyrics = f.read()

        print(f"\n--- 歌曲歌词 (版本 {self.lyrics_index:02d}) ---")
        print(lyrics)
        print("---------------------------------------")

        suggestion = self.handle_input("\n请输入修改建议 (或输入 'ok' 批准): ")
        if suggestion == "/new": return
        if suggestion == "/desc": return

        if self.check_approval(suggestion):
            print("\n正在生成标题并保存...")
            title_prompt = f"为以下歌词取一个简洁的标题：\n{lyrics}"
            title = self.call_ollama(title_prompt, stream=False).strip().replace("\"", "").replace("'", "")
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
            with open(f"{safe_title}.txt", 'w', encoding='utf-8') as f:
                f.write(f"{title}\n\n{lyrics}")
            print(f"歌词已保存到 {safe_title}.txt")
            self.state = "ENDING"
            return

        print("\n正在修改歌词...")
        prompt = f"基于以下建议修改歌词：\n建议：{suggestion}\n\n当前歌词：\n{lyrics}\n\n风格参考：{self.style}\n额外指令：{instruction}"
        new_lyrics = self.call_ollama(prompt)
        self.lyrics_index += 1
        new_filename = f"tmp_song_lyrics_{self.lyrics_index:02d}.md"
        with open(new_filename, 'w', encoding='utf-8') as f:
            f.write(new_lyrics)

    def handle_ending(self):
        choice = self.handle_input("\n是否创作新歌曲? (yes/no): ")
        if choice == "/new": return
        
        if choice.lower() == 'yes':
            self.clear_tmp_files()
            self.description_index = 0
            self.lyrics_index = 0
            self.state = "INIT"
        elif choice.lower() == 'no':
            self.state = "SONG_LYRICS"
        else:
            print("请输入 'yes' 或 'no'。")

if __name__ == "__main__":
    agent = LyricAgent()
    agent.run()
