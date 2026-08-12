import subprocess
import json
import os

def execute_command(command: str) -> str:
    """Execute a shell command on the host machine and return the output."""
    try:
        # Load config to check for human-in-the-loop
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
        except:
            config = {"require_human_confirmation": False}
            
        if config.get("require_human_confirmation", False):
            if os.getenv("HEADLESS_MODE") == "true":
                return "Error: Cannot execute command because 'require_human_confirmation' is ON, but the agent is running in Headless API mode without a terminal. Please disable human confirmation in the Web UI to run autonomous commands."
            
            print(f"\n[SECURITY] The agent wants to run: `{command}`")
            choice = input("Allow execution? (y/N): ")
            if choice.lower() != 'y':
                return "Execution aborted by user."
                
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except Exception as e:
        return f"Error executing command: {e}"
