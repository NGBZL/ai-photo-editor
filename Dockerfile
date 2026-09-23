FROM python:3.11-slim

# Python 运行时设置
#
# PYTHONPATH=/app 是必须的，不要删：
#   项目是"平铺"结构（ai_agent.py / raw_processor.py / tools/ 直接在 /app 下），
#   而 celery 以控制台脚本（/usr/local/bin/celery）启动时，sys.path[0] 是
#   /usr/local/bin，cwd(/app) 并不在 sys.path 里。celery 只在解析 "-A tasks"
#   的那一瞬间用 cwd_in_path() 把 /app 塞进 sys.path，导入完立刻移走。
#   于是 tasks.py 里"惰性导入"的
#       from ai_agent import PhotoEditOrchestrator
#   在任务真正执行时就会 ModuleNotFoundError: No module named 'ai_agent'。
#   （main.py 顶层的 import 发生在 /app 还在 sys.path 时，所以 API 正常，
#     只有 worker 执行任务时才炸。）
#   把 /app 永久写进 PYTHONPATH，api 和 worker 一起受益。
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    TZ=Asia/Shanghai

# 系统依赖：
#   libraw-dev         -> rawpy 解码 RAW（ARW/CR2/NEF/DNG）
#   libglib2.0-0       -> 图片/相机相关运行库
#   libgl1             -> OpenCV 运行库
#   libgomp1           -> numpy/scipy 的 OpenMP 运行时
#   ca-certificates    -> 访问 DeepSeek API 的 HTTPS 证书
RUN apt-get update && apt-get install -y --no-install-recommends \
        libraw-dev \
        libglib2.0-0 \
        libgl1 \
        libgomp1 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖，利用 Docker 层缓存（改代码不会重装依赖）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 运行时目录（同时会被 compose 的 volume 覆盖挂载）
RUN mkdir -p uploads outputs

EXPOSE 8000

# 默认启动 API；worker 服务用 docker-compose 里的 command 覆盖
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
