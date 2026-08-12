import os
import json
from tool_registry import ToolRegistry
from backends import get_backend
from dotenv import load_dotenv

load_dotenv()


class NovaAgent:
    def __init__(self):
        self.backend = get_backend()
        self.registry = ToolRegistry()

        # Load all user profiles from profiles/ directory
        profile_text = ""
        try:
            if os.path.exists("profiles"):
                for filename in sorted(os.listdir("profiles")):
                    if filename.endswith(".txt"):
                        filepath = os.path.join("profiles", filename)
                        with open(filepath, "r") as f:
                            profile_text += f"\n\n--- PROFILE: {filename} ---\n{f.read()}"
        except Exception as e:
            print(f"[Nova] Error loading profiles: {e}")

        self.messages = [
            {
                "role": "system",
                "content": (
                    "You are Nova, a local agentic AI assistant. "
                    "Be concise, direct, and helpful. "
                    "You have access to tools for shell commands, web search, email, and building new tools. "
                    "Use tools proactively when they would help answer the user's request."
                    + profile_text
                )
            }
        ]

    def chat(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": user_input})

        while True:
            self.registry.load_tools()
            tools = self.registry.get_tool_schemas()

            msg = self.backend.chat(self.messages, tools)
            self.messages.append(msg)

            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    func_name = tool_call.function.name
                    try:
                        args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    print(f"[Nova] → {func_name}({args})")

                    if func_name in self.registry.tools:
                        try:
                            result = self.registry.tools[func_name](**args)
                        except Exception as e:
                            result = f"Error executing tool '{func_name}': {e}"
                    else:
                        result = f"Tool '{func_name}' not found."

                    self.messages.append({
                        "role": "tool",
                        "name": func_name,
                        "content": str(result),
                        "tool_call_id": tool_call.id
                    })
            else:
                return msg.content or ""
