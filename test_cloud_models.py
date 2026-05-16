import os
import json
import requests

def debug_cloud():
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(_env_path):
        with open(_env_path, "r") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    os.environ[k.strip()] = v.strip()

    key = os.getenv("OLLAMA_API_KEY")
    url = "https://ollama.com/api/chat"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    # List of general-purpose models to test
    models_to_try = [
        "qwen3.5:cloud",
        "qwen3-next:cloud",
        "gpt-oss:120b-cloud",
        "gemma4:cloud",
        "deepseek-v4-pro:cloud"
    ]

    print(f"Testing Non-Coding Cloud Models...")
    
    for model in models_to_try:
        print(f"\n>> Trying model: {model}")
        payload = {"model": model, "messages": [{"role": "user", "content": "hi"}], "stream": False}
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                print(f"SUCCESS! Accessible.")
            else:
                print(f"Failed ({resp.status_code}): {resp.json().get('error')}")
        except Exception as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    debug_cloud()
