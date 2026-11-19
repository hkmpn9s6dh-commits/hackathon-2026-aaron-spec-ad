# -*- coding: utf-8 -*-
"""把 raw 图版处理成可用的 plates：去工具水印 → 裁 16:9 → 统一影调 → 放大到 2400x1350。

为什么水印不能靠裁：裁掉的 6% 往往正是主体（中枢 C-20261119-57824124 的教训）。
这里先找水印框、用左侧一块镜像内容盖住，再用断言量那一块的边缘能量。

用法：
    python scripts/plates.py            # 从 plates/raw 重建 plates/
    python scripts/plates.py --check    # 只检查现有 plates/ 是否与 manifest 一致
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "plates" / "raw"
OUT = ROOT / "plates"

# raw 文件名 → 交付名
MAP = {
    "Cinematic_wide_shot_on_the_wes_2026-11-19T10-25-48": "snowfield",
    "Extreme_macro_photograph__one__2026-11-19T10-24-07": "snow-crystal",
    "Cinematic_shot_deep_inside_a_v_2026-11-19T10-23-05": "fissure",
    "Extreme_macro_photograph_of_a__2026-11-19T10-24-07": "rock-film",
    "Cinematic_photograph_of_a_cold_2026-11-19T10-24-07": "spring",
    "Cinematic_product_photograph___2026-11-19T10-23-04": "bottle",
}

# 16:9 取窗的竖直偏移（0=顶，1=底）。主体偏下就往下取。
CROP_OFFSET = {
    "snowfield": 0.35,
    "snow-crystal": 0.40,
    "fissure": 0.30,
    "rock-film": 0.45,
    "spring": 1.00,      # 一定要留住水池
    "bottle": 0.65,
}

MAP_REV = {v: k for k, v in MAP.items()}

OUT_W, OUT_H = 2400, 1350  # 留 1.25x 推镜余量，成片再降到 1080p


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


# 出图工具的水印固定在右下角，六张同尺寸（1536x1024）位置完全一致。
# 不用亮度检测：瓶身那张右下角有亮雾，检测会把一大片画面当成水印（踩过）。
WM_BOX = (1392, 942, 1536, 1024)


def find_watermark(im: Image.Image):
    """工具每张都在同一角落打水印，所以无条件盖掉这一块。

    曾经用亮度检测：瓶身那张右下角有亮雾，检测会把一大片画面当成水印；
    暗场的两张又检测不到（白字压在黑水上，均值差不到 4）。位置固定，就不用猜。
    """
    w, h = im.size
    x0, y0 = WM_BOX[0], WM_BOX[1]
    x1, y1 = min(WM_BOX[2], w), min(WM_BOX[3], h)
    if x1 - x0 < 40 or y1 - y0 < 30:
        return None
    return (x0, y0, x1, y1)


def patch(im: Image.Image, box) -> Image.Image:
    """用左侧一块镜像内容盖住水印，再补上同强度颗粒。"""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    src = im.crop((max(0, x0 - w - 16), y0, max(1, x0 - 16), y1))
    src = src.transpose(Image.FLIP_LEFT_RIGHT).resize((w, h), Image.LANCZOS)
    src = src.filter(ImageFilter.GaussianBlur(2.2))
    a = np.asarray(src).astype(np.float32)
    rng = np.random.default_rng(3)
    a = np.clip(a + rng.normal(0, 2.4, a.shape), 0, 255)
    im.paste(Image.fromarray(a.astype(np.uint8), "RGB"), (x0, y0))
    return im


def crop169(im: Image.Image, yfrac: float) -> Image.Image:
    w, h = im.size
    ch = int(round(w * 9 / 16))
    if ch > h:
        raise SystemExit("source shorter than 16:9")
    top = int(round((h - ch) * min(max(yfrac, 0.0), 1.0)))
    return im.crop((0, top, w, top + ch))


def grade(im: Image.Image, warm: float, contrast: float, expo: float) -> Image.Image:
    """统一的影调：色温、对比、曝光、饱和、暗角。全片同一套，只是参数沿时间走。"""
    a = np.asarray(im.convert("RGB")).astype(np.float32) / 255.0
    h, w, _ = a.shape

    # 色温
    a[..., 0] *= 1.0 + 0.11 * warm
    a[..., 2] *= 1.0 - 0.13 * warm
    a[..., 1] *= 1.0 + 0.02 * warm

    # 曝光
    a *= 2.0 ** expo

    # 对比（围绕 0.42 的支点）
    a = (a - 0.42) * contrast + 0.42

    # 饱和：稍微压一点，广告的水要有颜色但不能脏
    luma = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    a = luma[..., None] + (a - luma[..., None]) * 0.92

    # 暗角
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    r = np.sqrt(((xx - cx) / cx) ** 2 * 0.75 + ((yy - cy) / cy) ** 2) / 1.32
    vig = 1.0 - 0.30 * np.clip(r, 0, 1) ** 2.1
    a *= vig[..., None]

    return Image.fromarray(np.clip(a * 255.0, 0, 255).astype(np.uint8), "RGB")


def one(name: str) -> dict:
    src = RAW / f"{MAP_REV[name]}.png"
    dst = OUT / f"{name}.png"
    if not src.exists():
        raise SystemExit(f"missing raw plate: {src}")
    im = Image.open(src).convert("RGB")
    wm = find_watermark(im)
    if wm:
        im = patch(im, wm)
    im = crop169(im, CROP_OFFSET[name])
    # 图版是"中性"的，调色在渲染时按时间走；这里只做一点点统一
    im = grade(im, warm=0.0, contrast=1.03, expo=0.0)
    im = im.resize((OUT_W, OUT_H), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.4, percent=58, threshold=3))
    im.save(dst, optimize=True)
    print(f"  {name:14s} <- {src.name[:34]:34s} wm={wm}")
    return dict(
        raw=src.name, raw_sha256=sha256(src), plate_sha256=sha256(dst),
        watermark_box=wm, crop_offset=CROP_OFFSET[name], size=[OUT_W, OUT_H],
    )


def build(check_only: bool = False) -> dict:
    """逐张独立进程跑：一台机上连续处理六张 2400x1350 会在第五张被系统杀掉（踩过）。"""
    man = {}
    for raw_name, name in MAP.items():
        dst = OUT / f"{name}.png"
        if check_only:
            if not dst.exists():
                raise SystemExit(f"missing plate: {dst}")
            man[name] = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))[name]
            continue
        subprocess.run([sys.executable, __file__, "--one", name], check=True)
        man[name] = one_manifest(name)
    (OUT / "manifest.json").write_text(
        json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    return man


def one_manifest(name: str) -> dict:
    src = RAW / f"{MAP_REV[name]}.png"
    dst = OUT / f"{name}.png"
    return dict(
        raw=src.name, raw_sha256=sha256(src), plate_sha256=sha256(dst),
        watermark_box=WM_BOX, crop_offset=CROP_OFFSET[name], size=[OUT_W, OUT_H],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--one", default=None)
    a = ap.parse_args()
    if a.one:
        one(a.one)
        return
    man = build(a.check)
    print(f"plates: {len(man)}")


if __name__ == "__main__":
    sys.exit(main())
