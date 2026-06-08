import os
import sys
import json
import time
import requests
from datetime import datetime

# Add parent directory to path to import CommunicationClient
try:
    from communication_manager.client import CommunicationClient
except ImportError:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from communication_manager.client import CommunicationClient

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    ENDC = '\033[0m'

class OllamaClient:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url

    def list_models(self):
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            return [m['name'] for m in response.json().get('models', [])]
        except Exception as e:
            print(f"Error connecting to Ollama: {e}")
            return []

    def generate(self, model, prompt):
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False}
            )
            response.raise_for_status()
            return response.json().get('response', "")
        except Exception as e:
            print(f"Error calling Ollama generate: {e}")
            return ""

class LyricMaker:
    DEFAULT_CLIENT = "deepseek"
    DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data"))
    OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../output"))

    def __init__(self):
        self.comm_client = CommunicationClient(base_url="http://localhost:9223")
        self.ollama_client = OllamaClient()
        self.prompts = {}
        self.log_file = None
        self.selected_model = None

    def load_prompts(self):
        prompt_files = {
            "灵感": "灵感_prompt.md",
            "选风格": "选风格_prompt.md",
            "填写大师": "填写大师_prompt.md",
            "音乐总监": "音乐总监_prompt.md",
            "制作人": "制作人_prompt.md"
        }
        for key, filename in prompt_files.items():
            path = os.path.join(self.DATA_DIR, filename)
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    self.prompts[key] = f.read()
            else:
                print(f"Warning: Prompt file {path} not found.")

    def init_log(self):
        if not os.path.exists(self.OUTPUT_DIR):
            os.makedirs(self.OUTPUT_DIR)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        log_path = os.path.join(self.OUTPUT_DIR, f"{timestamp}_log.txt")
        self.log_file = open(log_path, 'a', encoding='utf-8')
        self.log(f"--- Lyric Maker Session Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

    def log(self, message, color=None):
        clean_message = message
        if color:
            print(f"{color}{message}{Colors.ENDC}")
        else:
            print(message)
            
        if self.log_file:
            # Strip ANSI colors for file logging
            import re
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            clean_log = ansi_escape.sub('', message)
            self.log_file.write(f"[{datetime.now().strftime('%H:%M:%S')}] {clean_log}\n")
            self.log_file.flush()

    def wait_for_interaction(self, interaction_id, timeout=300):
        start_time = time.time()
        self.log(f"Waiting for interaction {interaction_id} (timeout: {timeout}s)...", Colors.YELLOW)
        last_status = None
        while time.time() - start_time < timeout:
            res = self.comm_client.peek_next_interaction()
            if res and res['id'] == interaction_id:
                status = res['status']
                if status != last_status:
                    self.log(f"  > Status: {status}", Colors.CYAN)
                    last_status = status
                
                if status == 'COMPLETED':
                    output = res['output_string']
                    self.log(f"Success! Received response ({len(output)} chars):", Colors.GREEN)
                    print(f"{Colors.BLUE}{'='*60}{Colors.ENDC}")
                    print(output)
                    print(f"{Colors.BLUE}{'='*60}{Colors.ENDC}")
                    
                    # Clear the task by setting status to CONSUMED
                    self.log("Marking interaction as CONSUMED...", Colors.YELLOW)
                    self.comm_client.update_next_interaction(status="CONSUMED")
                    return output
                elif status == 'FAILED':
                    # User said other status means not ready or stale. 
                    # If FAILED, we might just want to wait for timeout or retry?
                    # But for now, let's just log it and NOT consume, keeping it for debug.
                    if last_status != 'FAILED_LOGGED':
                        self.log(f"Warning: Interaction {interaction_id} reported FAILED.", Colors.RED)
                        last_status = 'FAILED_LOGGED'
            else:
                if res and last_status != f"OTHER_{res['id']}":
                    self.log(f"  (Interaction {res['id']} is at the top, waiting for ours...)", Colors.YELLOW)
                    last_status = f"OTHER_{res['id']}"
            
            time.sleep(5) 
        self.log(f"Timed out waiting for interaction {interaction_id}", Colors.RED)
        return None

    def extract_score(self, text):
        # Step 6: Use Ollama to extract score (1-10)
        prompt = f"Please extract the score (1-10) from the following evaluation text. Output only the number (e.g. 8.5). If no score found, output 0.\n\nText:\n{text}"
        score_str = self.ollama_client.generate(self.selected_model, prompt).strip()
        try:
            # Try to find a float in the response
            import re
            match = re.search(r"(\d+(\.\d+)?)", score_str)
            if match:
                return float(match.group(1))
            return 0.0
        except:
            return 0.0

    def get_multiline_input(self, prompt_text):
        print(f"{Colors.BOLD}{Colors.CYAN}{prompt_text}{Colors.ENDC} (Press Enter on an empty line to finish):")
        lines = []
        while True:
            line = sys.stdin.readline()
            if not line or line.strip() == "":
                break
            lines.append(line.rstrip("\r\n"))
        return "\n".join(lines)

    def run(self):
        self.init_log()
        self.load_prompts()
        
        # Step 1: Clear the queue to start fresh
        self.log("Clearing communication manager queue...", Colors.YELLOW)
        try:
            self.comm_client.clear_interactions()
            self.log("Queue cleared.", Colors.GREEN)
        except Exception as e:
            self.log(f"Warning: Failed to clear queue: {e}", Colors.RED)

        print(f"\n{Colors.HEADER}{'='*60}")
        print(f"      🎵  AI LYRIC MAKER ORCHESTRATOR  🎵")
        print(f"{'='*60}{Colors.ENDC}\n")

        # Step 2: Choose Ollama model
        models = self.ollama_client.list_models()
        if not models:
            self.log("No Ollama models found. Please make sure Ollama is running.", Colors.RED)
            return

        print(f"{Colors.BOLD}Available Ollama models for scoring:{Colors.ENDC}")
        for i, m in enumerate(models):
            print(f"  {i+1}. {m}")
        
        while True:
            try:
                choice_input = input("\nChoose a model for scoring (number): ").strip()
                if not choice_input: continue
                choice = int(choice_input)
                if 1 <= choice <= len(models):
                    self.selected_model = models[choice-1]
                    self.log(f"Selected model: {self.selected_model}")
                    break
            except ValueError:
                pass
        
        while True:
            # Step 3: Style or Lyrics choice
            print(f"\n{Colors.BOLD}{Colors.CYAN}--- MAIN MENU ---{Colors.ENDC}")
            print("1. Start with a Style (Generate Inspiration)")
            print("2. Start with Lyrics (Generate Styles)")
            
            choice_type = input("\nSelect entry mode (1 or 2): ").strip()
            
            initial_response = ""
            if choice_type == "1":
                # Step 4a: Style
                style = self.get_multiline_input("\nEnter song style")
                print(f"\n{Colors.CYAN}{'-'*30} PHASE 1: GENERATING INSPIRATION {'-'*30}{Colors.ENDC}")
                kickoff_input = f"{self.prompts.get('灵感', '')}\n\nUser Input Style: {style}"
                self.log(f"Sending '灵感' request...", Colors.YELLOW)
                res = self.comm_client.add_interaction(kickoff_input, client=self.DEFAULT_CLIENT)
                initial_response = self.wait_for_interaction(res['id'])
            elif choice_type == "2":
                # Step 4b: Lyrics
                lyrics = self.get_multiline_input("\nEnter lyrics")
                print(f"\n{Colors.CYAN}{'-'*30} PHASE 1: ANALYZING STYLE {'-'*30}{Colors.ENDC}")
                kickoff_input = f"{self.prompts.get('选风格', '')}\n\nUser Input Lyrics:\n{lyrics}"
                self.log(f"Sending '选风格' request...", Colors.YELLOW)
                res = self.comm_client.add_interaction(kickoff_input, client=self.DEFAULT_CLIENT)
                initial_response = self.wait_for_interaction(res['id'])
            else:
                continue

            if not initial_response: continue

            # Step 5: User input (choice)
            print(f"\n{Colors.CYAN}{'-'*30} STEP 5: YOUR CHOICE {'-'*30}{Colors.ENDC}")
            user_choice = self.get_multiline_input("Enter your choice or refinement based on the response above")
            self.log(f"Sending your choice to manager...", Colors.YELLOW)
            res = self.comm_client.add_interaction(user_choice, client=self.DEFAULT_CLIENT)
            # We wait for it to be processed so it's in the chat history
            self.wait_for_interaction(res['id'])
            
            # Step 6: 填写大师
            print(f"\n{Colors.CYAN}{'-'*30} PHASE 2: WRITING LYRICS {'-'*30}{Colors.ENDC}")
            self.log(f"Sending '填写大师' request (Prompt Only)...", Colors.YELLOW)
            tianxie_input = self.prompts.get('填写大师', '')
            res = self.comm_client.add_interaction(tianxie_input, client=self.DEFAULT_CLIENT)
            tianxie_res = self.wait_for_interaction(res['id'])
            if not tianxie_res: continue

            current_lyric = tianxie_res # This is used for logging/evaluation, but not sent in next prompt
            iteration = 0
            while True:
                # Step 7: 音乐总监 (Evaluation)
                print(f"\n{Colors.CYAN}{'-'*30} PHASE 3: EVALUATION (Iteration {iteration+1}) {'-'*30}{Colors.ENDC}")
                self.log(f"Sending '音乐总监' request (Prompt Only)...", Colors.YELLOW)
                zongjian_input = self.prompts.get('音乐总监', '')
                res = self.comm_client.add_interaction(zongjian_input, client=self.DEFAULT_CLIENT)
                zongjian_res = self.wait_for_interaction(res['id'])
                if not zongjian_res: break

                # Step 8: Extract score
                self.log(f"Extracting score using {self.selected_model}...", Colors.YELLOW)
                score = self.extract_score(zongjian_res)
                
                if score >= 9.2:
                    self.log(f"🎯 SUCCESS! Final Score: {score} / 10", Colors.GREEN)
                    break
                else:
                    self.log(f"Current Score: {score} / 10 (Needs improvement)", Colors.RED)

                iteration += 1
                if iteration >= 5:
                    cont = input(f"\n{Colors.BOLD}{Colors.YELLOW}Reached 5 iterations. Continue refining? (y/n): {Colors.ENDC}")
                    if cont.lower() != 'y':
                        break
                    iteration = 0

                # Step 9: 制作人
                print(f"\n{Colors.CYAN}{'-'*30} PHASE 4: REFINING LYRICS {'-'*30}{Colors.ENDC}")
                self.log(f"Sending '制作人' request (Prompt Only)...", Colors.YELLOW)
                zhizuo_input = self.prompts.get('制作人', '')
                res = self.comm_client.add_interaction(zhizuo_input, client=self.DEFAULT_CLIENT)
                zhizuo_res = self.wait_for_interaction(res['id'])
                if not zhizuo_res: break
                
                # Update current_lyric for the next iteration's evaluation extraction (if needed)
                # Note: The design says Step 7 evaluates, but the producer might output the new lyrics.
                # If Step 7 evaluated the PREVIOUS lyrics, then the loop might be tricky.
                # However, following the "as is" rule, we just send the prompt.
                current_lyric = zhizuo_res

            # Step 99: Continue?
            cont_all = input(f"\n{Colors.BOLD}{Colors.GREEN}Session complete. Start another song? (y/n): {Colors.ENDC}")
            if cont_all.lower() != 'y':
                break

        self.log("Exiting Lyric Maker.")
        if self.log_file:
            self.log_file.close()

if __name__ == "__main__":
    maker = LyricMaker()
    maker.run()
