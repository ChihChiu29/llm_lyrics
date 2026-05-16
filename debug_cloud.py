import os
import json
import requests

def debug_cloud():
    key = os.getenv("OLLAMA_API_KEY")
    if not key:
        print("Error: No OLLAMA_API_KEY found in environment or .env")
        return

    url = "https://ollama.com/api/chat"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

    # Try a few different model names that are known to be in the cloud preview
    models_to_try = [
        "deepseek-v3:cloud",
        "deepseek-r1:cloud",
        "deepseek-v3.1:671b-cloud",
        "qwen3-coder:480b-cloud"
    ]

    print(f"Testing Ollama Cloud API with key: {key[:5]}...{key[-5:]}")
    
    for model in models_to_try:
        print(f"\n>> Trying model: {model}")
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False
        }
        
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            print(f"Status Code: {resp.status_code}")
            if resp.status_code == 200:
                print(f"SUCCESS! Response: {resp.json().get('message', {}).get('content')}")
                print(f"Conclusion: Use '{model}' instead of your current model name.")
                return
            else:
                print(f"Response: {resp.text}")
        except Exception as e:
            print(f"Request failed: {e}")

    print("\nConclusion: All known cloud models returned errors. Your account might not have 'Cloud Preview' access yet, or the key is invalid.")

if __name__ == "__main__":
    # Load .env manually as in agent_utils
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(_env_path):
        with open(_env_path, "r") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    os.environ[k.strip()] = v.strip()
    
    debug_cloud()
