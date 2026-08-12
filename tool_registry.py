import inspect
import json
import os
import importlib.util
from typing import Callable, Dict, Any, List

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
                param_type = "string"
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation == int: param_type = "integer"
                    elif param.annotation == float: param_type = "number"
                    elif param.annotation == bool: param_type = "boolean"
                
                properties[param_name] = {
                    "type": param_type,
                    "description": f"Parameter {param_name}"
                }
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
