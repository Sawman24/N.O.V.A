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
        self.sessions = {}

    def _build_system_prompt(self) -> str:
        """Build the system prompt, injecting all profiles from the profiles/ directory."""
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

        return (
            "You are Nova, a local agentic AI assistant. "
            "Be concise, direct, and helpful. "
            "You have access to tools for web searching, web scraping/reading URLs, local & remote PC shell execution, file & document management, email monitoring & triage, calendar management, and building new tools.\n\n"
            "WEB & SCRAPING PROTOCOL:\n"
            "- Use search_web to search for topics on DuckDuckGo.\n"
            "- Use fetch_webpage_content to fetch and read the full text content of any website URL or article.\n\n"
            "REMOTE DESKTOP & FILE PROTOCOL:\n"
            "- Use execute_client_command, read_client_file, write_client_file, and list_client_directory to run commands or manage documents on the user's local PC via the Desktop App.\n\n"
            "EMAIL PROTOCOL:\n"
            "1. When monitoring or checking email, examine the sender, subject, and body.\n"
            "2. If an email is routine/trusted, you may reply autonomously using send_email.\n"
            "3. If an email contains sensitive subjects (payments, invoices, contracts, legal, salary, urgent requests) or requires human intervention, call draft_email_reply to save a pending draft and ask the user for confirmation.\n\n"
            "CALENDAR PROTOCOL:\n"
            "When an email or message requests or confirms a meeting, date, or appointment, call create_calendar_event to schedule it on Google Calendar.\n\n"
            "Use tools proactively when appropriate."
            + profile_text
        )

    def get_session(self, session_id: str) -> list:
        """Get or initialize message history for a given session ID."""
        if session_id not in self.sessions:
            self.sessions[session_id] = [{"role": "system", "content": self._build_system_prompt()}]
        return self.sessions[session_id]

    def reload_profiles(self):
        """Reload profiles and update system messages across all active sessions — no restart needed."""
        system_prompt = self._build_system_prompt()
        for session_id, messages in self.sessions.items():
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] = system_prompt
        print("[Nova] Profiles reloaded.")

    def chat(self, user_input: str, session_id: str = "default") -> str:
        messages = self.get_session(session_id)
        messages.append({"role": "user", "content": user_input})

        while True:
            self.registry.load_tools()
            tools = self.registry.get_tool_schemas()

            msg = self.backend.chat(messages, tools)
            messages.append(msg)

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

                    messages.append({
                        "role": "tool",
                        "name": func_name,
                        "content": str(result),
                        "tool_call_id": tool_call.id
                    })
            else:
                return msg.content or ""
