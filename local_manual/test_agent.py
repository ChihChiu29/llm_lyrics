import sys
from lyric_agent import load_text, chat_with_ollama

def test_loading():
    print("Testing file loading...")
    instruction = load_text("song_lyrics_instruction.md")
    styles_text = load_text("song_style_prompts.md")
    
    if not instruction:
        print("FAIL: instruction empty")
        return False
    if not styles_text:
        print("FAIL: styles_text empty")
        return False
    
    styles = [s.strip() for s in styles_text.split("\n\n") if s.strip()]
    print(f"Loaded {len(styles)} styles.")
    if len(styles) == 0:
        print("FAIL: No styles parsed")
        return False
    return True

def test_api():
    print("Testing Ollama API connection...")
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say 'Test OK'"}
    ]
    response = chat_with_ollama(messages)
    print(f"Ollama response: {response}")
    if "Test OK" in response or "Error" not in response:
        return True
    return False

if __name__ == "__main__":
    loading_ok = test_loading()
    api_ok = test_api()
    
    if loading_ok and api_ok:
        print("\nSUCCESS: Logic and API checks passed.")
        sys.exit(0)
    else:
        print("\nFAIL: One or more checks failed.")
        sys.exit(1)
