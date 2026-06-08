import os
import re
import sys
import datetime
import json
import math
from agent_utils import Spinner, OllamaClient, handle_rich_input

class MultiModelTagCLI:
    def __init__(self):
        self.ollama = OllamaClient()
        self.C_CYAN = "\033[36m"
        self.C_GRAY = "\033[90m"
        self.C_YELLOW = "\033[33m"
        self.C_GREEN = "\033[32m"
        self.C_RESET = "\033[0m"
        
        # Load prompt templates
        self.style_prompt = self._load_prompt("prompts/style_system.md", "你是一位资深风格策划师。为歌词策划 5 个详尽的 SUNO Style Prompts。")
        self.system_scoring_prompt = self._load_prompt("prompts/scoring_system.md", "You are a music style evaluator. Score the proposed SUNO AI style prompts from 1 to 10 matching the song's context.")

    def _load_prompt(self, path, default):
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except:
                return default
        return default

    def select_models(self):
        models = self.ollama.get_models()
        if not models:
            print(f"{self.C_YELLOW}无法连接 Ollama。{self.C_RESET}")
            sys.exit(1)
        
        print(f"\n{self.C_GRAY}可用模型:{self.C_RESET}")
        for i, m in enumerate(models):
            print(f"{i+1}. {m}")
        
        selected_models = []
        print(f"\n{self.C_YELLOW}请输入要选择的模型编号（一次输入一个，直接回车/空输入结束选择）:{self.C_RESET}")
        while True:
            current_selection_str = ", ".join(selected_models) if selected_models else "无"
            choice = handle_rich_input(f"选择模型 #{len(selected_models)+1} (当前已选: {current_selection_str}): ", multiline=False)
            if choice == "/quit":
                print("程序已退出。")
                sys.exit(0)
            if not choice:
                if selected_models:
                    break
                else:
                    print(f"{self.C_YELLOW}请至少选择一个模型。{self.C_RESET}")
                    continue
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(models):
                    model_name = models[idx]
                    if model_name in selected_models:
                        print(f"{self.C_YELLOW}模型 {model_name} 已在选择列表中。{self.C_RESET}")
                    else:
                        selected_models.append(model_name)
                        print(f"已添加模型: {self.C_GREEN}{model_name}{self.C_RESET}")
                else:
                    print(f"{self.C_YELLOW}编号超出范围，请重新输入。{self.C_RESET}")
            except ValueError:
                print(f"{self.C_YELLOW}无效输入，请输入数字编号。{self.C_RESET}")
        return selected_models

    def save_config(self, selected_models):
        if not os.path.exists("configs"):
            os.makedirs("configs")
        try:
            with open(os.path.join("configs", "models.conf"), 'w', encoding='utf-8') as f:
                for m in selected_models:
                    f.write(m + "\n")
        except Exception as e:
            print(f"{self.C_YELLOW}警告: 保存模型配置失败: {e}{self.C_RESET}")

    def load_config(self):
        path = os.path.join("configs", "models.conf")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    models = [line.strip() for line in f if line.strip()]
                    return models
            except:
                pass
        return None

    def save_session(self, song_title, lyrics_original, selected_models, generated_styles, style_records, completed=False):
        if not os.path.exists("tmp"):
            os.makedirs("tmp")
        state = {
            "song_title": song_title,
            "lyrics_original": lyrics_original,
            "selected_models": selected_models,
            "generated_styles": generated_styles,
            "style_records": style_records,
            "completed": completed
        }
        try:
            with open(os.path.join("tmp", "last_session.json"), 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"{self.C_YELLOW}警告: 保存临时状态失败: {e}{self.C_RESET}")

    def load_session(self):
        path = os.path.join("tmp", "last_session.json")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    if not state.get("completed", False):
                        return state
            except:
                pass
        return None

    def clear_session(self):
        path = os.path.join("tmp", "last_session.json")
        if os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass

    def parse_styles(self, text):
        styles = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith(('-', '*')):
                style = line.lstrip('-* ').strip()
                if style:
                    styles.append(style)
        if not styles:
            for line in text.split('\n'):
                line = line.strip()
                match = re.match(r'^\d+[\.\s]+(.*)', line)
                if match:
                    styles.append(match.group(1).strip())
        if not styles:
            styles = [l.strip() for l in text.split('\n') if l.strip()]
        return styles[:5]

    def parse_scores(self, response_text, num_styles):
        try:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                if "scores" in data and isinstance(data["scores"], list):
                    scores = [int(s) for s in data["scores"]]
                    if len(scores) == num_styles:
                        return scores
        except Exception:
            pass
        
        scores = []
        lines = response_text.split('\n')
        for line in lines:
            match = re.search(r'(?:^|\s)(\d+)(?:\s|$|\/10)', line)
            if match:
                val = int(match.group(1))
                if 1 <= val <= 10:
                    scores.append(val)
                    if len(scores) == num_styles:
                        return scores
                        
        all_nums = [int(x) for x in re.findall(r'\b(?:10|[1-9])\b', response_text)]
        if len(all_nums) >= num_styles:
            return all_nums[:num_styles]
            
        while len(scores) < num_styles:
            scores.append(5)
        return scores[:num_styles]

    def run(self):
        print(f"{self.C_CYAN}=== SUNO 多模型歌词风格评估命令行版 ==={self.C_RESET}")
        
        if not os.path.exists("output"):
            os.makedirs("output")
            
        session = self.load_session()
        resumed = False
        selected_models = []
        
        if session:
            print(f"\n{self.C_YELLOW}发现未完成的前次任务：{self.C_RESET}")
            print(f"歌名: {self.C_GREEN}{session['song_title']}{self.C_RESET}")
            print(f"所选模型: {self.C_GREEN}{', '.join(session['selected_models'])}{self.C_RESET}")
            
            choice = handle_rich_input("是否恢复前次工作？(y/n): ", multiline=False)
            if choice.lower().strip() in ['y', 'yes', '是的', '好']:
                resumed = True
                song_title = session['song_title']
                lyrics_original = session['lyrics_original']
                selected_models = session['selected_models']
                generated_styles = session['generated_styles']
                style_records = session['style_records']
                print(f"{self.C_GREEN}已恢复前次会话。{self.C_RESET}")
            else:
                self.clear_session()
                
        if not resumed:
            saved_models = self.load_config()
            if saved_models:
                print(f"\n{self.C_GRAY}已加载上次的模型选择: {', '.join(saved_models)}{self.C_RESET}")
                choice = handle_rich_input("是否继续使用这些模型？(y/n): ", multiline=False)
                if choice.lower().strip() in ['y', 'yes', '是的', '好']:
                    selected_models = saved_models
                else:
                    selected_models = self.select_models()
                    self.save_config(selected_models)
            else:
                selected_models = self.select_models()
                self.save_config(selected_models)
                
            print(f"\n已选择的模型: {self.C_GREEN}{', '.join(selected_models)}{self.C_RESET}")
        
        while True:
            if resumed:
                resumed = False
                safe_title = re.sub(r'[\\/*?:"<>|\r\n\t]', "", song_title).replace(" ", "_")[:40]
            else:
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
                generated_styles = []
                style_records = []
                self.save_session(song_title, lyrics_original, selected_models, generated_styles, style_records)
            
            # Step 2: Generate styles for each chosen model
            models_done = set(gen_model for _, gen_model in generated_styles)
            
            for model_name in selected_models:
                if model_name in models_done:
                    print(f"\n{self.C_GREEN}模型 {model_name} 已有生成的风格提示词，跳过生成。{self.C_RESET}")
                    continue
                    
                print(f"\n{self.C_CYAN}正在使用模型 {model_name} 生成 5 个风格提示词...{self.C_RESET}")
                client = OllamaClient(model=model_name)
                prompt_text = f"歌词：\n\n标题：{song_title}\n{lyrics_original}"
                
                style_suggestions = client.call(
                    prompt_text,
                    system_prompt=self.style_prompt,
                    spinner=Spinner(f"正在生成 ({model_name})")
                )
                
                if not style_suggestions:
                    print(f"{self.C_YELLOW}模型 {model_name} 风格策划失败，跳过。{self.C_RESET}")
                    continue
                
                parsed = self.parse_styles(style_suggestions)
                for style in parsed:
                    generated_styles.append((style, model_name))
                
                self.save_session(song_title, lyrics_original, selected_models, generated_styles, style_records)
            
            if not generated_styles:
                print(f"{self.C_YELLOW}未成功生成任何风格提示词，请重试。{self.C_RESET}")
                continue
                
            # Build/sync style_records
            existing_styles = {r["style"]: r for r in style_records}
            style_records = []
            for style, gen_model in generated_styles:
                if style in existing_styles:
                    style_records.append(existing_styles[style])
                else:
                    style_records.append({
                        "style": style,
                        "generator_model": gen_model,
                        "scores": {}
                    })
            
            # Step 3: Batch scoring
            print(f"\n{self.C_CYAN}开始对生成的 {len(generated_styles)} 个风格提示词进行交叉评分...{self.C_RESET}")
            
            batch_size = 5
            for i in range(0, len(style_records), batch_size):
                batch = style_records[i:i+batch_size]
                batch_styles = [item["style"] for item in batch]
                
                for scorer_model in selected_models:
                    if all(scorer_model in item["scores"] for item in batch):
                        continue
                        
                    client = OllamaClient(model=scorer_model)
                    prompt_text = f"Song Title: {song_title}\nLyrics:\n{lyrics_original}\n\nStyles to score:\n"
                    for idx, style in enumerate(batch_styles):
                        prompt_text += f"{idx+1}. {style}\n"
                    prompt_text += f"\nPlease score these {len(batch_styles)} styles from 1-10 matching the song's context. Respond in the JSON format specified in the system prompt."
                    
                    spinner_msg = f"模型 {scorer_model} 正在评估样式 {i+1}-{i+len(batch)}"
                    scores = []
                    for attempt in range(2):
                        response = client.call(
                            prompt_text,
                            system_prompt=self.system_scoring_prompt,
                            spinner=Spinner(spinner_msg),
                            temperature=0.2
                        )
                        if response:
                            scores = self.parse_scores(response, len(batch_styles))
                            break
                    if not scores:
                        scores = [5] * len(batch_styles)
                        
                    for idx, score in enumerate(scores):
                        batch[idx]["scores"][scorer_model] = score
                        
                    self.save_session(song_title, lyrics_original, selected_models, generated_styles, style_records)
            
            # Step 4: Average and rank
            for record in style_records:
                scores_list = list(record["scores"].values())
                if scores_list:
                    mean = sum(scores_list) / len(scores_list)
                    record["average_score"] = mean
                    variance = sum((x - mean) ** 2 for x in scores_list) / len(scores_list)
                    record["std_dev"] = math.sqrt(variance)
                else:
                    record["average_score"] = 0.0
                    record["std_dev"] = 0.0
                    
            style_records.sort(key=lambda x: x["average_score"], reverse=True)
            
            # Step 5: Save result
            today = datetime.datetime.now().strftime("%Y_%m_%d")
            save_path = os.path.join("output", f"{safe_title}_{today}.md")
            
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {song_title}\n\n")
                    f.write("## Lyrics\n")
                    f.write("```\n")
                    f.write(lyrics_original + "\n")
                    f.write("```\n\n")
                    f.write("## Ranked Styles\n\n")
                    for idx, record in enumerate(style_records):
                        f.write(f"### {idx+1}. {record['style']}\n")
                        f.write(f"- **Average Score**: {record['average_score']:.2f} (±{record['std_dev']:.2f})\n")
                        f.write(f"- **Generated by**: {record['generator_model']}\n")
                        f.write("- **Individual Scores**:\n")
                        for scorer, score in record["scores"].items():
                            f.write(f"  - {scorer}: {score}\n")
                        f.write("\n")
                print(f"\n{self.C_GREEN}所有处理完成! 结果已保存至 {save_path}{self.C_RESET}")
                self.clear_session()
            except Exception as e:
                print(f"{self.C_YELLOW}保存结果失败: {e}{self.C_RESET}")

if __name__ == "__main__":
    try:
        cli = MultiModelTagCLI()
        cli.run()
    except KeyboardInterrupt:
        print("\n已退出。")
        sys.exit(0)
