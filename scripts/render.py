# -*- coding: utf-8 -*-
"""逐帧渲染《三十年前的雪》。

一个镜头 = 一张图版 + 一条运镜 + 若干程序化叠加层 + 一条调色曲线。
不做整帧重运算（中枢 C-20261115-326cff81 的教训）：调色只做线性变换，
暗角与颗粒是预乘好的层，文字只画在需要的那几帧上。

用法：
    python scripts/render.py --from 0 --to 240 --out build/seg0.mp4
"""
import argparse
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import story as S  # noqa: E402
from ff import FFMPEG, FFPROBE  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PLATES = ROOT / "plates"
FONTS = Path("C:/Windows/Fonts")
W, H = S.W, S.H
FPS = S.FPS
GRAIN_STRENGTH = 3.6

SERIF = "NotoSerifSC-VF.ttf"
SANS = "NotoSansSC-VF.ttf"


# ------------------------------------------------------------------ 时间轴
def layout():
    """每个镜头的有效区间：叠化让后一个镜头提前进来。"""
    out = []
    for i, sh in enumerate(S.SHOTS):
        prev = S.SHOTS[i - 1] if i else None
        xf = S.XFADE.get((prev["id"], sh["id"]), 0.0) if prev else 0.0
        start = sh["start"] - xf
        out.append(dict(shot=sh, start=start, end=sh["end"], xf_in=xf))
    return out


LAYOUT = layout()


def frames_total():
    return int(round(S.FILM_SEC * FPS))


def shots_at(t):
    """返回 [(镜头, 进度 0..1, 权重)]，最多两个（叠化时）。"""
    act = []
    for x in LAYOUT:
        if x["start"] <= t < x["end"]:
            k = (t - x["start"]) / max(1e-6, (x["end"] - x["start"]))
            act.append((x, k))
    if not act:
        act = [(LAYOUT[-1], 0.999)]
    if len(act) == 1:
        return [(act[0][0], act[0][1], 1.0)]
    (a, ka), (b, kb) = act[0], act[1]
    span = max(1e-6, a["end"] - b["start"])
    wb = min(1.0, max(0.0, (t - b["start"]) / span))
    return [(a, ka, 1.0 - wb), (b, kb, wb)]


# ------------------------------------------------------------------ 运镜
def ease(k, kind):
    k = min(1.0, max(0.0, k))
    if kind == "in":
        return k * k
    if kind == "out":
        return 1.0 - (1.0 - k) ** 2
    if kind == "inout":
        return k * k * (3 - 2 * k)
    return k


def crop_window(plate, mv, prog):
    z0, z1, cx0, cy0, cx1, cy1, kind = mv
    e = ease(prog, kind)
    z = z0 + (z1 - z0) * e
    cx = cx0 + (cx1 - cx0) * e
    cy = cy0 + (cy1 - cy0) * e
    pw, ph = plate.size
    win_h = ph / z
    win_w = win_h * 16.0 / 9.0
    if win_w > pw:
        win_w = pw
        win_h = win_w * 9.0 / 16.0
    left = cx * pw - win_w / 2.0
    top = cy * ph - win_h / 2.0
    left = min(max(0.0, left), pw - win_w)
    top = min(max(0.0, top), ph - win_h)
    box = (int(round(left)), int(round(top)),
           int(round(left + win_w)), int(round(top + win_h)))
    return plate.crop(box).resize((W, H), Image.BILINEAR)


# ------------------------------------------------------------------ 调色
def grade_params(t):
    g = S.GRADE
    if t <= g[0][0]:
        return g[0][1:]
    for i in range(len(g) - 1):
        t0, w0, c0, e0 = g[i]
        t1, w1, c1, e1 = g[i + 1]
        if t0 <= t <= t1:
            k = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            k = k * k * (3 - 2 * k)
            return (w0 + (w1 - w0) * k, c0 + (c1 - c0) * k, e0 + (e1 - e0) * k)
    return g[-1][1:]


_vig = None


def vignette():
    global _vig
    if _vig is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        cx, cy = (W - 1) / 2.0, (H - 1) / 2.0
        r = np.sqrt(((xx - cx) / cx) ** 2 * 0.80 + ((yy - cy) / cy) ** 2) / 1.30
        _vig = (1.0 - 0.26 * np.clip(r, 0, 1) ** 2.0).astype(np.float32)[..., None]
    return _vig


def apply_grade(arr, warm, contrast, expo):
    a = arr.astype(np.float32) / 255.0
    a[..., 0] *= 1.0 + 0.10 * warm
    a[..., 1] *= 1.0 + 0.015 * warm
    a[..., 2] *= 1.0 - 0.12 * warm
    if expo:
        a *= 2.0 ** expo
    a = (a - 0.42) * contrast + 0.42
    luma = a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722
    a += (luma[..., None] - a) * 0.06      # 压一点饱和
    a *= vignette()
    np.clip(a, 0.0, 1.0, out=a)
    return a


# ------------------------------------------------------------------ 叠加层
_grain = None


def grain_tiles():
    global _grain
    if _grain is not None:
        return _grain
    cache = ROOT / "build" / "grain.npz"
    if cache.exists():
        z = np.load(str(cache))
        _grain = z["t"]
        return _grain
    cache.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    t = rng.normal(0, GRAIN_STRENGTH, (10, H, W)).astype(np.float32)
    np.savez_compressed(str(cache), t=t)
    _grain = t
    return _grain


def soft_field(size, seed, blur=90, lo=0.0, hi=1.0):
    """一张低分辨率的随机场放大成柔光/雾。"""
    rng = np.random.default_rng(seed)
    small = rng.random((size[1] // 32, size[0] // 32)).astype(np.float32)
    im = Image.fromarray((small * 255).astype(np.uint8), "L").resize(size, Image.BICUBIC)
    im = im.filter(ImageFilter.GaussianBlur(blur))
    a = np.asarray(im).astype(np.float32) / 255.0
    a = (a - a.min()) / max(1e-6, (a.max() - a.min()))
    return lo + (hi - lo) * a


_snow = None


def snow_layers():
    """三层雪：近的快、远的小。预乘成亮度层，加法叠上去。"""
    global _snow
    if _snow is not None:
        return _snow
    cache = ROOT / "build" / "snow.npz"
    if cache.exists():
        z = np.load(str(cache))
        _snow = [z["a"], z["b"], z["c"]]
        return _snow
    rng = np.random.default_rng(11)
    layers = []
    ch, cw = H + 260, W + 320
    for num, rad, bright in [(420, 0.85, 0.34), (190, 1.5, 0.42), (60, 2.6, 0.55)]:
        lay = np.zeros((ch, cw), dtype=np.float32)
        xs = rng.uniform(0, cw, num)
        ys = rng.uniform(0, ch, num)
        for x, y in zip(xs, ys):
            rr = rad * rng.uniform(0.55, 1.5)
            x0, x1 = int(max(0, x - 3 * rr)), int(min(cw, x + 3 * rr + 1))
            y0, y1 = int(max(0, y - 7 * rr)), int(min(ch, y + 7 * rr + 1))
            if x1 <= x0 or y1 <= y0:
                continue
            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            d2 = ((xx - x) ** 2) / (2 * rr * rr) + ((yy - y) ** 2) / (2 * (rr * 3.0) ** 2)
            lay[y0:y1, x0:x1] += np.exp(-d2) * bright
        layers.append(np.clip(lay, 0, 2))
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(str(cache), a=layers[0], b=layers[1], c=layers[2])
    _snow = layers
    return layers


def scroll(layer, dx, dy):
    """把大层按 (dx,dy) 取一个 W×H 的窗口（带环绕）。"""
    ch, cw = layer.shape
    x = int(dx) % cw
    y = int(dy) % ch
    big = np.take(layer, (np.arange(y, y + H) % ch), axis=0)
    return big[:, (np.arange(x, x + W) % cw)]


_flare = None


def flare_field():
    global _flare
    if _flare is not None:
        return _flare
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W * 0.50, H * 0.30
    d = np.sqrt(((xx - cx) / (W * 0.30)) ** 2 + ((yy - cy) / (H * 0.30)) ** 2)
    g = np.exp(-(d ** 2) * 1.4)
    core = np.exp(-((d * 3.2) ** 2) * 1.2)
    _flare = np.clip(g * 0.55 + core * 0.85, 0, 1.2).astype(np.float32)[..., None]
    return _flare


_spray = None


def spray_points():
    global _spray
    if _spray is not None:
        return _spray
    rng = np.random.default_rng(23)
    n = 260
    _spray = dict(
        x=rng.normal(0, 0.055, n), y=rng.normal(0, 0.03, n),
        vx=rng.normal(0, 0.045, n), vy=-np.abs(rng.normal(0.10, 0.06, n)),
        r=rng.uniform(0.6, 2.2, n), ph=rng.uniform(0, 6.28, n),
        life=rng.uniform(0.5, 1.4, n),
    )
    return _spray


_mist = None


def mist_field():
    global _mist
    if _mist is None:
        _mist = soft_field((W, H), 5, blur=110, lo=0.0, hi=1.0).astype(np.float32)[..., None]
    return _mist


def add(arr, layer, k):
    if k == 0:
        return
    arr += layer * k


def bloom(arr, amount=0.35, thresh=0.66):
    luma = arr.max(axis=2)
    hot = np.clip((luma - thresh) / (1.0 - thresh), 0, 1)
    im = Image.fromarray((hot * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(26))
    g = np.asarray(im).astype(np.float32) / 255.0
    arr += g[..., None] * amount


def draw_spray(arr, t, cx=0.50, cy=0.62, k=1.0):
    p = spray_points()
    n = len(p["r"])
    for i in range(n):
        tau = ((t / p["life"][i]) + p["ph"][i]) % 1.0
        x = cx + p["x"][i] + p["vx"][i] * tau
        y = cy + p["y"][i] + p["vy"][i] * tau + 0.10 * tau * tau
        px, py = int(x * W), int(y * H)
        if not (0 <= px < W - 3 and 0 <= py < H - 3):
            continue
        a = (1.0 - tau) * 0.55 * k
        r = int(round(p["r"][i]))
        arr[py:py + r + 1, px:px + r + 1] += a * (0.7 + 0.3 * math.sin(t * 9 + i))


def draw_thread(arr, t, k=1.0, cx=0.50, amp=0.055, speed=1.0):
    """一道贴着岩壁往下走的水线——S04 那 6 秒要有"水在走"，否则只是一张石头。

    一行一行地加一条带柔边的亮线，再在最前面点一颗水珠。
    """
    ys = np.arange(H, dtype=np.float32)
    u = ys / float(H)
    phase = t * 0.55 * speed
    xs = cx * W + amp * W * np.sin(u * 5.2 + phase) * (0.6 + 0.4 * u)
    for y in range(H):
        x = int(xs[y])
        w = 3.0 + 5.0 * (y / H)
        a = k * (0.20 + 0.07 * math.sin(u[y] * 9.0 - t * 1.7))
        x0, x1 = max(0, int(x - 4 * w)), min(W, int(x + 4 * w) + 1)
        if x1 <= x0:
            continue
        d = (np.arange(x0, x1, dtype=np.float32) - x) / w
        arr[y, x0:x1] += (np.exp(-d * d * 1.6) * a)[..., None] * np.array(
            [0.72, 0.86, 1.0], dtype=np.float32)
    # 水珠
    by = ((t * 0.16) % 1.0)
    by = 0.10 + 0.72 * by
    bx = cx * W + amp * W * math.sin(by * 5.2 + phase)
    R = 13
    yy0, yy1 = int(by * H) - R, int(by * H) + R
    xx0, xx1 = int(bx) - R, int(bx) + R
    if 0 <= yy0 and yy1 < H and 0 <= xx0 and xx1 < W:
        yy, xx = np.mgrid[yy0:yy1, xx0:xx1].astype(np.float32)
        d2 = ((xx - bx) ** 2 + (yy - by * H) ** 2) / (R * R * 0.16)
        arr[yy0:yy1, xx0:xx1] += (np.exp(-d2) * 0.95 * k)[..., None] * np.array(
            [0.80, 0.92, 1.0], dtype=np.float32)


# ------------------------------------------------------------------ 文字
_font_cache = {}


def font(name, size):
    key = (name, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(str(FONTS / name), size)
    return _font_cache[key]


def tracked_width(txt, f, track):
    return sum(f.getlength(c) for c in txt) + track * max(0, len(txt) - 1)


def draw_tracked(d, xy, txt, f, fill, track, anchor="ls"):
    x, y = xy
    if anchor.startswith("m"):
        x -= tracked_width(txt, f, track) / 2.0
    for c in txt:
        d.text((x, y), c, font=f, fill=fill, anchor="ls")
        x += f.getlength(c) + track
    return x - track


def card_layout(card):
    """返回一张卡在成片里的位置（像素）。verify.py 用同一套算术。"""
    f = font(SERIF, card["size"])
    tw = tracked_width(card["text"], f, card["size"] * 0.05)
    if card["place"] == "lower-left":
        x0 = 150
        base = 884
        rule_y = base - int(card["size"] * 1.62)
        return dict(x0=x0, y0=rule_y - 3, x1=int(x0 + tw), y1=int(base + card["size"] * 0.34),
                    base=base, rule_y=rule_y, tw=tw)
    if card["place"] == "center-low":
        base = 968
        x0 = int((W - tw) / 2)
        return dict(x0=x0, y0=int(base - card["size"] * 1.10), x1=int(x0 + tw),
                    y1=int(base + card["size"] * 0.34), base=base, rule_y=None, tw=tw)
    raise SystemExit("unknown place: " + card["place"])


def endcard_layout():
    fb = font(SERIF, S.ENDCARD["brand_size"])
    fs = font(SANS, S.ENDCARD["slogan_size"])
    fd = font(SANS, S.ENDCARD["disclosure_size"])
    x0 = 150
    brand_base = 820
    slogan_base = 898
    disc_base = 952
    bw = tracked_width(S.ENDCARD["brand"], fb, S.ENDCARD["brand_size"] * 0.06)
    sw = tracked_width(S.ENDCARD["slogan"], fs, 0.6)
    dw = tracked_width(S.ENDCARD["disclosure"], fd, 0.4)
    return dict(
        x0=x0,
        brand=dict(base=brand_base, w=bw, box=(x0, brand_base - S.ENDCARD["brand_size"],
                                               int(x0 + bw), brand_base + 12)),
        rule=(x0, brand_base + 24, int(x0 + min(bw, 460))),
        slogan=dict(base=slogan_base, w=sw,
                    box=(x0, slogan_base - S.ENDCARD["slogan_size"],
                         int(x0 + sw), slogan_base + 8)),
        disclosure=dict(base=disc_base, w=dw,
                        box=(x0, disc_base - S.ENDCARD["disclosure_size"],
                             int(x0 + dw), disc_base + 6)),
    )


def _draw_all(d, t, color, dy=0):
    """把这一帧所有该出现的字画进 d。color 是四元组 (r,g,b,a)。"""
    for c in S.CARDS:
        if not (c["t_in"] - 0.001 <= t <= c["t_out"]):
            continue
        L = card_layout(c)
        f = font(SERIF, c["size"])
        if L["rule_y"] is not None:
            d.line([(L["x0"], L["rule_y"] + dy), (L["x0"] + 64, L["rule_y"] + dy)],
                   fill=(color[0], color[1], color[2], int(color[3] * 0.55)), width=2)
        draw_tracked(d, (L["x0"], L["base"] + dy), c["text"], f,
                     color, c["size"] * 0.05)
    e = S.ENDCARD
    if e["t_in"] - 0.001 <= t <= e["t_out"]:
        L = endcard_layout()
        fb = font(SERIF, e["brand_size"])
        fs = font(SANS, e["slogan_size"])
        fd = font(SANS, e["disclosure_size"])
        draw_tracked(d, (L["x0"], L["brand"]["base"] + dy), e["brand"], fb,
                     color, e["brand_size"] * 0.06)
        d.line([(L["rule"][0], L["rule"][1] + dy), (L["rule"][2], L["rule"][1] + dy)],
               fill=(color[0], color[1], color[2], int(color[3] * 0.45)), width=1)
        draw_tracked(d, (L["x0"], L["slogan"]["base"] + dy), e["slogan"], fs,
                     (color[0], color[1], color[2], int(color[3] * 0.86)), 0.8)
        draw_tracked(d, (L["x0"], L["disclosure"]["base"] + dy), e["disclosure"], fd,
                     (color[0], color[1], color[2], int(color[3] * 0.86)), 0.5)


def _alpha_at(t):
    a = 0.0
    for c in S.CARDS:
        if c["t_in"] - 0.001 <= t <= c["t_out"]:
            fade = 0.34
            k = 1.0
            if t < c["t_in"] + fade:
                k = (t - c["t_in"]) / fade
            elif t > c["t_out"] - fade:
                k = (c["t_out"] - t) / fade
            a = max(a, max(0.0, min(1.0, k)))
    e = S.ENDCARD
    if e["t_in"] - 0.001 <= t <= e["t_out"]:
        k = 1.0 if t >= e["t_in"] + 0.45 else (t - e["t_in"]) / 0.45
        a = max(a, max(0.0, min(1.0, k)))
    return a


_mask_cache = {}


def _masks(t):
    """这一帧出现的字，画成两张 alpha 蒙版。同组合只画一次。

    早年逐帧画 + 逐帧高斯模糊，720 帧里多花了三分之一的渲染时间。
    """
    key = tuple(c["id"] for c in S.CARDS if c["t_in"] - 0.001 <= t <= c["t_out"])
    if S.ENDCARD["t_in"] - 0.001 <= t <= S.ENDCARD["t_out"]:
        key = key + ("END",)
    if key in _mask_cache:
        return _mask_cache[key]
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _draw_all(ImageDraw.Draw(shadow), t, (0, 0, 0, 158), dy=4)
    shadow = shadow.filter(ImageFilter.GaussianBlur(7))
    top = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _draw_all(ImageDraw.Draw(top), t, (255, 255, 255, 246), dy=0)
    out = (np.asarray(top)[..., 3:4].astype(np.float32) / 255.0,
           np.asarray(shadow)[..., 3:4].astype(np.float32) / 255.0)
    _mask_cache[key] = out
    return out


def render_cards(t):
    """返回 (文字 alpha, 阴影 alpha)，都已乘上这一帧的淡入淡出。"""
    a = _alpha_at(t)
    top, shadow = _masks(t)
    return top * a, shadow * a



# ------------------------------------------------------------------ 单帧
_plate_cache = {}


def plate(name):
    if name not in _plate_cache:
        _plate_cache[name] = Image.open(PLATES / f"{name}.png").convert("RGB")
    return _plate_cache[name]


def render_frame(fi):
    t = fi / float(FPS)
    act = shots_at(t)
    if len(act) == 1:
        sh, k, _ = act[0]
        img = crop_window(plate(sh["shot"]["plate"]), sh["shot"]["move"], k)
        arr = np.asarray(img).astype(np.float32) / 255.0
    else:
        (a, ka, wa), (b, kb, wb) = act
        ia = crop_window(plate(a["shot"]["plate"]), a["shot"]["move"], ka)
        ib = crop_window(plate(b["shot"]["plate"]), b["shot"]["move"], kb)
        arr = (np.asarray(ia).astype(np.float32) / 255.0) * wa + \
              (np.asarray(ib).astype(np.float32) / 255.0) * wb

    warm, contrast, expo = grade_params(t)
    # 调色（在 0..1 空间里做，最后统一乘回去）
    arr[..., 0] *= 1.0 + 0.10 * warm
    arr[..., 1] *= 1.0 + 0.015 * warm
    arr[..., 2] *= 1.0 - 0.12 * warm
    if expo:
        arr *= 2.0 ** expo
    arr = (arr - 0.42) * contrast + 0.42
    luma = arr[..., 0] * 0.2126 + arr[..., 1] * 0.7152 + arr[..., 2] * 0.0722
    arr += (luma[..., None] - arr) * 0.06
    arr *= vignette()
    np.clip(arr, 0.0, 1.0, out=arr)

    ov = set()
    for sh, _, _ in act:
        ov.update(sh["shot"]["ov"])

    if "snow" in ov:
        sl = snow_layers()
        add(arr, scroll(sl[0], t * 190, t * 520)[..., None] * 0.55, 0.14)
        add(arr, scroll(sl[1], -t * 120, t * 760)[..., None] * 0.70, 0.17)
        add(arr, scroll(sl[2], t * 60, t * 1150)[..., None] * 0.90, 0.20)
    if "flare" in ov:
        fl = flare_field()
        pulse = 0.85 + 0.15 * math.sin(t * 2.2)
        arr += fl * 0.42 * pulse * np.array([1.0, 0.92, 0.80], dtype=np.float32)
    if "spark" in ov:
        add(arr, scroll(snow_layers()[1], t * 40, -t * 60)[..., None] * 0.6, 0.05)
    if "mist" in ov:
        m = mist_field()
        arr += m * 0.055
        arr += np.roll(m, int(t * 26), axis=1) * 0.035
    if "film" in ov:
        yy = np.arange(H, dtype=np.float32) / H
        band = np.exp(-((yy[None, :] - (0.35 + 0.30 * t / 18.6)) ** 2) * 40.0)
        arr += np.asarray(band, dtype=np.float32).T[..., None] * 0.045
    if "thread" in ov:
        draw_thread(arr, t, 1.0)
    if "spray" in ov:
        draw_spray(arr, t, 0.50, 0.60, 0.85)
    if "bloom" in ov:
        bloom(arr, 0.30, 0.62)
    if "endcard" in ov:
        arr *= 0.26
        arr += np.array([0.004, 0.006, 0.008], dtype=np.float32)
    if "grain" in ov:
        gt = grain_tiles()[fi % 10]
        arr += (gt[..., None] / 255.0)

    np.clip(arr, 0.0, 1.0, out=arr)

    # 文字：只在有字的帧上合成
    has_text = any(c["t_in"] - 0.001 <= t <= c["t_out"] for c in S.CARDS) or \
        (S.ENDCARD["t_in"] - 0.001 <= t <= S.ENDCARD["t_out"])
    if has_text:
        # 底部压暗：字压在亮水上也要读得出来（S03、S06 都踩过）
        yy = np.arange(H, dtype=np.float32) / H
        scrim = np.clip((yy - 0.58) / 0.42, 0, 1) ** 1.5
        arr *= (1.0 - 0.30 * scrim)[:, None, None]
        ta, sa = render_cards(t)
        arr *= (1.0 - sa * 0.92)          # 黑影（纯黑乘性压暗，比加法干净）
        arr = arr * (1.0 - ta) + ta       # 白字

    return np.clip(arr * 255.0 + 0.5, 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ 主程序
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="f0", type=int, default=0)
    ap.add_argument("--to", dest="f1", type=int, default=None)
    ap.add_argument("--out", default="build/seg0.mp4")
    ap.add_argument("--crf", default="20")
    ap.add_argument("--preset", default="veryfast")
    ap.add_argument("--no-encode", action="store_true")
    ap.add_argument("--frame", type=int, default=None, help="只渲一帧到 PNG，调试用")
    a = ap.parse_args()

    if a.frame is not None:
        arr = render_frame(a.frame)
        Image.fromarray(arr, "RGB").save(a.out)
        print("frame", a.frame, "->", a.out)
        return

    f0 = a.f0
    f1 = frames_total() if a.f1 is None else a.f1
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [FFMPEG, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-",
           "-an", "-c:v", "libx264", "-preset", a.preset, "-crf", str(a.crf),
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-g", str(FPS * 2),
           str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for fi in range(f0, f1):
            p.stdin.write(render_frame(fi).tobytes())
            if (fi - f0) % 60 == 0:
                print(f"  frame {fi}/{f1}", flush=True)
    finally:
        p.stdin.close()
        rc = p.wait()
    if rc != 0:
        raise SystemExit(f"ffmpeg failed: {rc}")
    print(f"wrote {out}  frames {f0}..{f1}  ({(f1 - f0) / FPS:.2f}s)")


if __name__ == "__main__":
    main()
