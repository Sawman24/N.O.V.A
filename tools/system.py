import subprocess
import re
import json
import os
from nova_logging import get_logger

logger = get_logger("tools.system")

# Patterns that should never be executed by the AI agent
BLOCKED_PATTERNS = [
    r"\brm\s+(-\w*\s+)*-\w*r\w*\s+/",   # rm -rf / variants
    r"\bmkfs\b",                           # format filesystems
    r"\bdd\s+if=",                         # raw disk writes
    r":\(\)\s*\{\s*:\|:\s*&\s*\}\s*;",     # fork bomb
    r"\bchmod\s+(-\w+\s+)*777\s+/",       # chmod 777 /
    r"\bshutdown\b",                       # shutdown
    r"\breboot\b",                         # reboot
    r">\s*/dev/sd",                        # overwrite disk devices
    r"\bcurl\b.*\|\s*(ba)?sh",            # curl pipe to shell
    r"\bwget\b.*\|\s*(ba)?sh",            # wget pipe to shell
    r"\bpython\b.*-c.*import\s+os.*system", # python shell escape
    r"\beval\b.*\$\(",                     # eval with command substitution
    r"\bnc\s+-\w*[el]",                   # netcat listeners (reverse shells)
    r">\s*/etc/passwd",                    # overwrite passwd
    r">\s*/etc/shadow",                    # overwrite shadow
]

MAX_OUTPUT_LENGTH = 65536  # 64KB cap on command output


def _is_blocked(command: str) -> bool:
    """Check if a command matches any blocked pattern."""
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


def execute_command(command: str) -> str:
    """Execute a shell command on the host machine and return the output."""
    try:
        # Security: check command against blocklist
        if _is_blocked(command):
            logger.warning(f"Blocked dangerous command: {command}")
            return (
                f"Error: Command blocked by security policy. "
                f"The command '{command}' matches a pattern known to be destructive. "
                f"This is a safety measure to prevent accidental damage."
            )

        # Load config to check for human-in-the-loop
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
        except Exception:
            config = {"require_human_confirmation": False}

        if config.get("require_human_confirmation", False):
            if os.getenv("HEADLESS_MODE") == "true":
                return "Error: Cannot execute command because 'require_human_confirmation' is ON, but the agent is running in Headless API mode without a terminal. Please disable human confirmation in the Web UI to run autonomous commands."

            print(f"\n[SECURITY] The agent wants to run: `{command}`")
            choice = input("Allow execution? (y/N): ")
            if choice.lower() != 'y':
                return "Execution aborted by user."

        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
        stdout = result.stdout[:MAX_OUTPUT_LENGTH] if result.stdout else ""
        stderr = result.stderr[:MAX_OUTPUT_LENGTH] if result.stderr else ""

        if len(result.stdout or "") > MAX_OUTPUT_LENGTH:
            stdout += f"\n\n[...truncated after {MAX_OUTPUT_LENGTH} characters...]"
        if len(result.stderr or "") > MAX_OUTPUT_LENGTH:
            stderr += f"\n\n[...truncated after {MAX_OUTPUT_LENGTH} characters...]"

        return f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    except subprocess.TimeoutExpired:
        return f"Error executing command: Command '{command}' timed out after 60 seconds."
    except Exception as e:
        return f"Error executing command: {e}"
