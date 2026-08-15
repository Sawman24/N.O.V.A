import os
import json
from tool_registry import ToolRegistry
from backends import get_backend
from dotenv import load_dotenv
from nova_logging import get_logger
import chat_store

load_dotenv()

logger = get_logger("agent")


class NovaAgent:
    def __init__(self):
        self.backend = get_backend()
        self.registry = ToolRegistry()
        self.sessions = {}

    def _build_system_prompt(self) -> str:
        """Build the system prompt, injecting loaded tools and all profiles from the profiles/ directory."""
        self.registry.load_tools()
        tool_list = ", ".join(sorted(self.registry.tools.keys())) if self.registry.tools else "none"

        profile_text = ""
        try:
            if os.path.exists("profiles"):
                for filename in sorted(os.listdir("profiles")):
                    if filename.endswith(".txt"):
                        filepath = os.path.join("profiles", filename)
                        with open(filepath, "r") as f:
                            profile_text += f"\n\n--- PROFILE: {filename} ---\n{f.read()}"
        except Exception as e:
            logger.error(f"Error loading profiles: {e}")

        return (
            "You are Nova, a local agentic AI assistant. "
            "Be concise, direct, and helpful. "
            f"You have access to the following tools: {tool_list}.\n\n"
            "WEB & SCRAPING PROTOCOL:\n"
            "- Use search_web to search for topics on DuckDuckGo.\n"
            "- Use fetch_webpage_content to fetch and read the full text content of any website URL or article.\n\n"
            "REMOTE DESKTOP & FILE PROTOCOL:\n"
            "- Use execute_client_command, read_client_file, write_client_file, and list_client_directory to run commands or manage documents on the user's local PC via the Desktop App.\n\n"
            "EMAIL PROTOCOL:\n"
            "1. When monitoring or checking email, examine the sender, subject, and body.\n"
            "2. If an email is routine/trusted, you may reply autonomously using send_email.\n"
            "3. If an email contains sensitive subjects (payments, invoices, contracts, legal, salary, urgent requests) or requires human intervention, call draft_email_reply to save a pending draft and ask the user for confirmation.\n\n"
            "Use tools proactively when appropriate."
            + profile_text
        )

    def get_session(self, session_id: str) -> list:
        """Get or initialize message history for a given session ID."""
        if session_id not in self.sessions:
            # Try loading from persistent store
            stored = chat_store.load_session(session_id)
            if stored:
                self.sessions[session_id] = stored
            else:
                system_msg = {"role": "system", "content": self._build_system_prompt()}
                self.sessions[session_id] = [system_msg]
                chat_store.save_message(session_id, "system", system_msg["content"])
        return self.sessions[session_id]

    def delete_session(self, session_id: str):
        """Delete a session from memory and persistent store."""
        self.sessions.pop(session_id, None)
        chat_store.delete_session(session_id)

    def reload_profiles(self):
        """Reload profiles and update system messages across all active sessions — no restart needed."""
        system_prompt = self._build_system_prompt()
        for session_id, messages in self.sessions.items():
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] = system_prompt
        logger.info("Profiles reloaded.")

    def chat(self, user_input: str, session_id: str = "default") -> str:
        messages = self.get_session(session_id)
        messages.append({"role": "user", "content": user_input})
        chat_store.save_message(session_id, "user", user_input)

        while True:
            self.registry.load_tools()
            tools = self.registry.get_tool_schemas()

            msg = self.backend.chat(messages, tools)
            messages.append(msg)

            if msg.tool_calls:
                # Persist assistant message with tool calls
                tc_data = [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in msg.tool_calls]
                chat_store.save_message(session_id, "assistant", msg.content, tool_calls=tc_data)

                for tool_call in msg.tool_calls:
                    func_name = tool_call.function.name
                    try:
                        args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    logger.info(f"Tool call: {func_name}({args})")

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
                    chat_store.save_message(session_id, "tool", str(result), name=func_name, tool_call_id=tool_call.id)
            else:
                chat_store.save_message(session_id, "assistant", msg.content)
                return msg.content or ""

    def chat_stream(self, user_input: str, session_id: str = "default"):
        """Generator that yields SSE-compatible event dicts for streaming chat."""
        messages = self.get_session(session_id)
        messages.append({"role": "user", "content": user_input})

        while True:
            self.registry.load_tools()
            tools = self.registry.get_tool_schemas()

            # Accumulate the full response for message history
            full_content = ""
            tool_calls_accum = {}  # index -> {id, name, arguments}

            for chunk in self.backend.chat_stream(messages, tools):
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                # Stream text tokens
                if delta.content:
                    full_content += delta.content
                    yield {"type": "token", "content": delta.content}

                # Accumulate tool call deltas
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls_accum:
                            tool_calls_accum[idx] = {
                                "id": tc_delta.id or "",
                                "name": tc_delta.function.name or "" if tc_delta.function else "",
                                "arguments": "",
                            }
                        if tc_delta.id:
                            tool_calls_accum[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_calls_accum[idx]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                tool_calls_accum[idx]["arguments"] += tc_delta.function.arguments

            # If there were tool calls, execute them and loop
            if tool_calls_accum:
                # Build a message object for history
                tool_calls_list = []
                for idx in sorted(tool_calls_accum.keys()):
                    tc = tool_calls_accum[idx]
                    tool_calls_list.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"],
                        },
                    })

                messages.append({
                    "role": "assistant",
                    "content": full_content or None,
                    "tool_calls": tool_calls_list,
                })

                for tc in tool_calls_list:
                    func_name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        args = {}

                    logger.info(f"Tool call (stream): {func_name}({args})")
                    yield {"type": "tool_call", "name": func_name, "args": args}

                    if func_name in self.registry.tools:
                        try:
                            result = self.registry.tools[func_name](**args)
                        except Exception as e:
                            result = f"Error executing tool '{func_name}': {e}"
                    else:
                        result = f"Tool '{func_name}' not found."

                    yield {"type": "tool_result", "name": func_name, "result": str(result)[:500]}

                    messages.append({
                        "role": "tool",
                        "name": func_name,
                        "content": str(result),
                        "tool_call_id": tc["id"],
                    })
                # Loop back to get the model's final response
                continue
            else:
                # No tool calls — done
                messages.append({"role": "assistant", "content": full_content})
                yield {"type": "done"}
                return
