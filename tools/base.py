from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import numpy as np
from PIL import Image

class Tool(ABC):
    """所有修图工具的基类"""
    
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}  # JSON Schema格式
    
    @abstractmethod
    def apply(self, img: np.ndarray, params: Dict[str, Any]) -> np.ndarray:
        """应用工具到图像数组"""
        pass
    
    def to_tool_definition(self) -> Dict[str, Any]:
        """生成MCP/OpenAI兼容的工具定义"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": list(self.parameters.keys())
                }
            }
        }