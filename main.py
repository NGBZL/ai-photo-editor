from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import uvicorn
import os
import uuid
import json
from typing import List, Optional
from PIL import Image

from models import EditRequest, ToolCall, EditResponse
from raw_processor import RAWProcessor
from tools.registry import ToolRegistry
from ai_agent import DeepSeekPhotoAgent
from tasks import auto_edit_task
from celery.result import AsyncResult

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

# 支持的扩展名
RAW_EXTS = ['.arw', '.cr2', '.cr3', '.nef', '.dng', '.raf']
IMG_EXTS = ['.jpg', '.jpeg', '.png']
ALL_EXTS = RAW_EXTS + IMG_EXTS


def find_upload_file(file_id: str):
    """根据 file_id 找原图，优先原图扩展名，排除 _preview"""
    candidates = []
    for f in os.listdir(UPLOAD_DIR):
        if not f.startswith(file_id):
            continue
        if '_preview' in f:
            continue
        ext = os.path.splitext(f)[1].lower()
        if ext in ALL_EXTS:
            candidates.append(f)
    
    if not candidates:
        return None
    
    for f in candidates:
        ext = os.path.splitext(f)[1].lower()
        if ext in RAW_EXTS:
            return os.path.join(UPLOAD_DIR, f)
    
    return os.path.join(UPLOAD_DIR, candidates[0])


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
    raw_path = find_upload_file(file_id)
    
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
    """提交修图任务，立即返回 task_id"""
    raw_path = request.get("raw_path")
    feedback = request.get("feedback")
    
    full_path = find_upload_file(raw_path)
    
    if not full_path:
        raise HTTPException(404, "文件不存在")
    
    # 提交任务到队列
    task = auto_edit_task.delay(full_path, feedback)
    
    return {
        'success': True,
        'task_id': task.id,
        'status': 'pending',
        'message': '任务已提交'
    }


@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """查询任务状态"""
    task = AsyncResult(task_id)
    
    if task.state == 'PENDING':
        return {'status': 'pending', 'message': '等待中'}
    elif task.state == 'STARTED':
        return {'status': 'started', 'message': '开始处理'}
    elif task.state == 'PROGRESS':
        return {'status': 'progress', 'meta': task.info}
    elif task.state == 'SUCCESS':
        result = task.result
        return {
            'status': 'success',
            'result': result,
            'output_path': result.get('output_path'),
        }
    elif task.state == 'FAILURE':
        return {'status': 'failed', 'error': str(task.info)}
    else:
        return {'status': task.state}


@app.get("/task/{task_id}/stream")
async def stream_task_status(task_id: str):
    """SSE 流式返回任务状态（前端用 EventSource 订阅，替代轮询）"""

    async def event_generator():
        last_key = None
        while True:
            task = AsyncResult(task_id)
            state = task.state

            # PROGRESS / STARTED 阶段 meta 里带 message
            meta = task.info if state in ('PROGRESS', 'STARTED') else None

            # 变化判定的 key = 状态 + meta。
            # 注意：tasks.py 里三次 update_state 的 state 都是 'PROGRESS'，
            # 只有 meta.message 在变（analyzing -> editing -> done）。
            # 若只比较 state，中间两条永远推不出去，前端会一直停在第一条消息上。
            key = (state, json.dumps(meta, sort_keys=True, ensure_ascii=False, default=str))

            if key != last_key:
                event_data = {
                    'state': state,
                    'meta': meta,
                    'result': task.result if state == 'SUCCESS' else None,
                    'error': str(task.info) if state == 'FAILURE' else None,
                }
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                last_key = key

            # 终态退出
            if state in ('SUCCESS', 'FAILURE'):
                break

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)