import inspect
import json
import os
import importlib.util
from typing import Callable, Dict, Any, List, get_origin, get_args


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

    def load_tools(self):
        """Dynamically load all python files in the tools directory."""
        self.tools.clear()
        if not os.path.exists(self.tools_dir):
            return

        for filename in os.listdir(self.tools_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = filename[:-3]
                file_path = os.path.join(self.tools_dir, filename)

                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    try:
                        spec.loader.exec_module(module)
                        for name, obj in inspect.getmembers(module):
                            if inspect.isfunction(obj) and getattr(obj, '__module__', '') == module_name:
                                if not name.startswith("_"):
                                    self.tools[name] = obj
                    except Exception as e:
                        print(f"Error loading {file_path}: {e}")

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
