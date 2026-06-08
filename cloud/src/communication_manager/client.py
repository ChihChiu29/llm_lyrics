import argparse
import requests
import json
import time

class CommunicationClient:
    def __init__(self, base_url="http://localhost:9223"):
        self.base_url = base_url
        
    def add_interaction(self, input_string, client="deepseek"):
        response = requests.post(
            f"{self.base_url}/api/interaction",
            json={"input_string": input_string, "client": client}
        )
        response.raise_for_status()
        return response.json()
        
    def peek_next_interaction(self):
        response = requests.get(f"{self.base_url}/api/interaction/next")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
        
    def update_next_interaction(self, status=None, output_string=None):
        payload = {}
        if status is not None:
            payload['status'] = status
        if output_string is not None:
            payload['output_string'] = output_string
            
        response = requests.put(
            f"{self.base_url}/api/interaction/next",
            json=payload
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
        
    def list_interactions(self):
        response = requests.get(f"{self.base_url}/api/interactions")
        response.raise_for_status()
        return response.json()
        
    def clear_interactions(self):
        response = requests.delete(f"{self.base_url}/api/interactions")
        response.raise_for_status()
        return response.json()

def main():
    parser = argparse.ArgumentParser(description="Communication Manager CLI Client")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Add command
    parser_add = subparsers.add_parser("add", help="Add a new interaction")
    parser_add.add_argument("input_string", help="Input text for the interaction")
    parser_add.add_argument("--client", default="deepseek", help="Target client (deepseek, chatgpt, claude, qwen)")
    
    # Peek command
    parser_peek = subparsers.add_parser("peek", help="Peek the next interaction")
    
    # Update command
    parser_update = subparsers.add_parser("update", help="Update the next interaction")
    parser_update.add_argument("--status", choices=["PENDING", "RUNNING", "COMPLETED", "FAILED", "CONSUMED"], help="New status")
    parser_update.add_argument("--output", help="Output string")
    
    # List command
    parser_list = subparsers.add_parser("list", help="List all interactions")
    
    # Clear command
    parser_clear = subparsers.add_parser("clear", help="Clear all interactions")
    
    
    args = parser.parse_args()
    client = CommunicationClient()
    
    try:
        if args.command == "add":
            res = client.add_interaction(args.input_string, client=args.client)
            print(json.dumps(res, indent=2))
            
        elif args.command == "peek":
            res = client.peek_next_interaction()
            print(json.dumps(res, indent=2))
            
        elif args.command == "update":
            res = client.update_next_interaction(status=args.status, output_string=args.output)
            print(json.dumps(res, indent=2))
            
        elif args.command == "list":
            res = client.list_interactions()
            print(json.dumps(res, indent=2))
            
        elif args.command == "clear":
            res = client.clear_interactions()
            print(json.dumps(res, indent=2))
            
                
        else:
            parser.print_help()
            
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to server: {e}")

if __name__ == "__main__":
    main()
