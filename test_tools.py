"""
工具回归测试：断言每个工具的方向性、不放大性、以及输出契约。

跑法（容器里，因为需要 cv2/numpy）：
    docker cp test_tools.py ai-photo-api:/app/test_tools.py
    docker exec ai-photo-api python test_tools.py

这些测试专门盯住已经踩过的坑：
  * highlights 负值必须【压暗】高光（旧实现符号反了，-35 变成高光 +35%，过曝发白）
  * shadows 正值必须【提亮】阴影
  * contrast 不能制造新的高光截断
  * whites/blacks 必须真的生效且方向正确（旧实现 blacks 是死代码、whites 方向反了）
"""
import numpy as np

from tools.registry import ToolRegistry
from tools.curves import _build_curve

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}  {detail}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {detail}")


def blow(img):
    """死白像素占比(%)"""
    return float((img.astype(np.float32) >= 254).mean() * 100)


def crushed(img):
    """死黑像素占比(%)"""
    return float((img.astype(np.float32) <= 1).mean() * 100)


def scene():
    """高动态范围"室内窗户"测试图：亮窗 / 中间调 / 暗室内"""
    img = np.zeros((240, 360, 3), np.uint8)
    img[:80] = 250      # 亮部：窗
    img[80:160] = 128   # 中间调：墙
    img[160:] = 25      # 暗部：室内
    return img


BRIGHT = slice(0, 80)
MID = slice(80, 160)
DARK = slice(160, 240)


def rmean(img, sl):
    return float(img[sl].astype(np.float32).mean())


ALL_TOOLS = [
    ("adjust_exposure", {"exposure": 0.15, "contrast": 12, "highlights": -35, "shadows": 28}),
    ("adjust_levels", {"black": 8, "gamma": 1.05, "white": 248}),
    ("adjust_hsl", {"hue": -3, "saturation": 10, "lightness": -4}),
    ("tone_curve", {"points": [{"x": 0, "y": 0}, {"x": 64, "y": 58}, {"x": 192, "y": 198}, {"x": 255, "y": 255}]}),
    ("rgb_curve", {"red_points": [{"x": 0, "y": 0}, {"x": 128, "y": 132}, {"x": 255, "y": 255}]}),
    ("sharpen", {"amount": 45}),
    ("color_balance", {"midtones": {"cyan_red": 10, "magenta_green": 0, "yellow_blue": -8}}),
    ("apply_lut", {"style": "film", "intensity": 60}),
]

img0 = scene()

print("=" * 100)
print("1) 输出契约：uint8 / 形状不变 / 值域 0-255")
print("=" * 100)
for name, params in ALL_TOOLS:
    out = ToolRegistry.execute_tool(name, img0.copy(), params)
    check(f"{name} 契约",
          out.dtype == np.uint8 and out.shape == img0.shape and out.min() >= 0 and out.max() <= 255,
          f"dtype={out.dtype} shape={out.shape} range=[{out.min()},{out.max()}]")

print()
print("=" * 100)
print("2) 高光方向（重点：旧代码此处符号反了）")
print("=" * 100)
neg = ToolRegistry.execute_tool("adjust_exposure", img0.copy(), {"highlights": -35})
pos = ToolRegistry.execute_tool("adjust_exposure", img0.copy(), {"highlights": 35})
b_in, b_neg, b_pos = rmean(img0, BRIGHT), rmean(neg, BRIGHT), rmean(pos, BRIGHT)
check("highlights=-35 压暗高光", b_neg < b_in - 5, f"亮部 {b_in:.1f} -> {b_neg:.1f}")
check("highlights=+35 提亮高光", b_pos > b_in + 1, f"亮部 {b_in:.1f} -> {b_pos:.1f}")
check("highlights=-35 不产生新死白", blow(neg) <= blow(img0) + 0.01, f"死白 {blow(img0):.2f}% -> {blow(neg):.2f}%")
check("highlights=-35 不动暗部", abs(rmean(neg, DARK) - rmean(img0, DARK)) < 3.0,
      f"暗部 {rmean(img0, DARK):.1f} -> {rmean(neg, DARK):.1f}")

print()
print("=" * 100)
print("3) 阴影方向")
print("=" * 100)
up = ToolRegistry.execute_tool("adjust_exposure", img0.copy(), {"shadows": 28})
dn = ToolRegistry.execute_tool("adjust_exposure", img0.copy(), {"shadows": -28})
check("shadows=+28 提亮阴影", rmean(up, DARK) > rmean(img0, DARK) + 1, f"暗部 {rmean(img0, DARK):.1f} -> {rmean(up, DARK):.1f}")
check("shadows=-28 压暗阴影", rmean(dn, DARK) < rmean(img0, DARK) - 1, f"暗部 {rmean(img0, DARK):.1f} -> {rmean(dn, DARK):.1f}")
check("shadows=+28 不动高光", abs(rmean(up, BRIGHT) - rmean(img0, BRIGHT)) < 3.0,
      f"亮部 {rmean(img0, BRIGHT):.1f} -> {rmean(up, BRIGHT):.1f}")

print()
print("=" * 100)
print("4) 对比度不制造新的高光截断（旧实现是线性拉伸，必截断）")
print("=" * 100)
ramp = np.tile(np.arange(256, dtype=np.uint8)[None, :, None], (8, 1, 3))
for c in (12, 50, 100):
    out = ToolRegistry.execute_tool("adjust_exposure", ramp.copy(), {"contrast": c})
    row = out[0, :, 0].astype(int)
    mono = bool(np.all(np.diff(row) >= 0))
    top = row[240:256]
    check(f"contrast={c} 查表单调不反转", mono, f"最大单步={int(np.diff(row).max())} 最小单步={int(np.diff(row).min())}")
    check(f"contrast={c} 端点保持 0/255", row[0] == 0 and row[255] == 255, f"{row[0]} -> {row[255]}")
    # 关键：250 不能被推成纯白 255（否则窗/天空这类区域会直接塌成一片白）
    check(f"contrast={c} 250 未塌成纯白", row[250] < 255, f"250 -> {row[250]}")
    # 顶部层次：S 曲线必然压缩两端，但绝不能塌成一片（旧线性拉伸会把 229 以上全推成 255 = 1 级）
    need = 10 if c <= 12 else 4
    check(f"contrast={c} 顶部仍有层次(>={need} 级)", len(set(top.tolist())) >= need,
          f"240..255 -> {len(set(top.tolist()))} 个不同值")
    check(f"contrast={c} 确实拉开了中间调", row[192] > 193 and row[64] < 63,
          f"64 -> {row[64]}, 192 -> {row[192]}")

# 报告里的温和值必须一点都不爆：窗户场景里 250 的亮部不能新增死白
sc_neg = ToolRegistry.execute_tool("adjust_exposure", img0.copy(), {"contrast": 12})
check("contrast=12 在窗户场景下不新增死白", blow(sc_neg) <= blow(img0) + 0.01,
      f"死白 {blow(img0):.2f}% -> {blow(sc_neg):.2f}%")

print()
print("=" * 100)
print("5) whites / blacks 必须生效且方向正确（旧实现 blacks 完全没作用）")
print("=" * 100)
w_p = ToolRegistry.execute_tool("adjust_exposure", img0.copy(), {"whites": 30})
w_n = ToolRegistry.execute_tool("adjust_exposure", img0.copy(), {"whites": -30})
b_p = ToolRegistry.execute_tool("adjust_exposure", img0.copy(), {"blacks": 30})
b_n = ToolRegistry.execute_tool("adjust_exposure", img0.copy(), {"blacks": -30})
check("whites=+30 整体变亮", w_p.astype(np.float32).mean() > img0.astype(np.float32).mean() + 1,
      f"mean {img0.astype(np.float32).mean():.1f} -> {w_p.astype(np.float32).mean():.1f}")
check("whites=-30 整体变暗", w_n.astype(np.float32).mean() < img0.astype(np.float32).mean() - 1,
      f"mean {img0.astype(np.float32).mean():.1f} -> {w_n.astype(np.float32).mean():.1f}")
check("blacks=+30 压暗暗部", rmean(b_p, DARK) < rmean(img0, DARK) - 1, f"暗部 {rmean(img0, DARK):.1f} -> {rmean(b_p, DARK):.1f}")
check("blacks=-30 提亮暗部", rmean(b_n, DARK) > rmean(img0, DARK) + 1, f"暗部 {rmean(img0, DARK):.1f} -> {rmean(b_n, DARK):.1f}")
check("blacks=0 时不动图", np.array_equal(
    ToolRegistry.execute_tool("adjust_exposure", img0.copy(), {"blacks": 0}), img0))

print()
print("=" * 100)
print("6) tone_curve 曲线本身")
print("=" * 100)
pts = [{"x": 0, "y": 0}, {"x": 64, "y": 58}, {"x": 192, "y": 198}, {"x": 255, "y": 255}]
curve = _build_curve(pts)
check("LUT 单调递增", bool(np.all(np.diff(curve.astype(int)) >= 0)), f"最大跳变={int(np.diff(curve.astype(int)).max())}")
check("LUT 端点 0->0 / 255->255", curve[0] == 0 and curve[255] == 255, f"{curve[0]} / {curve[255]}")
check("LUT 命中控制点", abs(int(curve[64]) - 58) <= 1 and abs(int(curve[192]) - 198) <= 1,
      f"64->{curve[64]} 192->{curve[192]}")
for n in (2, 3, 4, 8):
    xs = np.linspace(0, 255, n).astype(int)
    c = _build_curve([{"x": int(x), "y": int(x)} for x in xs])
    check(f"{n} 个控制点的恒等曲线不失真", bool(np.all(np.abs(c.astype(int) - np.arange(256)) <= 2)))

print()
print("=" * 100)
print("7) adjust_hsl 方向")
print("=" * 100)
sat = ToolRegistry.execute_tool("adjust_hsl", img0.copy(), {"saturation": 30})
lig = ToolRegistry.execute_tool("adjust_hsl", img0.copy(), {"lightness": -30})
check("saturation=+30 变亮/变艳（mean 上升或 std 上升）",
      ToolRegistry.execute_tool("adjust_hsl", scene().copy(), {"saturation": 30}).astype(np.float32).std()
      >= img0.astype(np.float32).std() - 0.01, "")
check("lightness=-30 整体变暗", lig.astype(np.float32).mean() < img0.astype(np.float32).mean() - 3,
      f"mean {img0.astype(np.float32).mean():.1f} -> {lig.astype(np.float32).mean():.1f}")
check("hue 偏移不改变整体亮度", abs(ToolRegistry.execute_tool("adjust_hsl", img0.copy(), {"hue": 20})
      .astype(np.float32).mean() - img0.astype(np.float32).mean()) < 1.0, "")

print()
print("=" * 100)
print("8) sharpen 不应改变整体亮度、不应大幅新增死白")
print("=" * 100)
sh = ToolRegistry.execute_tool("sharpen", img0.copy(), {"amount": 45})
check("sharpen 保持亮度", abs(sh.astype(np.float32).mean() - img0.astype(np.float32).mean()) < 0.5,
      f"Δmean={sh.astype(np.float32).mean() - img0.astype(np.float32).mean():+.3f}")
check("sharpen 死白增幅 <= 0.5%", blow(sh) <= blow(img0) + 0.5, f"死白 {blow(img0):.2f}% -> {blow(sh):.2f}%")
sh200 = ToolRegistry.execute_tool("sharpen", img0.copy(), {"amount": 200})
check("sharpen amount=200 仍在值域内", sh200.min() >= 0 and sh200.max() <= 255, f"range=[{sh200.min()},{sh200.max()}]")

print()
print("=" * 100)
print("9) 整链回归：用户报告的那套参数，不能再把画面修爆")
print("=" * 100)
chain = [
    ("adjust_exposure", {"exposure": 0.15, "contrast": 12, "highlights": -35, "shadows": 28}),
    ("tone_curve", {"points": pts}),
    ("adjust_hsl", {"hue": -3, "saturation": 10, "lightness": -4}),
    ("sharpen", {"amount": 45}),
]
cur = img0.copy()
for name, params in chain:
    cur = ToolRegistry.execute_tool(name, cur.copy(), params)
print(f"  输入 : mean={img0.astype(np.float32).mean():.1f} std={img0.astype(np.float32).std():.1f} "
      f"死白={blow(img0):.2f}% 暗部均值={rmean(img0, DARK):.1f}")
print(f"  输出 : mean={cur.astype(np.float32).mean():.1f} std={cur.astype(np.float32).std():.1f} "
      f"死白={blow(cur):.2f}% 暗部均值={rmean(cur, DARK):.1f}")
check("整链不新增死白", blow(cur) <= blow(img0) + 1.0, f"死白 {blow(img0):.2f}% -> {blow(cur):.2f}%")
check("整链不新增死黑", crushed(cur) <= crushed(img0) + 1.0, f"死黑 {crushed(img0):.2f}% -> {crushed(cur):.2f}%")
check("亮部没被抹平（仍有层次）", rmean(cur, BRIGHT) > 100, f"亮部均值 {rmean(cur, BRIGHT):.1f}")
check("暗部没被过曝洗白", rmean(cur, DARK) < 90, f"暗部均值 {rmean(cur, DARK):.1f}")
check("整体没有明显过曝（mean 涨幅 < 15）", cur.astype(np.float32).mean() - img0.astype(np.float32).mean() < 15,
      f"Δmean={cur.astype(np.float32).mean() - img0.astype(np.float32).mean():+.1f}")

print()
print("=" * 100)
print("10) apply_lut：intensity 必须真的控制强度（旧实现 intensity=0 也是全强度）")
print("=" * 100)
lut0 = ToolRegistry.execute_tool("apply_lut", img0.copy(), {"style": "film", "intensity": 0})
lut100 = ToolRegistry.execute_tool("apply_lut", img0.copy(), {"style": "film", "intensity": 100})
check("film intensity=0 等于不改图", np.array_equal(lut0, img0),
      f"最大差异={int(np.abs(lut0.astype(int) - img0.astype(int)).max())}")
check("film intensity=100 确实产生效果",
      abs(lut100.astype(np.float32).mean() - img0.astype(np.float32).mean()) > 5,
      f"mean {img0.astype(np.float32).mean():.1f} -> {lut100.astype(np.float32).mean():.1f}")
steps = [20, 60, 100]
means = [ToolRegistry.execute_tool("apply_lut", img0.copy(), {"style": "film", "intensity": i}).astype(np.float32).mean()
         for i in [0] + steps]
check("film 强度单调递增", all(b >= a - 0.01 for a, b in zip(means, means[1:])),
      " -> ".join(f"{m:.1f}" for m in means))
check("cinematic intensity=0 等于不改图",
      np.array_equal(ToolRegistry.execute_tool("apply_lut", img0.copy(), {"style": "cinematic", "intensity": 0}), img0))

print()
print("=" * 100)
print(f"结果：PASS={PASS}  FAIL={FAIL}")
print("=" * 100)
raise SystemExit(1 if FAIL else 0)
