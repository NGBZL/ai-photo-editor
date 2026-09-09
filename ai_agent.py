import os
import json
import base64
import io
from typing import List, Dict, Any, Optional
from openai import OpenAI
from PIL import Image
import numpy as np


class DeepSeekPhotoAgent:
    """
    DeepSeek V4 多模态修图Agent
    自动分析照片内容、场景、光线，生成修图参数
    """
    
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or "https://api.deepseek.com/v1"
        
        if not self.api_key:
            raise ValueError("请设置 DEEPSEEK_API_KEY 环境变量")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def analyze_photo(self, image_path: str) -> Dict[str, Any]:
        """
        分析照片，返回场景描述 + 修图参数
        """
        img_data = self._compress_image(image_path)
        base64_img = base64.b64encode(img_data).decode('utf-8')
        
        system_prompt = self._get_system_prompt()
        user_message = self._get_user_prompt()
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-v4-flash-vision-exp",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_message},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_img}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.3,
                max_tokens=4096,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception as e:
            print(f"DeepSeek API调用失败: {e}")
            # 返回默认参数
            return {
                "scene_analysis": "AI分析失败，使用默认参数",
                "edit_tools": [
                    {"tool": "adjust_exposure", "params": {"exposure": 0.2, "contrast": 10}},
                    {"tool": "adjust_hsl", "params": {"hue": 0, "saturation": 5}}
                ]
            }
    
    def _compress_image(self, image_path: str, max_size: int = 800) -> bytes:
        """压缩图片到DeepSeek要求的尺寸（支持RAW和普通图片）"""
        ext = os.path.splitext(image_path)[1].lower()
        img = None
        
        # 如果是 RAW 文件，用 rawpy 解码
        if ext in ['.arw', '.cr2', '.cr3', '.nef', '.dng', '.raf']:
            try:
                import rawpy
                with rawpy.imread(image_path) as raw:
                    # 先尝试提取内嵌预览图（快）
                    try:
                        thumb = raw.extract_thumb()
                        if thumb.format == rawpy.ThumbFormat.JPEG:
                            img = Image.open(io.BytesIO(thumb.data))
                        else:
                            raise ValueError("无JPEG预览图")
                    except:
                        # 如果没有预览图，解码RAW（慢但可靠）
                        print("无预览图，解码RAW文件...")
                        rgb = raw.postprocess(output_bps=8, half_size=True)
                        img = Image.fromarray(rgb)
            except Exception as e:
                print(f"RAW解码失败: {e}")
                raise ValueError(f"无法处理RAW文件: {e}")
        else:
            # 普通图片直接用 PIL 打开
            try:
                img = Image.open(image_path)
            except Exception as e:
                print(f"打开图片失败: {e}")
                raise ValueError(f"无法打开图片: {e}")
        
        # 转换为RGB
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        # 缩放到最大边不超过 max_size
        w, h = img.size
        if max(w, h) > max_size:
            scale = max_size / max(w, h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # 保存为高质量JPEG
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=92, optimize=True)
        return buffer.getvalue()
    
    def _get_system_prompt(self) -> str:
        return """你是一位专业的图像修图师和色彩科学家。你的任务是分析照片内容，并生成一套完整的修图参数。

## 分析维度
1. 场景类型：人像/风光/街拍/静物/建筑/夜景/其他
2. 光线条件：顺光/逆光/侧光/阴天/黄金时刻/蓝色时刻/室内/人工光
3. 色彩分析：主色调、冷暖倾向、饱和度水平
4. 曝光分析：欠曝/过曝/正常

## 输出格式
你必须输出一个JSON对象，包含：
1. scene_analysis: 场景分析文本（中文）
2. scene_type: 场景类型
3. light_condition: 光线条件
4. color_tone: 色彩倾向
5. edit_tools: 工具调用数组

## 可用工具及参数
1. adjust_exposure: exposure(-5~5), contrast(-100~100), highlights(-100~100), shadows(-100~100)
2. adjust_levels: black(0~255), gamma(0.1~10), white(0~255)
3. tone_curve: points=[{x,y}] 控制点（0-255）
4. adjust_hsl: hue(-180~180), saturation(-100~100), lightness(-100~100)
5. sharpen: amount(0~200)
6. apply_lut: style(film/cinematic), intensity(0~100)

## 修图原则
- 人像：柔化肤色、轻微暖调、提亮眼神
- 风光：增加饱和度、强化冷暖对比、拉高清晰度
- 街拍：增加对比度、强化阴影细节
- 夜景：降噪、提亮阴影、保持暗部氛围
- 始终优先：细节不丢失、色彩不溢出、整体自然

请只输出JSON，不要有其他文字。"""
    
    def _get_user_prompt(self) -> str:
        return """请分析这张照片，生成3-5步修图参数。JSON格式输出。"""


class PhotoEditOrchestrator:
    """
    修图编排器：连接 DeepSeek AI + 修图工具
    """
    
    def __init__(self, api_key: str = None):
        self.agent = DeepSeekPhotoAgent(api_key)
    
    def auto_edit(self, raw_path: str, output_path: str = None) -> Dict[str, Any]:
        from raw_processor import RAWProcessor
        from tools.registry import ToolRegistry
        import time
        import uuid
        
        start_time = time.time()
        
        print("📸 AI分析照片...")
        analysis = self.agent.analyze_photo(raw_path)
        print(f"场景分析: {analysis.get('scene_analysis', '')[:100]}...")
        
        print("📂 加载图片...")
        img = RAWProcessor.load(raw_path, output_bps=8)
        
        tools_calls = analysis.get('edit_tools', [])
        print(f"🔧 执行 {len(tools_calls)} 步修图...")
        
        for i, call in enumerate(tools_calls):
            tool_name = call.get('tool')
            params = call.get('params', {})
            print(f"  步骤 {i+1}: {tool_name}")
            try:
                img = ToolRegistry.execute_tool(tool_name, img, params)
            except Exception as e:
                print(f"  ⚠️ {tool_name} 执行失败: {e}")
                continue
        
        if not output_path:
            output_path = f"outputs/auto_edit_{uuid.uuid4()}.jpg"
        
        RAWProcessor.save(img, output_path, "jpg", quality=95)
        
        elapsed = time.time() - start_time
        print(f"✅ 修图完成! 耗时 {elapsed:.1f}s")
        
        return {
            "analysis": analysis,
            "output_path": output_path,
            "tools_executed": len(tools_calls),
            "elapsed_seconds": elapsed
        }
    
    def edit_with_feedback(self, raw_path: str, feedback: str, output_path: str = None) -> Dict[str, Any]:
        analysis = self.agent.analyze_photo(raw_path)
        tools_calls = analysis.get('edit_tools', [])
        
        if feedback:
            params = {}
            if "暖" in feedback:
                params["hue"] = 15
            elif "冷" in feedback:
                params["hue"] = -15
            if "饱和" in feedback:
                if "增加" in feedback or "高" in feedback:
                    params["saturation"] = 20
                elif "降低" in feedback or "低" in feedback:
                    params["saturation"] = -20
            if "亮" in feedback:
                params["lightness"] = 15
            if "暗" in feedback:
                params["lightness"] = -15
            if "对比" in feedback:
                # 反馈里提到对比度，追加一个曝光调整
                tools_calls.append({"tool": "adjust_exposure", "params": {"contrast": 20}})
            if params:
                tools_calls.append({"tool": "adjust_hsl", "params": params})
        
        return self._execute_tools(raw_path, tools_calls, output_path)
    
    def _execute_tools(self, raw_path: str, tools_calls: List, output_path: str) -> Dict:
        from raw_processor import RAWProcessor
        from tools.registry import ToolRegistry
        import uuid
        
        img = RAWProcessor.load(raw_path, output_bps=8)
        for call in tools_calls:
            try:
                img = ToolRegistry.execute_tool(call['tool'], img, call['params'])
            except Exception as e:
                print(f"执行工具 {call.get('tool')} 失败: {e}")
                continue
        
        if not output_path:
            output_path = f"outputs/feedback_edit_{uuid.uuid4()}.jpg"
        
        RAWProcessor.save(img, output_path, "jpg", quality=95)
        return {"output_path": output_path, "tools_executed": len(tools_calls)}