import numpy as np
import cv2
from .base import Tool
from typing import Dict, Any

class LevelsTool(Tool):
    """色阶 - 黑白场 + Gamma"""
    
    name = "adjust_levels"
    description = "调整色阶：设定黑场(black)、白场(white)和Gamma值。黑场以下变黑，白场以上变白，Gamma调整中间调亮度。"
    parameters = {
        "black": {"type": "number", "minimum": 0, "maximum": 255, "default": 0},
        "gamma": {"type": "number", "minimum": 0.1, "maximum": 10.0, "default": 1.0},
        "white": {"type": "number", "minimum": 0, "maximum": 255, "default": 255}
    }
    
    def apply(self, img: np.ndarray, params: Dict[str, Any]) -> np.ndarray:
        black = params.get('black', 0)
        white = params.get('white', 255)
        gamma = params.get('gamma', 1.0)
        
        # 归一化到0-1
        img_norm = img.astype(np.float32) / 255.0
        # 黑白场裁剪
        img_norm = np.clip((img_norm - black/255) / (white/255 - black/255), 0, 1)
        # Gamma校正
        img_norm = np.power(img_norm, 1.0/gamma)
        return (img_norm * 255).astype(np.uint8)


class ExposureTool(Tool):
    """曝光/对比度/高光/阴影"""
    
    name = "adjust_exposure"
    description = "综合曝光调整：曝光补偿(exposure)、对比度(contrast)、高光(highlights)、阴影(shadows)、白色(whites)、黑色(blacks)。"
    parameters = {
        "exposure": {"type": "number", "minimum": -5.0, "maximum": 5.0, "default": 0},
        "contrast": {"type": "number", "minimum": -100, "maximum": 100, "default": 0},
        "highlights": {"type": "number", "minimum": -100, "maximum": 100, "default": 0},
        "shadows": {"type": "number", "minimum": -100, "maximum": 100, "default": 0},
        "whites": {"type": "number", "minimum": -100, "maximum": 100, "default": 0},
        "blacks": {"type": "number", "minimum": -100, "maximum": 100, "default": 0}
    }
    
    def apply(self, img: np.ndarray, params: Dict[str, Any]) -> np.ndarray:
        result = img.astype(np.float32)
        
        # 曝光 (类似亮度对数调整)
        exp = params.get('exposure', 0)
        result = result * (2 ** exp)
        
        # 对比度
        contrast = params.get('contrast', 0)
        if contrast != 0:
            factor = 1 + contrast / 100
            mean = np.mean(result)
            result = mean + (result - mean) * factor
        
        # 高光/阴影 (简化版：使用阈值分离)
        highlights = params.get('highlights', 0)
        shadows = params.get('shadows', 0)
        
        if highlights != 0:
            # 高于128为高光区域
            h_mask = (result > 128).astype(np.float32)
            h_mask = cv2.GaussianBlur(h_mask, (15,15), 0)
            result = result * (1 - h_mask * highlights / 100)
        
        if shadows != 0:
            s_mask = (result < 128).astype(np.float32)
            s_mask = cv2.GaussianBlur(s_mask, (15,15), 0)
            result = result * (1 + s_mask * shadows / 100)
        
        # 白场/黑场
        whites = params.get('whites', 0)
        blacks = params.get('blacks', 0)
        if whites > 0:
            result = np.clip(result, 0, 255 - whites)
        elif whites < 0:
            result = np.clip(result + whites, 0, 255)
        
        return np.clip(result, 0, 255).astype(np.uint8)