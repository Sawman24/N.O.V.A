import asyncio
import concurrent.futures
from routers.ws_bridge import bridge_manager


def _run_coro_sync(coro):
    """Execute an async coroutine synchronously, whether called inside an existing loop or not."""
    try:
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(lambda: asyncio.run(coro))
            return future.result()
    except RuntimeError:
        return asyncio.run(coro)


def execute_client_command(command: str) -> str:
    """Executes a shell command locally on the user's personal Mac or Windows PC (via the Desktop App).
    Use this tool when you need to run terminal commands, open apps, or check status on the user's local machine."""
    return _run_coro_sync(bridge_manager.send_rpc("default_pc", "execute_command", {"command": command}))


def read_client_file(filepath: str) -> str:
    """Reads the contents of a file on the user's personal Mac or Windows PC (via the Desktop App)."""
    return _run_coro_sync(bridge_manager.send_rpc("default_pc", "read_file", {"filepath": filepath}))


def write_client_file(filepath: str, content: str) -> str:
    """Writes content to a file on the user's personal Mac or Windows PC (via the Desktop App)."""
    return _run_coro_sync(bridge_manager.send_rpc("default_pc", "write_file", {"filepath": filepath, "content": content}))


def list_client_directory(path: str = ".") -> str:
    """Lists files and folders inside a directory on the user's personal Mac or Windows PC (via the Desktop App)."""
    return _run_coro_sync(bridge_manager.send_rpc("default_pc", "list_directory", {"path": path}))
