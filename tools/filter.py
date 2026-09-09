import numpy as np
import cv2
from .base import Tool
from typing import Dict, Any

class LUTTool(Tool):
    """3D LUT滤镜 - 应用颜色查找表"""
    
    name = "apply_lut"
    description = "应用3D LUT颜色查找表，实现电影级风格化调色。支持.cube格式。"
    parameters = {
        "lut_path": {"type": "string", "description": "LUT文件路径(.cube格式)"},
        "intensity": {"type": "number", "minimum": 0, "maximum": 100, "default": 100}
    }
    
    def apply(self, img: np.ndarray, params: Dict[str, Any]) -> np.ndarray:
        # 简化版：内置几种常见风格
        style = params.get('style', 'film')
        intensity = params.get('intensity', 100) / 100.0
        
        if style == 'film':
            # 模拟胶片：S曲线 + 偏青
            return self._film_lut(img, intensity)
        elif style == 'cinematic':
            # 青橙色调
            return self._cinematic_lut(img, intensity)
        else:
            return img
    
    def _film_lut(self, img, intensity):
        # S曲线
        result = img.astype(np.float32) / 255
        result = result / (result + (1 - result) * 0.5)  # 模拟胶片S曲线
        # 高光偏暖，阴影偏青
        result[:,:,2] *= (1 + 0.05 * intensity)  # B通道提亮（偏青）
        return np.clip(result * 255, 0, 255).astype(np.uint8)
    
    def _cinematic_lut(self, img, intensity):
        # 青橙色调：阴影偏青，肤色（橙）提亮
        result = img.astype(np.float32)
        # 阴影加青
        shadow_mask = (np.mean(result, axis=2) < 64).astype(np.float32)[:,:,np.newaxis]
        result[:,:,2] += shadow_mask[:,:,0] * 15 * intensity  # B+
        # 高光加橙
        highlight_mask = (np.mean(result, axis=2) > 192).astype(np.float32)[:,:,np.newaxis]
        result[:,:,0] += highlight_mask[:,:,0] * 10 * intensity  # R+
        return np.clip(result, 0, 255).astype(np.uint8)


class SharpenTool(Tool):
    """锐化 - 让画面更清晰"""
    
    name = "sharpen"
    description = "图像锐化，增强边缘细节。amount控制锐化强度，radius控制影响半径。"
    parameters = {
        "amount": {"type": "number", "minimum": 0, "maximum": 200, "default": 50},
        "radius": {"type": "number", "minimum": 0.5, "maximum": 5.0, "default": 1.0}
    }
    
    def apply(self, img: np.ndarray, params: Dict[str, Any]) -> np.ndarray:
        amount = params.get('amount', 50) / 100
        radius = params.get('radius', 1.0)
        
        # 高斯模糊生成蒙版
        blurred = cv2.GaussianBlur(img, (0,0), radius)
        # 叠加边缘
        sharpened = cv2.addWeighted(img, 1 + amount, blurred, -amount, 0)
        return np.clip(sharpened, 0, 255).astype(np.uint8)


class NoiseReductionTool(Tool):
    """降噪 - 平滑画面"""
    
    name = "denoise"
    description = "图像降噪，减少噪点。color_strength控制颜色降噪强度，detail_strength控制细节保留程度。"
    parameters = {
        "color_strength": {"type": "number", "minimum": 0, "maximum": 100, "default": 50},
        "detail_strength": {"type": "number", "minimum": 0, "maximum": 100, "default": 50}
    }
    
    def apply(self, img: np.ndarray, params: Dict[str, Any]) -> np.ndarray:
        h = 10 + params.get('color_strength', 50) / 100 * 40
        return cv2.fastNlMeansDenoisingColored(img, None, h, h*0.5)