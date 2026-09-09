from typing import Dict, List, Type
from .base import Tool
import numpy as np
from .color import HSLTool, ColorBalanceTool, SelectiveColorTool
from .curves import ToneCurveTool, RGBCurveTool
from .levels import LevelsTool, ExposureTool
from .filter import LUTTool, SharpenTool, NoiseReductionTool

class ToolRegistry:
    """所有可用工具的注册中心"""
    
    _tools: Dict[str, Tool] = {}
    
    @classmethod
    def register(cls, tool: Tool):
        cls._tools[tool.name] = tool
    
    @classmethod
    def get(cls, name: str) -> Tool:
        return cls._tools.get(name)
    
    @classmethod
    def get_all_definitions(cls) -> List[Dict]:
        """生成所有工具的OpenAI Function Calling格式"""
        return [tool.to_tool_definition() for tool in cls._tools.values()]
    
    @classmethod
    def execute_tool(cls, name: str, img: np.ndarray, params: Dict) -> np.ndarray:
        """执行工具链中的一个步骤"""
        tool = cls.get(name)
        if not tool:
            raise ValueError(f"未知工具: {name}")
        return tool.apply(img, params)

# 注册所有工具
ToolRegistry.register(HSLTool())
ToolRegistry.register(ColorBalanceTool())
ToolRegistry.register(SelectiveColorTool())
ToolRegistry.register(ToneCurveTool())
ToolRegistry.register(RGBCurveTool())
ToolRegistry.register(LevelsTool())
ToolRegistry.register(ExposureTool())
ToolRegistry.register(LUTTool())
ToolRegistry.register(SharpenTool())
ToolRegistry.register(NoiseReductionTool())