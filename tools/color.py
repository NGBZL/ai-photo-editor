import numpy as np
import cv2
from .base import Tool
from typing import Dict, Any

class HSLTool(Tool):
    """色轮工具 - 调整色相/饱和度/明度"""
    
    name = "adjust_hsl"
    description = "调整图片的色相(Hue)、饱和度(Saturation)、明度(Lightness)。负值降低，正值提高。"
    parameters = {
        "hue": {"type": "number", "minimum": -180, "maximum": 180, "default": 0},
        "saturation": {"type": "number", "minimum": -100, "maximum": 100, "default": 0},
        "lightness": {"type": "number", "minimum": -100, "maximum": 100, "default": 0}
    }
    
    def apply(self, img: np.ndarray, params: Dict[str, Any]) -> np.ndarray:
        # RGB -> HSV
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV).astype(np.float32)
        h, s, v = hsv[:,:,0], hsv[:,:,1], hsv[:,:,2]
        
        # 色相偏移 (0-180)
        h = (h + params.get('hue', 0) / 2) % 180
        
        # 饱和度调整 (0-255)
        s = np.clip(s * (1 + params.get('saturation', 0) / 100), 0, 255)
        
        # 明度调整 (0-255)
        v = np.clip(v * (1 + params.get('lightness', 0) / 100), 0, 255)
        
        hsv = np.stack([h, s, v], axis=-1).astype(np.uint8)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)


class ColorBalanceTool(Tool):
    """色彩平衡 - 阴影/中间调/高光三路色彩平衡"""
    
    name = "color_balance"
    description = "色彩平衡，调整阴影、中间调、高光区域的色彩偏向。值范围-100到100，负值偏冷(青/绿/黄)，正值偏暖(红/品红/蓝)。"
    parameters = {
        "shadows": {"type": "object", "properties": {
            "cyan_red": {"type": "number", "minimum": -100, "maximum": 100, "default": 0},
            "magenta_green": {"type": "number", "minimum": -100, "maximum": 100, "default": 0},
            "yellow_blue": {"type": "number", "minimum": -100, "maximum": 100, "default": 0}
        }},
        "midtones": {"type": "object", "properties": {
            "cyan_red": {"type": "number", "minimum": -100, "maximum": 100, "default": 0},
            "magenta_green": {"type": "number", "minimum": -100, "maximum": 100, "default": 0},
            "yellow_blue": {"type": "number", "minimum": -100, "maximum": 100, "default": 0}
        }},
        "highlights": {"type": "object", "properties": {
            "cyan_red": {"type": "number", "minimum": -100, "maximum": 100, "default": 0},
            "magenta_green": {"type": "number", "minimum": -100, "maximum": 100, "default": 0},
            "yellow_blue": {"type": "number", "minimum": -100, "maximum": 100, "default": 0}
        }}
    }
    
    def apply(self, img: np.ndarray, params: Dict[str, Any]) -> np.ndarray:
        # 简化实现：全局色彩平衡
        result = img.astype(np.float32)
        # 提取主平衡参数（取中间调的）
        mid = params.get('midtones', {})
        result[:,:,0] += mid.get('cyan_red', 0) * 1.2  # R
        result[:,:,1] += mid.get('magenta_green', 0) * 1.2  # G
        result[:,:,2] += mid.get('yellow_blue', 0) * 1.2  # B
        return np.clip(result, 0, 255).astype(np.uint8)


class SelectiveColorTool(Tool):
    """可选颜色 - 针对特定颜色通道调整"""
    
    name = "selective_color"
    description = "针对特定颜色（红/黄/绿/青/蓝/品红/白/中性/黑）分别调整CMYK通道，实现精细分区调色。"
    parameters = {
        "color": {"type": "string", "enum": ["red", "yellow", "green", "cyan", "blue", "magenta", "white", "neutral", "black"]},
        "cyan": {"type": "number", "minimum": -100, "maximum": 100, "default": 0},
        "magenta": {"type": "number", "minimum": -100, "maximum": 100, "default": 0},
        "yellow": {"type": "number", "minimum": -100, "maximum": 100, "default": 0},
        "black": {"type": "number", "minimum": -100, "maximum": 100, "default": 0}
    }
    
    def apply(self, img: np.ndarray, params: Dict[str, Any]) -> np.ndarray:
        # 简化实现：基于色相范围的选择性调整
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        h = hsv[:,:,0].astype(np.float32)  # 0-180
        
        color_ranges = {
            'red': (0, 15, 160, 180),
            'yellow': (20, 35),
            'green': (40, 80),
            'cyan': (85, 100),
            'blue': (105, 125),
            'magenta': (130, 155),
        }
        
        if params['color'] in color_ranges:
            ranges = color_ranges[params['color']]
            if len(ranges) == 2:
                mask = (h >= ranges[0]) & (h <= ranges[1])
            else:
                mask = (h >= ranges[0]) & (h <= ranges[1]) | (h >= ranges[2]) & (h <= ranges[3])
            mask = mask.astype(np.uint8)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.GaussianBlur(mask.astype(np.float32), (15,15), 0)
            mask = mask[:,:,np.newaxis]
            
            result = img.astype(np.float32)
            # CMYK调整映射到RGB
            adj = np.array([
                -params['cyan'] + params['magenta'] + params['yellow'],
                params['cyan'] - params['magenta'] + params['yellow'],
                params['cyan'] + params['magenta'] - params['yellow']
            ]) * 0.5
            
            result += adj * mask
            return np.clip(result, 0, 255).astype(np.uint8)
        return img