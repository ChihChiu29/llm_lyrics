import requests
import json
import os

OLLAMA_API_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3.5:latest" # Using qwen3.5 based on previous Ollama list

def load_text(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

def chat_with_ollama(messages):
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status()
        result = response.json()
        return result.get("message", {}).get("content", "")
    except Exception as e:
        return f"Error: {str(e)}"

def main():
    instruction = load_text("song_lyrics_instruction.md")
    styles_text = load_text("song_style_prompts.md")
    styles = [s.strip() for s in styles_text.split("\n\n") if s.strip()]
    
    print("=== 中文说唱歌词创作助手 ===")
    print("请选择一个风格:")
    for i, style in enumerate(styles):
        # Show first line or a summary of the style
        summary = style.split("\n")[0][:60].replace("- ", "") + "..."
        print(f"{i+1}. {summary}")
    
    choice = input("\n请输入编号 (或直接按回车选择第一个): ")
    if not choice:
        selected_style = styles[0]
    else:
        try:
            selected_style = styles[int(choice)-1]
        except:
            print("无效选择，默认选择第一个风格。")
            selected_style = styles[0]
            
    print(f"\n已选择风格: {selected_style.split('\\n')[0][:100]}...")
    
    # Initialize messages with system prompt
    system_prompt = f"{instruction}\n\n当前风格参考:\n{selected_style}"
    messages = [{"role": "system", "content": system_prompt}]
    
    while True:
        topic = input("\n请输入你想写的歌词主题或反馈 (输入 'quit' 退出, 'reset' 重置对话): ")
        if topic.lower() == 'quit':
            break
        if topic.lower() == 'reset':
            messages = [{"role": "system", "content": system_prompt}]
            print("对话已重置。")
            continue
            
        messages.append({"role": "user", "content": topic})
        
        print("\n正在生成/回复中，请稍候...")
        response = chat_with_ollama(messages)
        print("\n--- 歌词/助手回复 ---")
        print(response)
        print("\n------------------")
        
        messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()
