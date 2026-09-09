import rawpy
import numpy as np
from PIL import Image
import io

class RAWProcessor:
    """处理索尼ARW等RAW文件"""
    
    @staticmethod
    def load(raw_path: str, 
             use_camera_wb: bool = True,
             output_bps: int = 8,
             half_size: bool = False) -> np.ndarray:
        """加载RAW文件并解码为RGB数组"""
        with rawpy.imread(raw_path) as raw:
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
    def get_embedded_preview(raw_path: str) -> np.ndarray:
        """提取RAW内嵌的JPG预览图（极快）"""
        with rawpy.imread(raw_path) as raw:
            thumb = raw.extract_thumb()
            if thumb.format == rawpy.ThumbFormat.JPEG:
                img = Image.open(io.BytesIO(thumb.data))
                return np.array(img)
        return None