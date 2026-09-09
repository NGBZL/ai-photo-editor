from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import uuid
import json
from typing import List, Optional
from PIL import Image

from models import EditRequest, ToolCall, EditResponse
from raw_processor import RAWProcessor
from tools.registry import ToolRegistry
from ai_agent import DeepSeekPhotoAgent, PhotoEditOrchestrator

app = FastAPI(title="AI修图服务", description="MCP风格图片编辑API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.get("/tools")
async def get_tools():
    return {"tools": ToolRegistry.get_all_definitions()}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.arw', '.cr2', '.cr3', '.nef', '.dng', '.raf', '.jpg', '.jpeg', '.png']:
        raise HTTPException(400, "不支持的文件格式")
    
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")
    
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    preview_path = None
    try:
        preview = RAWProcessor.get_embedded_preview(file_path)
        if preview is not None:
            preview_path = os.path.join(UPLOAD_DIR, f"{file_id}_preview.jpg")
            Image.fromarray(preview).save(preview_path)
    except Exception as e:
        print(f"生成预览失败: {e}")
    
    return {
        "file_id": file_id,
        "path": file_path,
        "preview": f"/preview/{file_id}" if preview_path else None
    }


@app.post("/edit")
async def edit_image(request: EditRequest):
    img = RAWProcessor.load(request.raw_path, output_bps=8)
    
    for tool_call in request.tools:
        img = ToolRegistry.execute_tool(
            tool_call.tool,
            img,
            tool_call.params
        )
    
    output_id = str(uuid.uuid4())
    output_path = os.path.join(OUTPUT_DIR, f"{output_id}.{request.output_format}")
    RAWProcessor.save(img, output_path, request.output_format, request.quality)
    
    original_size = os.path.getsize(request.raw_path)
    output_size = os.path.getsize(output_path)
    
    return EditResponse(
        success=True,
        output_path=output_path,
        message=f"编辑完成，共执行{len(request.tools)}步操作",
        before_size=original_size,
        after_size=output_size
    )


@app.get("/download/{file_id}")
async def download(file_id: str):
    for f in os.listdir(OUTPUT_DIR):
        if f.startswith(file_id):
            return FileResponse(os.path.join(OUTPUT_DIR, f))
    raise HTTPException(404, "文件不存在")


@app.get("/preview/{file_id}")
async def preview(file_id: str):
    preview_path = os.path.join(UPLOAD_DIR, f"{file_id}_preview.jpg")
    if os.path.exists(preview_path):
        return FileResponse(preview_path)
    raise HTTPException(404, "预览图不存在")


# ============ AI 端点 ============

@app.get("/ai-analyze")
async def ai_analyze(file_id: str):
    """AI 分析照片"""
    raw_path = None
    for f in os.listdir(UPLOAD_DIR):
        if f.startswith(file_id):
            raw_path = os.path.join(UPLOAD_DIR, f)
            break
    
    if not raw_path:
        raise HTTPException(404, "文件不存在")
    
    agent = DeepSeekPhotoAgent()
    try:
        analysis = agent.analyze_photo(raw_path)
        return analysis
    except Exception as e:
        print(f"AI分析失败: {e}")
        raise HTTPException(500, f"AI分析失败: {str(e)}")


@app.post("/ai-edit")
async def ai_edit(request: dict):
    """AI 自动修图"""
    raw_path = request.get("raw_path")
    feedback = request.get("feedback")
    
    full_path = None
    for f in os.listdir(UPLOAD_DIR):
        if f.startswith(raw_path):
            full_path = os.path.join(UPLOAD_DIR, f)
            break
    
    if not full_path:
        raise HTTPException(404, "文件不存在")
    
    orchestrator = PhotoEditOrchestrator()
    try:
        if feedback:
            result = orchestrator.edit_with_feedback(full_path, feedback)
        else:
            result = orchestrator.auto_edit(full_path)
        
        output_file = result["output_path"]
        file_id = os.path.splitext(os.path.basename(output_file))[0]
        
        return {
            "success": True,
            "output_path": output_file,
            "download_url": f"/download/{file_id}",
            "tools_used": result["tools_executed"],
            "analysis": result.get("analysis", {})
        }
    except Exception as e:
        print(f"修图失败: {e}")
        raise HTTPException(500, f"修图失败: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)