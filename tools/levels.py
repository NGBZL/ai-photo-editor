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
        # 黑白场裁剪（分母加保护：black==white 时会除零，整步会被静默跳过）
        denom = max(white - black, 1) / 255.0
        img_norm = np.clip((img_norm - black/255) / denom, 0, 1)
        # Gamma校正
        img_norm = np.power(img_norm, 1.0/gamma)
        return (img_norm * 255).astype(np.uint8)


def _srgb_to_linear(x: np.ndarray) -> np.ndarray:
    """sRGB 编码值(0~1) -> 线性光(0~1)"""
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(x: np.ndarray) -> np.ndarray:
    """线性光(0~1) -> sRGB 编码值(0~1)"""
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def _exposure_lut(exp: float) -> np.ndarray:
    """
    曝光查表：在【线性光】空间乘 2**exp，再回到 sRGB。

    旧实现是 result * 2**exp 直接乘 sRGB 编码值，这等于把"曝光"当亮度乘进去：
    +0.15EV 会让 240 变成 240*1.1096=266 -> 截断成 255（实测死白从 1.2% 涨到 22.7%）。
    在真实相机/修图软件里 +0.15EV 只是 1/6 档，240 应该只到 251，根本不该溢出。
    """
    lut_x = np.arange(256, dtype=np.float32) / 255.0
    lin = _srgb_to_linear(lut_x) * (2.0 ** exp)
    return np.clip(_linear_to_srgb(lin) * 255.0, 0, 255).astype(np.uint8)


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
        exp = float(params.get('exposure', 0) or 0)
        contrast = float(params.get('contrast', 0) or 0)
        highlights = float(params.get('highlights', 0) or 0)
        shadows = float(params.get('shadows', 0) or 0)
        whites = float(params.get('whites', 0) or 0)
        blacks = float(params.get('blacks', 0) or 0)

        # ---------- 1. 曝光（线性光 + 256 项查表，几乎不占内存） ----------
        if exp:
            img = cv2.LUT(img, _exposure_lut(exp))

        result = img.astype(np.float32)

        # ---------- 2. 对比度：以中灰 128 为轴、端点不动的 S 曲线 ----------
        # 旧实现 mean + (result-mean)*factor 是纯线性拉伸，任何 >229 的像素都会被推过 255
        # 然后截断（实测 contrast=12 单独就多出 14.6% 死白）。
        # 改成 smoothstep 混合：(1-k)*x + k*x²(3-2x)
        #   - 0->0、0.5->0.5、1->1（端点恒等）
        #   - 两端导数为 0，天然带高光/暗部"肩部"，任何 k∈[-1,1] 都保证输出落在 [0,1]
        #     => 对比度不可能制造新的溢出，也不会把顶部几级压成同一个白
        if contrast:
            f = max(-1.0, min(1.0, contrast / 100.0))
            # k 用 sqrt 曲线映射（类似推子手感）：
            #   contrast=12 -> k=0.485（四分之一调 ±12 级，和旧实现 1.12 倍力度相当）
            #   contrast=50 -> k=0.99，contrast>=51 -> 1.0（封顶，保证单调）
            k = float(np.clip((1.0 if f >= 0 else -1.0) * 1.4 * (abs(f) ** 0.5), -0.9, 1.0))
            if k:
                x = np.clip(result, 0.0, 255.0) / 255.0
                s = x * x * (3.0 - 2.0 * x)
                result = ((1.0 - k) * x + k * s) * 255.0

        # ---------- 3. 高光 / 阴影 ----------
        # 旧实现三处错误：
        #   (a) 高光符号反了：写成 1 - mask*highlights/100，于是 highlights=-35（压高光）
        #       实际变成 ×1.35（高光提亮 35%）—— 实测死白 1.2% -> 24.3%，这就是"过曝发白"主因。
        #   (b) 蒙版是 (result>128) 的【二值】蒙版再 15x15 模糊，而且在三个通道上分别比较：
        #       128 附近出现硬边、窗边出现光晕、还会串色。
        #   (c) 直接乘亮度：highlights=-100 会把高光乘成纯黑，参数到极值就崩。
        # 现在按【亮度】算平滑权重，并把调整改成"沿中灰方向压缩/扩张"：
        #     v' = 128 + (v - 128) * (1 + w_h*highlights/100 - w_s*shadows/100)
        #   负 highlights 只把高光往中灰压（永远压不到中灰以下），正 shadows 只把暗部往中灰提，
        #   两者互不越界；同时整体亮度基本保持不变（不会像旧实现那样一片发白）。
        if highlights or shadows:
            lum = result.mean(axis=2)                       # 用调整前的亮度算权重，两步互不干扰
            gain = 1.0
            if highlights:
                w_h = np.clip((lum - 100.0) / 155.0, 0.0, 1.0) ** 2   # 100 以下不碰，最亮处权重 1
                gain = gain + w_h * (highlights / 100.0)
            if shadows:
                w_s = np.clip((100.0 - lum) / 100.0, 0.0, 1.0)        # 最暗处权重 1，100 以上不碰
                gain = gain - w_s * (shadows / 100.0)
            result = 128.0 + (result - 128.0) * gain[..., None]

        # ---------- 4. 白场 / 黑场 ----------
        # 旧实现：whites>0 时 np.clip(result, 0, 255-whites) 是"把高光砍掉"，
        # whites<0 时全图减 |whites|，方向都是反的；blacks 取了参数却完全没用（死代码）。
        # 改成与 adjust_levels 一致的色阶重映射。
        if whites or blacks:
            wp = 255.0 - whites * 1.275     # whites=+100 -> 白场降到 127.5（高光更亮）
            bp = blacks * 1.275             # blacks=+100 -> 黑场升到 127.5（暗部更黑）
            if wp - bp < 1.0:
                wp = bp + 1.0
            result = (result - bp) * (255.0 / (wp - bp))

        # ---------- 5. 统一收口 ----------
        return np.clip(result, 0, 255).astype(np.uint8)
