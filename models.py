from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from enum import Enum

class Point(BaseModel):
    x: float = Field(ge=0, le=255)
    y: float = Field(ge=0, le=255)

class ColorBalance(BaseModel):
    cyan_red: float = Field(default=0, ge=-100, le=100)
    magenta_green: float = Field(default=0, ge=-100, le=100)
    yellow_blue: float = Field(default=0, ge=-100, le=100)

class HSLAdjust(BaseModel):
    hue: float = Field(default=0, ge=-180, le=180)
    saturation: float = Field(default=0, ge=-100, le=100)
    lightness: float = Field(default=0, ge=-100, le=100)

class LevelsAdjust(BaseModel):
    black: float = Field(default=0, ge=0, le=255)
    gamma: float = Field(default=1.0, ge=0.1, le=10.0)
    white: float = Field(default=255, ge=0, le=255)

class ToneCurve(BaseModel):
    rgb: List[Point]  # 统一RGB曲线
    red: Optional[List[Point]] = None
    green: Optional[List[Point]] = None
    blue: Optional[List[Point]] = None

class CropBox(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)

class ToolCall(BaseModel):
    tool: str
    params: Dict[str, Any]

class EditRequest(BaseModel):
    raw_path: str
    tools: List[ToolCall]  # 按顺序执行的工具链
    output_format: Literal["jpg", "tiff", "png"] = "jpg"
    quality: int = Field(default=95, ge=1, le=100)
    output_path: Optional[str] = None

class EditResponse(BaseModel):
    success: bool
    output_path: str
    message: str
    before_size: Optional[int] = None
    after_size: Optional[int] = None