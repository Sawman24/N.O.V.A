import inspect
import json
import os
import importlib.util
from typing import Callable, Dict, Any, List, get_origin, get_args
from nova_logging import get_logger

logger = get_logger("tool_registry")


def _type_to_schema(annotation) -> Dict[str, Any]:
    if annotation == inspect.Parameter.empty:
        return {"type": "string"}

    origin = get_origin(annotation) or annotation
    args = get_args(annotation)

    if origin == int:
        return {"type": "integer"}
    elif origin == float:
        return {"type": "number"}
    elif origin == bool:
        return {"type": "boolean"}
    elif origin in (list, List):
        item_schema = _type_to_schema(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": item_schema}
    elif origin in (dict, Dict):
        return {"type": "object"}
    else:
        return {"type": "string"}


class ToolRegistry:
    def __init__(self, tools_dir="tools"):
        self.tools_dir = tools_dir
        self.tools: Dict[str, Callable] = {}
        self._file_mtimes: Dict[str, float] = {}  # filepath -> last mtime
        self._file_tools: Dict[str, list] = {}  # filepath -> [tool_names]

    def load_tools(self):
        """Dynamically load python files in the tools directory, only re-importing changed files."""
        if not os.path.exists(self.tools_dir):
            return

        current_files = {}
        for filename in os.listdir(self.tools_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                file_path = os.path.join(self.tools_dir, filename)
                current_files[file_path] = os.path.getmtime(file_path)

        # Remove tools from deleted files
        removed = set(self._file_mtimes.keys()) - set(current_files.keys())
        for file_path in removed:
            for tool_name in self._file_tools.get(file_path, []):
                self.tools.pop(tool_name, None)
            self._file_mtimes.pop(file_path, None)
            self._file_tools.pop(file_path, None)

        # Load new or changed files
        for file_path, mtime in current_files.items():
            if file_path in self._file_mtimes and self._file_mtimes[file_path] == mtime:
                continue  # Unchanged — skip

            # Remove old tools from this file before reloading
            for tool_name in self._file_tools.get(file_path, []):
                self.tools.pop(tool_name, None)

            module_name = os.path.basename(file_path)[:-3]
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                loaded_names = []
                try:
                    spec.loader.exec_module(module)
                    for name, obj in inspect.getmembers(module):
                        if inspect.isfunction(obj) and getattr(obj, '__module__', '') == module_name:
                            if not name.startswith("_"):
                                self.tools[name] = obj
                                loaded_names.append(name)
                except Exception as e:
                    logger.error(f"Error loading {file_path}: {e}")

                self._file_mtimes[file_path] = mtime
                self._file_tools[file_path] = loaded_names

    def force_reload(self):
        """Clear all caches and reload everything from scratch."""
        self.tools.clear()
        self._file_mtimes.clear()
        self._file_tools.clear()
        self.load_tools()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Convert loaded tools into OpenAI compatible JSON schemas."""
        schemas = []
        for name, func in self.tools.items():
            doc = inspect.getdoc(func) or f"Execute {name}"

            sig = inspect.signature(func)
            properties = {}
            required = []

            for param_name, param in sig.parameters.items():
                param_schema = _type_to_schema(param.annotation)
                param_schema["description"] = f"Parameter {param_name}"
                properties[param_name] = param_schema

                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": doc,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            })
        return schemas
