# 📸 AI 智能修图工具

> 本地化 AI 修图工具：把照片（含 RAW）交给 DeepSeek 视觉模型分析，自动生成一套调色参数，再用本地工具链执行修图。
>
> 原图只存在本机，只有压缩到 800px 的缩略图会发给云端做「看图」分析。

![Python](https://img.shields.io/badge/Python-3.11-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)
![Celery](https://img.shields.io/badge/Celery-5.3+-green.svg)
![Docker](https://img.shields.io/badge/Docker%20Compose-ready-blue.svg)

---

## ✨ 功能特性

- 🤖 **AI 场景识别**：自动判断场景类型（人像/风光/街拍/夜景…）、光线条件、色彩倾向与曝光状态
- 🎛️ **自动修图方案**：AI 输出 3–5 步修图工具链，按顺序在本地执行，不依赖云端算力
- 📷 **RAW 支持**：索尼 `.ARW`、佳能 `.CR2/.CR3`、尼康 `.NEF`、通用 `.DNG`、富士 `.RAF`
- 🖼️ **普通图片支持**：`.JPG / .JPEG / .PNG` 与 RAW 走同一套流程
- ⚡ **异步任务**：修图交给 Celery + Redis 后台执行，接口立即返回 `task_id`
- 📡 **进度推送**：前端用 **SSE** 订阅任务状态（分析中 → 修图中 → 完成），不再轮询
- 💬 **自然语言反馈**：可填「再暖一点 / 增加对比度 / 暗部提亮」，在 AI 方案上追加调整
- 🖥️ **本地运行**：图片默认保存在本机 `uploads/`，仅缩略图用于云端分析
- 🐳 **一键部署**：`docker compose up -d --build` 起全栈（Redis + API + Worker + Flower + Nginx）

---

## 🧰 修图工具链

10 个工具注册在 `tools/registry.py`，按扩展名/参数在本地执行。

| 工具 | 功能 | 主要参数 |
|------|------|----------|
| `adjust_exposure` | 曝光补偿、对比度、高光、阴影、白场、黑场 | `exposure` -5~5，`contrast` / `highlights` / `shadows` / `whites` / `blacks` -100~100 |
| `adjust_levels` | 色阶（黑场 / Gamma / 白场） | `black` 0~255，`gamma` 0.1~10，`white` 0~255 |
| `tone_curve` | RGB 曲线（控制点插值） | `points` `[{x, y}]`，0~255 |
| `rgb_curve` | R/G/B 分通道曲线 | `red_points` / `green_points` / `blue_points` |
| `adjust_hsl` | 色相 / 饱和度 / 明度 | `hue` -180~180，`saturation` / `lightness` -100~100 |
| `color_balance` | 色彩平衡（阴影 / 中间调 / 高光） | `shadows` / `midtones` / `highlights` 各含 `cyan_red`、`magenta_green`、`yellow_blue` |
| `selective_color` | 可选颜色（红/黄/绿/青/蓝/品红/白/中性/黑） | `color` + `cyan` / `magenta` / `yellow` / `black` |
| `apply_lut` | 风格滤镜（内置 `film` 胶片 / `cinematic` 青橙） | `style`、`intensity` 0~100 |
| `sharpen` | 锐化 | `amount` 0~200，`radius` 0.5~5 |
| `denoise` | 降噪 | `color_strength` / `detail_strength` 0~100 |

> 说明：`ai_agent.py` 的系统提示词目前只把其中 6 个（`adjust_exposure`、`adjust_levels`、`tone_curve`、`adjust_hsl`、`sharpen`、`apply_lut`）交给 AI 选择，其余工具通过 `POST /edit` 手动编排调用。

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | 单文件 `ui.html`（原生 HTML + CSS + JS，无构建步骤） |
| 后端 | FastAPI + Uvicorn |
| 异步任务 | Celery 5 + Redis（broker 与 result backend 共用） |
| AI 引擎 | DeepSeek 多模态 API（`openai` SDK，`response_format=json_object`） |
| RAW 解码 | rawpy / LibRaw |
| 图像处理 | Pillow + OpenCV + NumPy |
| 部署 | Docker Compose + Nginx 网关 |

---

## 🚀 快速开始（Docker Compose，推荐）

### 1. 克隆项目

```bash
git clone https://github.com/NGBZL/ai-photo-editor.git
cd ai-photo-editor
```

### 2. 配置 API Key

```bash
cp .env.example .env      # Windows: copy .env.example .env
```

编辑 `.env`，填入在 [DeepSeek 开放平台](https://platform.deepseek.com/) 申请的 Key：

```env
DEEPSEEK_API_KEY=sk-你的Key
REDIS_URL=redis://redis:6379/0
```

> `.env` 已在 `.gitignore` / `.dockerignore` 中，不会被提交进仓库。

### 3. 启动

```bash
docker compose up -d --build
```

### 4. 打开浏览器

访问 <http://localhost/> 即可（Nginx 托管前端并反向代理到 FastAPI）。

### 服务一览

| 服务 | 容器 | 端口 | 说明 |
|------|------|------|------|
| `nginx` | ai-photo-nginx | 80 | 前端托管 + API 反向代理 |
| `api` | ai-photo-api | 8000 | FastAPI 接口 |
| `worker` | ai-photo-worker | — | Celery worker（并发 2） |
| `flower` | ai-photo-flower | 5555 | Celery 任务监控面板 |
| `redis` | ai-photo-redis | — | 消息队列 / 结果后端 |

常用命令：

```bash
docker compose logs -f worker     # 看修图任务日志
docker compose restart worker     # 改完代码重启 worker
docker compose down               # 停止（redis 数据保留在卷里）
```

---

## 💻 本地开发（不用 Docker）

需要本机已有 Redis（`redis-server`，或 `docker run -d -p 6379:6379 redis:alpine`）。
`config.py` 默认连 `redis://localhost:6379/0`，与本机 Redis 一致；没有 `REDIS_URL` 也能跑。

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env      # 然后填入 DEEPSEEK_API_KEY

# 3. 启动 API（注意是 80 端口，原因见下方说明）
python -m uvicorn main:app --host 0.0.0.0 --port 80

# 4. 另开一个终端，启动 Celery worker
celery -A tasks worker --loglevel=info

# 5. 再开一个终端，托管前端
python -m http.server 80
```

然后访问 <http://localhost/ui.html>。

> ⚠️ 关于端口：`ui.html` 里的 `API_BASE` 是硬编码的 `http://localhost`（即 **80 端口**）。所以本地开发时 API 也要监听 80。
> 如果想让 API 留在 8000，请把 `ui.html` 第 124 行改成 `const API_BASE = 'http://localhost:8000';`。
> 用 Docker Compose 时一切都在 80 端口后面，不需要改。

### 运行工具链回归测试

`test_tools.py` 断言每个工具的方向性、值域与「不放大」特性（58 项检查，全部通过）：

```bash
python test_tools.py
```

在容器里跑：

```bash
docker cp test_tools.py ai-photo-api:/app/test_tools.py
docker exec ai-photo-api python test_tools.py
```

---

## 📖 使用说明

1. **上传图片**：拖拽或点击上传 JPG / PNG / RAW（RAW 会优先提取内嵌预览图，很快）
2. **AI 分析**：系统把缩略图发给 DeepSeek，返回场景描述 + 修图步骤列表
3. **一键修图**：任务提交到 Celery，前端通过 SSE 实时看到「AI 分析中 → 执行修图 → 完成」
4. **反馈调优（可选）**：在输入框填「再暖一点」「增加对比度」等，会追加对应的 HSL / 曝光调整
5. **下载结果**：完成后前后对比展示，一键下载

### 支持的文件格式

| 类型 | 扩展名 |
|------|--------|
| 索尼 RAW | `.ARW` |
| 佳能 RAW | `.CR2` `.CR3` |
| 尼康 RAW | `.NEF` |
| 通用 RAW | `.DNG` |
| 富士 RAW | `.RAF` |
| 普通图片 | `.JPG` `.JPEG` `.PNG` |

单文件上限由 Nginx 的 `client_max_body_size 512m` 控制。

---

## 🔌 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/tools` | 列出所有已注册工具的 JSON Schema |
| `POST` | `/upload` | 上传图片，返回 `file_id`、`path` 与预览地址 |
| `GET` | `/preview/{file_id}` | 取上传时生成的缩略图 |
| `GET` | `/ai-analyze?file_id=...` | 同步调用 AI 分析，返回场景描述与 `edit_tools` |
| `POST` | `/ai-edit` | 提交修图任务（body：`raw_path`、可选 `feedback`），返回 `task_id` |
| `GET` | `/task/{task_id}` | 查询任务状态（一次性） |
| `GET` | `/task/{task_id}/stream` | **SSE** 流式推送任务状态 |
| `POST` | `/edit` | 手动按工具链修图（body：`EditRequest`，见 `models.py`） |
| `GET` | `/download/{file_id}` | 下载修图结果 |

交互式文档：启动后访问 <http://localhost:8000/docs>（Docker 模式下即 <http://localhost/docs>）。

---

## 📁 项目结构

```
ai-photo-editor/
├── main.py              # FastAPI 入口：上传/预览/AI/任务/SSE/下载
├── ai_agent.py          # DeepSeek 调用 + 修图编排（含自然语言反馈）
├── raw_processor.py     # 图片加载与保存（RAW 走 rawpy，JPG/PNG 走 PIL）
├── tasks.py             # Celery 任务定义（auto_edit）
├── config.py            # pydantic-settings 配置（读 .env）
├── models.py            # 请求/响应数据模型
├── ui.html              # 前端单页（拖拽上传 + SSE 进度 + 前后对比）
├── test_tools.py        # 工具链回归测试（58 项断言）
├── diag_tools.py        # 单工具统计诊断脚本（排查“参数温和但画面修爆”）
├── tools/               # 修图工具链
│   ├── base.py          # 工具基类 + JSON Schema 导出
│   ├── registry.py      # 工具注册中心
│   ├── color.py         # adjust_hsl / color_balance / selective_color
│   ├── curves.py        # tone_curve / rgb_curve
│   ├── levels.py        # adjust_levels / adjust_exposure
│   └── filter.py        # apply_lut / sharpen / denoise
├── Dockerfile           # python:3.11-slim + libraw/OpenCV 运行库
├── docker-compose.yml   # redis + api + worker + flower + nginx
├── nginx.conf           # 前端托管 + 反向代理（变量式 proxy_pass + SSE 免缓冲）
├── requirements.txt
├── .env.example         # 环境变量模板（真实的 .env 不入库）
├── uploads/             # 上传的原图与预览（本地，Git 忽略）
└── outputs/             # 修图结果（本地，Git 忽略）
```

---

## 🔄 工作流程

```
用户上传图片
    ↓
/upload 保存到 uploads/ → 生成缩略图 → 返回 file_id
    ↓
/ai-analyze 把 800px 缩略图发给 DeepSeek（本机原图不出门）
    ↓
返回 scene_analysis + edit_tools（JSON）
    ↓
/ai-edit 提交 Celery 任务 → 返回 task_id
    ↓
Worker 执行工具链（曝光 → 曲线 → HSL → 锐化 …）
    ↓
/task/{id}/stream 通过 SSE 推送进度与结果
    ↓
/download/{id} 下载成品
```

---

## 🔐 隐私与安全

- 原图与成品只写在本机 `uploads/`、`outputs/`，这两个目录不入库
- 只有**压缩到 800px 的 JPEG 缩略图**会发送给 DeepSeek API 做分析
- `DEEPSEEK_API_KEY` 只放在 `.env` 里；`.env` 已被 `.gitignore` 与 `.dockerignore` 覆盖
- ⚠️ 当前 CORS 配置为 `allow_origins=["*"]`，Flower 也开了 `FLOWER_UNAUTHENTICATED_API`。**仅适合本机/内网使用**，公网部署请先补上鉴权与域名白名单

---

## ❓ 常见问题

**修图任务一直停在 pending**
Redis 没起来或 worker 挂了。`docker compose ps` 看服务状态，`docker compose logs worker` 看日志。

**Worker 报 `No module named 'ai_agent'`**
Dockerfile 里已经把 `/app` 写进 `PYTHONPATH`，请确保用镜像里的启动命令（不要手改 `sys.path` 相关逻辑）。

**Nginx 返回 502 Bad Gateway**
`docker compose up -d --build` 重建 api 容器后 IP 会变。`nginx.conf` 用变量式 `proxy_pass` + Docker 内置 DNS（`valid=10s`）自动重解析，最多 10 秒自愈；若仍 502，`docker compose restart nginx`。

**AI 分析失败**
接口会回退到「默认参数」并继续修图。检查 `.env` 里的 Key 是否有效、容器能否访问外网。

**Flower 面板空白（<http://localhost:5555> 能打开但没数据）**
Flower 2.x 默认锁定 `/api/*`（未配置认证时返回 401），而它的前端面板正是调 `/api/workers` 取数。本项目已在 compose 里设置 `FLOWER_UNAUTHENTICATED_API=true`（仅本机使用）。

---

## 📄 License

仓库暂未附带 License 文件；如需开源分发，请先补充（如 MIT）。
