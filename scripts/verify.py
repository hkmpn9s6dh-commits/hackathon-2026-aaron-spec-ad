# -*- coding: utf-8 -*-
"""闸 B 的断言。先写在这里，再让片子去满足它。

    python scripts/verify.py            # 全跑，失败即退出 1
    python scripts/verify.py --only=A   # 只跑某一组

分七组：
  A 容器规格（ffprobe 读出来的，不按分镜表算）
  B 响度
  C 文字安全区与时序
  D 文字真的出现在该出现的地方（逐帧取像素）
  E 末屏三件（品牌、口号、AI 标注）
  F 全片没有脸、没有死黑开场
  G 可复现（同帧两次渲染逐字节相同）
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import story as S  # noqa: E402
import render as R  # noqa: E402
from ff import FFMPEG, FFPROBE  # noqa: E402

FILM = ROOT / "out" / "thirty-years.mp4"
RESULTS = []


def chk(group, name, ok, detail=""):
    RESULTS.append((group, name, bool(ok), detail))
    print("  [%s] %-52s %s  %s" % (group, name, "PASS" if ok else "FAIL", detail))


def probe(path):
    p = subprocess.run([FFPROBE, "-v", "error", "-print_format", "json",
                        "-show_format", "-show_streams", str(path)],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit("ffprobe failed: " + p.stderr[-400:])
    return json.loads(p.stdout)


def frame_at(t):
    p = subprocess.run([FFMPEG, "-v", "error", "-ss", "%.3f" % t, "-i", str(FILM),
                        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True)
    if p.returncode != 0 or len(p.stdout) < S.W * S.H * 3:
        raise SystemExit("frame extract failed at %.2f" % t)
    return np.frombuffer(p.stdout[:S.W * S.H * 3], dtype=np.uint8).reshape(S.H, S.W, 3)


# ------------------------------------------------------------------ A 容器
def group_a():
    info = probe(FILM)
    v = [s for s in info["streams"] if s["codec_type"] == "video"][0]
    a = [s for s in info["streams"] if s["codec_type"] == "audio"][0]
    dur = float(info["format"]["duration"])
    chk("A", "时长 = 30.000 ±0.05 s", abs(dur - S.FILM_SEC) <= 0.05, "%.3f" % dur)
    chk("A", "画幅 1920x1080", v["width"] == S.W and v["height"] == S.H,
        "%dx%d" % (v["width"], v["height"]))
    chk("A", "帧率 24/1", v["r_frame_rate"] == "24/1", v["r_frame_rate"])
    chk("A", "编码 h264 High / yuv420p",
        v["codec_name"] == "h264" and v.get("profile") == "High" and
        v.get("pix_fmt") == "yuv420p",
        "%s %s %s" % (v["codec_name"], v.get("profile"), v.get("pix_fmt")))
    chk("A", "帧数 = 720", int(v.get("nb_frames", 0)) == 720, v.get("nb_frames", "?"))
    chk("A", "音轨 aac 48000 2ch",
        a["codec_name"] == "aac" and int(a["sample_rate"]) == 48000 and int(a["channels"]) == 2,
        "%s %s %s" % (a["codec_name"], a["sample_rate"], a["channels"]))
    chk("A", "码率 6–20 Mbps", 6e6 <= float(info["format"]["bit_rate"]) <= 20e6,
        "%.1f Mbps" % (float(info["format"]["bit_rate"]) / 1e6))
    chk("A", "文件 > 10 MB", FILM.stat().st_size > 10e6, "%.1f MB" % (FILM.stat().st_size / 1e6))
    # 分镜表自己加起来必须是 30.0
    total = R.LAYOUT[-1]["end"] - R.LAYOUT[0]["start"]
    chk("A", "时间轴覆盖 = 30.000 s", abs(total - S.FILM_SEC) < 1e-6, "%.4f" % total)


# ------------------------------------------------------------------ B 响度
def group_b():
    p = subprocess.run([FFMPEG, "-hide_banner", "-i", str(FILM),
                        "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    txt = p.stderr
    m_i = re.findall(r"I:\s+(-?\d+\.\d+) LUFS", txt)
    m_tp = re.findall(r"Peak:\s+(-?\d+\.\d+) dBFS", txt)
    i = float(m_i[-1]) if m_i else -99
    tp = float(m_tp[-1]) if m_tp else 0
    chk("B", "整体响度 -16.0 ±0.5 LUFS", abs(i - S.LOUDNESS_LUFS) <= 0.5, "%.1f" % i)
    chk("B", "真峰 ≤ -1.0 dBTP", tp <= -1.0, "%.1f" % tp)
    chk("B", "有声（不是静音）", i > -30, "%.1f LUFS" % i)


# ------------------------------------------------------------------ C 文字
def group_c():
    safe = (0.05 * S.W, 0.05 * S.H, 0.95 * S.W, 0.95 * S.H)
    worst = 0
    for c in S.CARDS:
        L = R.card_layout(c)
        inside = L["x0"] >= safe[0] and L["x1"] <= safe[2] and L["y0"] >= safe[1] and L["y1"] <= safe[3]
        chk("C", "安全区 %s「%s」" % (c["id"], c["text"][:8]),
            inside, "box=(%d,%d,%d,%d)" % (L["x0"], L["y0"], L["x1"], L["y1"]))
        dur = c["t_out"] - c["t_in"]
        chk("C", "停留 ≥ 2.0 s %s" % c["id"], dur >= 2.0, "%.2f s" % dur)
        # 必须落在它所属镜头的区间里
        sh = [x for x in S.SHOTS if x["id"] == c["shot"]][0]
        chk("C", "落在镜头 %s 内 %s" % (c["shot"], c["id"]),
            c["t_in"] >= sh["start"] - 1e-6 and c["t_out"] <= sh["end"] + 1e-6,
            "%.2f–%.2f vs %.2f–%.2f" % (c["t_in"], c["t_out"], sh["start"], sh["end"]))
        chk("C", "文案有出处 %s" % c["id"], bool(c.get("source")))
        worst = max(worst, L["x1"] / S.W)
    # 不重叠
    cards = sorted(S.CARDS, key=lambda x: x["t_in"])
    ok = all(cards[i]["t_out"] <= cards[i + 1]["t_in"] for i in range(len(cards) - 1))
    chk("C", "卡片之间不重叠", ok)
    # 末屏
    L = R.endcard_layout()
    for k in ("brand", "slogan", "disclosure"):
        b = L[k]["box"]
        chk("C", "末屏 %s 在安全区内" % k,
            b[0] >= safe[0] and b[2] <= safe[2] and b[1] >= safe[1] and b[3] <= safe[3],
            "box=%s" % (b,))


# ------------------------------------------------------------------ D 文字真的在
def text_contrast(t, box):
    a = frame_at(t).astype(np.float32) / 255.0
    x0, y0, x1, y1 = box
    reg = a[y0:y1, x0:x1]
    if reg.size == 0:
        return 0.0, 0.0
    lum = reg @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    # 字是白的：取最亮 2% 与最暗 40% 的均值比
    hi = np.percentile(lum, 99.5)
    lo = np.percentile(lum, 40)
    ratio = (hi + 0.05) / (lo + 0.05)
    bright_px = int((lum > 0.72).sum())
    return float(ratio), bright_px


def group_d():
    for c in S.CARDS:
        t = (c["t_in"] + c["t_out"]) / 2.0
        L = R.card_layout(c)
        ratio, bright = text_contrast(t, (L["x0"], L["y0"], L["x1"], L["y1"]))
        chk("D", "字可见 %s（对比≥3.0，亮像素≥300）" % c["id"],
            ratio >= 3.0 and bright >= 300, "ratio=%.1f bright=%d" % (ratio, bright))


# ------------------------------------------------------------------ E 末屏
def group_e():
    L = R.endcard_layout()
    t = 29.2
    # 亮像素的门槛按字号给：19–20px 的标注笔画只有 2px 宽，撑不到大字的量
    need = dict(brand=400, slogan=200, disclosure=40)
    for k in ("brand", "slogan", "disclosure"):
        ratio, bright = text_contrast(t, L[k]["box"])
        chk("E", "末屏 %s 可见" % k, ratio >= 2.2 and bright >= need[k],
            "ratio=%.1f bright=%d (need %d)" % (ratio, bright, need[k]))
    chk("E", "末屏有品牌全称", S.PRODUCT_FULL == "农夫山泉 · 长白雪", S.PRODUCT_FULL)
    chk("E", "末屏有 AI 标注", "AI" in S.DISCLOSURE, S.DISCLOSURE)
    chk("E", "末屏有品牌口号", bool(S.SLOGAN))


# ------------------------------------------------------------------ F 脸 / 死黑
def skin_ratio(a):
    """粗判：R 明显高于 G/B 且亮度在肤色区间的像素占比。"""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    # 收得比"暖色"更窄：还要绿也明显高于蓝、亮度落在皮肤区间
    m = (r > 0.30) & (r < 0.95) & (r > g * 1.30) & (r > b * 1.50) &         (g > b * 1.02) & (g > 0.14) & (g < 0.78)
    return float(m.mean())


def group_f():
    times = [1, 5, 9, 13, 17, 21, 25, 28, 29.5]
    worst = 0.0
    for t in times:
        r = skin_ratio(frame_at(t).astype(np.float32) / 255.0)
        worst = max(worst, r)
        chk("F", "无人物面部 t=%.1fs（肤色像素 <1.0%%）" % t, r < 0.010, "%.4f" % r)
    # 开场不能是死黑（赛道 N 的教训：暗开场被读成没加载）
    lum0 = float((frame_at(0.15).astype(np.float32) / 255.0).mean())
    chk("F", "开场 0.15s 不是死黑（平均亮度 ≥0.06）", lum0 >= 0.06, "%.3f" % lum0)
    dark = 0
    for i in range(24):
        l = float((frame_at(i / 24.0).astype(np.float32) / 255.0).mean())
        dark = dark + 1 if l < 0.02 else 0
        if dark >= 3:
            break
    chk("F", "开场没有连续 3 帧全黑", dark < 3, "连续暗帧=%d" % dark)


# ------------------------------------------------------------------ G 可复现
def group_g():
    a = R.render_frame(360)
    b = R.render_frame(360)
    chk("G", "同帧两次渲染逐字节相同", a.tobytes() == b.tobytes(),
        hashlib.sha256(a.tobytes()).hexdigest()[:16])
    c = R.render_frame(361)
    chk("G", "相邻帧不同（不是静帧幻灯片）", a.tobytes() != c.tobytes())
    # 图版清单与文件一致
    man = json.loads((ROOT / "plates" / "manifest.json").read_text(encoding="utf-8"))
    ok = True
    for name, m in man.items():
        f = ROOT / "plates" / ("%s.png" % name)
        if not f.exists():
            ok = False
            break
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        if h != m["plate_sha256"]:
            ok = False
            break
    chk("G", "六张图版与 manifest 的 sha256 一致", ok)
    used = {s["plate"] for s in S.SHOTS}
    chk("G", "分镜用到的图版都在", all((ROOT / "plates" / ("%s.png" % n)).exists() for n in used))
    # 水印框已盖住：角落块的边缘能量不能高于左边同一块太多
    for name in man:
        im = np.asarray(Image.open(ROOT / "plates" / ("%s.png" % name)).convert("L"))
        h, w = im.shape
        x1, y1 = int(w * 0.97), int(h * 0.97)
        x0, y0 = x1 - int(w * 0.06), y1 - int(h * 0.07)
        here = im[y0:y1, x0:x1].astype(np.float32)
        ref = im[y0:y1, x0 - (x1 - x0):x0].astype(np.float32)
        eh = np.abs(np.diff(here, axis=1)).mean()
        er = np.abs(np.diff(ref, axis=1)).mean()
        # 字形边缘会到十几；石头纹理在 3 以下。两个条件取其一即可
        chk("G", "无水印残留 %s" % name, eh < 3.0 or eh < er * 1.6 + 0.6,
            "edge %.1f vs %.1f" % (eh, er))


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    groups = dict(A=group_a, B=group_b, C=group_c, D=group_d, E=group_e, F=group_f, G=group_g)
    for k in "ABCDEFG":
        if a.only and k not in a.only:
            continue
        print("[%s]" % k, flush=True)
        groups[k]()
    fails = [r for r in RESULTS if not r[2]]
    print("\n合计 %d 条，失败 %d 条" % (len(RESULTS), len(fails)))
    if fails:
        for g, n, _, d in fails:
            print("  FAIL [%s] %s %s" % (g, n, d))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
