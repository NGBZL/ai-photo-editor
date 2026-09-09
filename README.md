\# 📸 AI 智能修图工具



> 基于 DeepSeek V4 视觉大模型的本地化智能修图工具，支持 RAW 格式，AI 自动分析场景并生成修图参数。



\[!\[Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

\[!\[FastAPI](https://img.shields.io/badge/FastAPI-0.141+-green.svg)](https://fastapi.tiangolo.com)

\[!\[DeepSeek](https://img.shields.io/badge/DeepSeek-V4-blueviolet.svg)](https://deepseek.com)



\---



\## ✨ 功能特性



\- 🤖 \*\*AI 场景识别\*\*：自动识别照片的场景类型、光线条件、色彩倾向

\- 📷 \*\*RAW 支持\*\*：支持索尼（.ARW）、佳能（.CR2）、尼康（.NEF）、DNG 等格式

\- 🖼️ \*\*普通图片支持\*\*：不支持 JPG、PNG 等常见格式

\- 🔧 \*\*完整工具链\*\*：色轮（HSL）、曲线、色阶、曝光、锐化、色彩平衡、可选颜色、LUT 滤镜

\- 🖥️ \*\*本地运行\*\*：原始图片不上传云端，仅发送缩略图给 AI 分析，保护隐私

\- 🌐 \*\*网页界面\*\*：拖拽上传，一键修图，简单易用

\- 💬 \*\*反馈调优\*\*：支持自然语言反馈（如"再暖一点"），实时调整效果



\---



\## 🔧 修图工具链



| 工具 | 功能 |

|------|------|

| `adjust\_hsl` | 色相/饱和度/明度调整（色轮） |

| `tone\_curve` | RGB 曲线调色 |

| `rgb\_curve` | 分通道曲线（R/G/B 独立） |

| `adjust\_levels` | 色阶（黑白场 + Gamma） |

| `adjust\_exposure` | 曝光/对比度/高光/阴影 |

| `color\_balance` | 色彩平衡（阴影/中间调/高光） |

| `selective\_color` | 可选颜色（针对特定色相） |

| `apply\_lut` | 滤镜风格（film/cinematic） |

| `sharpen` | 锐化 |

| `denoise` | 降噪 |



\---



\## 🛠️ 技术栈



| 层级 | 技术 |

|------|------|

| 前端 | HTML + CSS + JavaScript |

| 后端 | FastAPI (Python) |

| AI 引擎 | DeepSeek V4 多模态 API |

| RAW 解码 | rawpy (LibRaw) |

| 图像处理 | Pillow + OpenCV + NumPy |

| 调色引擎 | 10 种修图工具 |



\---



\## 🚀 快速开始



\### 1. 克隆项目



```bash

git clone https://github.com/NGBZL/ai-photo-editor.git

cd ai-photo-editor

2\. 安装依赖

bash

pip install fastapi uvicorn rawpy pillow numpy opencv-python scipy openai httpx python-multipart

3\. 设置 API Key

bash

\# Windows (PowerShell)

$env:DEEPSEEK\_API\_KEY = "sk-你的Key"



\# Mac/Linux

export DEEPSEEK\_API\_KEY="sk-你的Key"

在 DeepSeek 平台 获取 API Key



4\. 启动服务

bash

\# 启动后端

python -m uvicorn main:app --host 0.0.0.0 --port 8000



\# 新开终端，启动前端（或直接双击 ui.html）

python -m http.server 8080

5\. 打开浏览器

访问 http://localhost:8080/ui.html



📖 使用说明

上传图片：拖拽或点击上传你的 PNG/RAW 照片



AI 分析：系统自动识别场景类型和光线条件，生成修图方案



一键修图：点击按钮，AI 按顺序执行工具链



反馈调优（可选）：在输入框填写"再暖一点"、"增加对比度"等，AI 会追加调整



下载结果：修图完成后一键下载



支持的文件格式

格式	扩展名

索尼 RAW	.ARW

佳能 RAW	.CR2, .CR3

尼康 RAW	.NEF

通用 RAW	.DNG

📁 项目结构

text

ai-photo-editor/

├── main.py              # FastAPI 后端服务

├── ai\_agent.py          # DeepSeek AI 代理

├── raw\_processor.py     # RAW 文件处理

├── models.py            # 数据模型

├── ui.html              # 前端界面

├── tools/               # 修图工具链

│   ├── base.py          # 工具基类

│   ├── color.py         # 色轮/HSL/色彩平衡/可选颜色

│   ├── curves.py        # 曲线调色

│   ├── levels.py        # 色阶/曝光

│   ├── filter.py        # 滤镜/锐化/降噪

│   └── registry.py      # 工具注册中心

├── uploads/             # 上传文件（本地，Git忽略）

└── outputs/             # 修图结果（本地，Git忽略）

🔄 工作流程

text

用户上传图片

&#x20;   ↓

后端保存 → 返回 file\_id

&#x20;   ↓

AI 分析场景（DeepSeek V4）

&#x20;   ↓

生成修图参数（JSON）

&#x20;   ↓

执行工具链（HSL → 曲线 → 曝光 → 锐化...）

&#x20;   ↓

输出修图结果

&#x20;   ↓

用户下载

