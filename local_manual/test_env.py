import os
import sys

def test():
    print(f"Current Working Directory: {os.getcwd()}")
    print(f".env exists: {os.path.exists('.env')}")
    
    if os.path.exists(".env"):
        print("--- .env Content (masked) ---")
        with open(".env", "r") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    masked_v = v[:5] + "..." + v[-5:] if len(v) > 10 else "***"
                    print(f"{k}: {masked_v}")
    
    # Manual load logic from agent_utils
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value
    
    key = os.getenv("OLLAMA_API_KEY")
    print(f"\nFinal OLLAMA_API_KEY in os.environ: {key[:5] if key else 'None'}...")

if __name__ == "__main__":
    test()
