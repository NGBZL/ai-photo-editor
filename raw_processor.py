import os
import io
import rawpy
import numpy as np
from PIL import Image, ImageOps

RAW_EXTS = ['.arw', '.cr2', '.cr3', '.nef', '.dng', '.raf']


class RAWProcessor:
    """加载/保存图片：RAW 走 rawpy，JPG/PNG 走 PIL"""
    
    @staticmethod
    def load(image_path: str, 
             use_camera_wb: bool = True,
             output_bps: int = 8,
             half_size: bool = False) -> np.ndarray:
        """按扩展名分流：RAW 用 rawpy 解码，JPG/PNG 用 PIL 读取"""
        ext = os.path.splitext(image_path)[1].lower()
        
        if ext in RAW_EXTS:
            with rawpy.imread(image_path) as raw:
                rgb = raw.postprocess(
                    use_camera_wb=use_camera_wb,
                    output_bps=output_bps,
                    half_size=half_size,
                    user_flip=0,
                    output_color=rawpy.ColorSpace.sRGB,
                    gamma=(2.222, 4.5),  # sRGB gamma
                    no_auto_bright=False
                )
            return rgb
        
        # 普通图片
        img = Image.open(image_path)
        img = ImageOps.exif_transpose(img)   # 手机 JPG 多数带方向信息，不转会躺倒
        if img.mode != 'RGB':
            # 灰度 L / 调色板 P / RGBA / 16位 I;16 统一转 8 位 RGB，
            # 否则后面的 cv2 工具（要求 3 通道 uint8）会直接报错
            img = img.convert('RGB')
        return np.array(img)
    
    @staticmethod
    def save(img: np.ndarray, 
             output_path: str,
             format: str = "jpg",
             quality: int = 95):
        """保存为各种格式"""
        pil = Image.fromarray(img)
        if format == "jpg":
            pil.save(output_path, "JPEG", quality=quality, optimize=True)
        elif format == "tiff":
            pil.save(output_path, "TIFF", compression=None)
        elif format == "png":
            pil.save(output_path, "PNG", optimize=True)
    
    @staticmethod
    def get_embedded_preview(image_path: str) -> np.ndarray:
        """RAW 取内嵌 JPG 预览图（极快）；JPG/PNG 直接读像素"""
        ext = os.path.splitext(image_path)[1].lower()
        
        if ext in RAW_EXTS:
            with rawpy.imread(image_path) as raw:
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    img = Image.open(io.BytesIO(thumb.data))
                    return np.array(img)
            return None
        
        img = Image.open(image_path)
        # 与 load() 保持一致：否则预览图和修图成品方向会不一样
        img = ImageOps.exif_transpose(img)
        if img.mode != 'RGB':
            # 特别是带透明通道的 PNG：RGBA 数组存成 .jpg 会直接报错，
            # 那样 /upload 的预览图就生成不出来
            img = img.convert('RGB')
        return np.array(img)
