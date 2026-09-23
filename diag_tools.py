"""
临时诊断脚本：逐个工具统计输入/输出，定位"参数温和但结果爆炸"的元凶。

用法（容器内）：
    docker cp diag_tools.py ai-photo-api:/app/diag_tools.py
    docker exec -it ai-photo-api python diag_tools.py [图片路径]

注意：这是临时排查脚本，不要提交到 git。
"""
import os
import sys

import numpy as np

from raw_processor import RAWProcessor
from tools.registry import ToolRegistry
from tools.curves import _build_curve

IMG = sys.argv[1] if len(sys.argv) > 1 else 'uploads/_diag_window.jpg'

# 用户报告里 AI 返回的那一套参数
PARAMS = [
    ("adjust_exposure", {"exposure": 0.15, "contrast": 12, "highlights": -35, "shadows": 28}),
    ("tone_curve", {"points": [{"x": 0, "y": 0}, {"x": 64, "y": 58},
                               {"x": 192, "y": 198}, {"x": 255, "y": 255}]}),
    ("adjust_hsl", {"hue": -3, "saturation": 10, "lightness": -4}),
    ("sharpen", {"amount": 45}),
]

BAR = "=" * 118


def stats(tag, img):
    """打印一张图的统计特征：mean/std/min/max + 死白死黑比例 + 三通道均值"""
    f = img.astype(np.float32)
    blown = float((f >= 254).mean() * 100)
    crushed = float((f <= 1).mean() * 100)
    print(f"  {tag:26s} mean={f.mean():7.2f} std={f.std():6.2f} min={int(img.min()):3d} max={int(img.max()):3d}"
          f" | 死白>=254 {blown:6.2f}%  死黑<=1 {crushed:6.2f}%"
          f" | R/G/B={f[:, :, 0].mean():6.1f}/{f[:, :, 1].mean():6.1f}/{f[:, :, 2].mean():6.1f}")
    return f


print(f"输入图片: {IMG}")
img = RAWProcessor.load(IMG)
print(f"解码后: shape={img.shape} dtype={img.dtype}")

print()
print(BAR)
print("【A】每个工具单独作用在【原图】上的效果（隔离测试）")
print(BAR)
base = img.astype(np.float32)
stats("输入(原图)", img)
for name, params in PARAMS:
    out = ToolRegistry.execute_tool(name, img.copy(), params)
    f = stats(f"{name}", out)
    RAWProcessor.save(out, f'outputs/diag_{name}.jpg', 'jpg', 95)
    print(f"  {'':26s} 相对原图: Δmean={f.mean() - base.mean():+7.2f}  Δstd={f.std() - base.std():+7.2f}"
          f"  死白变化={float((f >= 254).mean() * 100) - float((base >= 254).mean() * 100):+6.2f}%")

print()
print(BAR)
print("【B】按 AI 给的顺序串联（= 线上真实执行顺序）")
print(BAR)
cur = img.copy()
stats("输入", cur)
for name, params in PARAMS:
    cur = ToolRegistry.execute_tool(name, cur.copy(), params)
    stats(f"累计 +{name}", cur)
RAWProcessor.save(cur, 'outputs/diag_chain_FULL.jpg', 'jpg', 95)

print()
print(BAR)
print("【C】把 adjust_exposure 拆成单参数，找出是谁在放大")
print(BAR)
combos = [
    ("只 exposure=0.15", {"exposure": 0.15}),
    ("只 contrast=12", {"contrast": 12}),
    ("只 highlights=-35", {"highlights": -35}),
    ("只 highlights=+35 (反向对照)", {"highlights": 35}),
    ("只 shadows=28", {"shadows": 28}),
    ("highlights=-35 + shadows=28", {"highlights": -35, "shadows": 28}),
]
for label, p in combos:
    out = ToolRegistry.execute_tool("adjust_exposure", img.copy(), p)
    stats(label, out)

print()
print(BAR)
print("【D】tone_curve 查表曲线本身是否正常（插值/单调性）")
print(BAR)
pts = PARAMS[1][1]["points"]
curve = _build_curve(pts)
diff = np.diff(curve.astype(int))
print(f"  LUT: len={len(curve)} min={curve.min()} max={curve.max()} dtype={curve.dtype}")
print(f"  单调递增: {bool(np.all(diff >= 0))}   最大单步跳变: {int(diff.max())}   最小单步: {int(diff.min())}")
print("  关键点映射: " + "  ".join(f"{x}->{curve[x]}" for x in (0, 32, 64, 128, 192, 224, 255)))

print()
print(BAR)
print("【E】白场/黑场参数（AI 这次没给，验证一下潜在问题）")
print(BAR)
for label, p in [("whites=+50", {"whites": 50}), ("whites=-50", {"whites": -50}),
                 ("blacks=+50", {"blacks": 50}), ("blacks=-50", {"blacks": -50})]:
    out = ToolRegistry.execute_tool("adjust_exposure", img.copy(), p)
    stats(label, out)
