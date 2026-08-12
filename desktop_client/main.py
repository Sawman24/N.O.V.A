import os
import sys
import json
import asyncio
import threading
import subprocess
import webview
import websockets

DEFAULT_SERVER_URL = os.getenv("NOVA_SERVER_URL", "http://localhost:8000")


def _get_ws_url(server_url: str) -> str:
    url = server_url.replace("http://", "ws://").replace("https://", "wss://")
    if not url.endswith("/"):
        url += "/"
    return url + "ws/client/desktop_pc"


class LocalExecutor:
    """Executes local file and system commands on the user's Mac/Windows machine."""

    @staticmethod
    def execute_command(command: str) -> str:
        try:
            res = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=60
            )
            return f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        except subprocess.TimeoutExpired:
            return f"Error: Command '{command}' timed out after 60 seconds."
        except Exception as e:
            return f"Error executing local command: {e}"

    @staticmethod
    def read_file(filepath: str) -> str:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception as e:
            return f"Error reading local file: {e}"

    @staticmethod
    def write_file(filepath: str, content: str) -> str:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote file to {filepath}"
        except Exception as e:
            return f"Error writing local file: {e}"

    @staticmethod
    def list_directory(path: str = ".") -> str:
        try:
            entries = os.listdir(path)
            results = []
            for entry in entries:
                full_path = os.path.join(path, entry)
                is_dir = os.path.isdir(full_path)
                results.append(f"{'[DIR]' if is_dir else '[FILE]'} {entry}")
            return "\n".join(results)
        except Exception as e:
            return f"Error listing local directory '{path}': {e}"


async def start_websocket_daemon(server_url: str):
    ws_url = _get_ws_url(server_url)
    print(f"[Nova Desktop Client] Connecting RPC daemon to {ws_url}...")

    executor = LocalExecutor()

    while True:
        try:
            async with websockets.connect(ws_url) as websocket:
                print(f"[Nova Desktop Client] Connected to Nova server.")
                while True:
                    message_text = await websocket.recv()
                    try:
                        msg = json.loads(message_text)
                        rpc_id = msg.get("rpc_id")
                        action = msg.get("action")
                        params = msg.get("params", {})

                        print(f"[Nova Desktop Client] RPC Call received: {action}({params})")

                        result = None
                        error = None

                        if action == "execute_command":
                            result = executor.execute_command(params.get("command", ""))
                        elif action == "read_file":
                            result = executor.read_file(params.get("filepath", ""))
                        elif action == "write_file":
                            result = executor.write_file(
                                params.get("filepath", ""), params.get("content", "")
                            )
                        elif action == "list_directory":
                            result = executor.list_directory(params.get("path", "."))
                        else:
                            error = f"Unknown action '{action}'"

                        response_payload = {
                            "rpc_id": rpc_id,
                            "result": result,
                            "error": error,
                        }
                        await websocket.send(json.dumps(response_payload))

                    except Exception as e:
                        print(f"[Nova Desktop Client] Error handling RPC message: {e}")

        except Exception as e:
            print(f"[Nova Desktop Client] Connection lost ({e}). Retrying in 5 seconds...")
            await asyncio.sleep(5)


def run_daemon_thread(server_url: str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_websocket_daemon(server_url))


def main():
    server_url = DEFAULT_SERVER_URL
    if len(sys.argv) > 1:
        server_url = sys.argv[1]

    # Start background WebSocket RPC daemon thread
    daemon_thread = threading.Thread(
        target=run_daemon_thread, args=(server_url,), daemon=True
    )
    daemon_thread.start()

    # Launch native Desktop Webview UI window
    print(f"[Nova Desktop App] Launching GUI window connecting to {server_url}...")
    window = webview.create_window(
        title="Nova — Local AI Desktop App",
        url=server_url,
        width=1200,
        height=800,
        resizable=True,
    )
    webview.start()


if __name__ == "__main__":
    main()
