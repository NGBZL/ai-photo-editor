import numpy as np
from .base import Tool
from typing import Dict, Any, List

class ToneCurveTool(Tool):
    """RGB曲线 - 所有通道统一曲线"""
    
    name = "tone_curve"
    description = "RGB曲线调色，通过控制点定义映射曲线。每个点(x,y)，x是输入亮度0-255，y是输出亮度0-255。曲线用于整体亮度对比度控制。"
    parameters = {
        "points": {"type": "array", "items": {
            "type": "object",
            "properties": {"x": {"type": "number", "minimum": 0, "maximum": 255},
                          "y": {"type": "number", "minimum": 0, "maximum": 255}}
        }}
    }
    
    def apply(self, img: np.ndarray, params: Dict[str, Any]) -> np.ndarray:
        points = params.get('points', [{"x":0,"y":0}, {"x":255,"y":255}])
        return self._apply_curve(img, points)
    
    def _apply_curve(self, img: np.ndarray, points: List[Dict]) -> np.ndarray:
        # 生成查表
        xs = [p['x'] for p in points]
        ys = [p['y'] for p in points]
        
        # 插值生成完整256点曲线
        import scipy.interpolate as si
        if len(points) > 2:
            f = si.interp1d(xs, ys, kind='cubic', fill_value='extrapolate')
            curve = np.clip(f(np.arange(256)), 0, 255).astype(np.uint8)
        else:
            curve = np.linspace(ys[0], ys[1], 256).astype(np.uint8)
        
        return cv2.LUT(img, curve)


class RGBCurveTool(Tool):
    """分通道曲线 - 独立控制R/G/B"""
    
    name = "rgb_curve"
    description = "分别调整R、G、B三个通道的曲线，实现精细色彩风格化。每个通道的曲线用控制点定义。"
    parameters = {
        "red_points": {"type": "array", "items": {
            "type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}
        }},
        "green_points": {"type": "array", "items": {
            "type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}
        }},
        "blue_points": {"type": "array", "items": {
            "type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}
        }}
    }
    
    def apply(self, img: np.ndarray, params: Dict[str, Any]) -> np.ndarray:
        result = img.copy()
        for idx, key in enumerate(['red_points', 'green_points', 'blue_points']):
            if params.get(key):
                points = params[key]
                xs = [p['x'] for p in points]
                ys = [p['y'] for p in points]
                if len(points) > 2:
                    import scipy.interpolate as si
                    f = si.interp1d(xs, ys, kind='cubic', fill_value='extrapolate')
                    curve = np.clip(f(np.arange(256)), 0, 255).astype(np.uint8)
                else:
                    curve = np.linspace(ys[0], ys[1], 256).astype(np.uint8)
                result[:,:,idx] = cv2.LUT(result[:,:,idx], curve)
        return result