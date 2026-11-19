# -*- coding: utf-8 -*-
"""生成投稿用的支撑视觉：六张关键帧、3:2 作品图、工作流图。

    python scripts/submission.py

产出都在 submission/ 下，全部可从成片与 story.py 重建。
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import story as S  # noqa: E402
import render as R  # noqa: E402
from ff import FFMPEG  # noqa: E402

SUB = ROOT / "submission"
FILM = ROOT / "out" / "thirty-years.mp4"
SERIF = "C:/Windows/Fonts/NotoSerifSC-VF.ttf"
SANS = "C:/Windows/Fonts/NotoSansSC-VF.ttf"

PICKS = [
    ("01-snowfield", 1.60, "长白山西坡"),
    ("02-snowflake", 5.60, "一片雪落在玄武岩上"),
    ("03-fissure", 9.80, "岩缝：全片唯一一处天光"),
    ("04-thirty-years", 15.60, "岩层里：水走三十年"),
    ("05-spring", 21.40, "泉眼"),
    ("06-bottle", 26.20, "你喝到的，是三十年前的雪"),
]


def grab(t):
    p = subprocess.run([FFMPEG, "-v", "error", "-ss", "%.3f" % t, "-i", str(FILM),
                        "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True)
    if p.returncode != 0:
        raise SystemExit("grab failed at %.2f" % t)
    import io
    return Image.open(io.BytesIO(p.stdout)).convert("RGB")


def stills():
    d = SUB / "stills"
    d.mkdir(parents=True, exist_ok=True)
    for name, t, cap in PICKS:
        im = grab(t)
        im.save(d / ("%s.jpg" % name), quality=92)
        print("  still", name, "%.2fs" % t)


def keyart():
    """3:2 作品图：瓶身 + 主张 + 品牌，一眼能读。"""
    base = grab(24.80).resize((1500, 844), Image.LANCZOS)
    canvas = Image.new("RGB", (1500, 1000), (11, 12, 13))
    canvas.paste(base, (0, 0))
    # 底部渐黑
    a = Image.new("L", (1500, 340), 0)
    ad = ImageDraw.Draw(a)
    for y in range(340):
        ad.line([(0, y), (1500, y)], fill=int(255 * (y / 339.0) ** 1.4))
    black = Image.new("RGB", (1500, 340), (0, 0, 0))
    canvas.paste(black, (0, 660), a)

    d = ImageDraw.Draw(canvas)
    f1 = ImageFont.truetype(SERIF, 62)
    f2 = ImageFont.truetype(SANS, 30)
    f3 = ImageFont.truetype(SANS, 22)
    d.text((90, 792), "你喝到的，是三十年前的雪。", font=f1, fill=(255, 255, 255))
    d.line([(90, 862), (610, 862)], fill=(255, 255, 255, 90), width=1)
    d.text((90, 884), "农夫山泉 · 长白雪　｜　AARON Awards 2027 · Best Speculative Ad",
           font=f2, fill=(210, 214, 218))
    d.text((90, 934), "水源地影像为 AI 生成示意", font=f3, fill=(150, 156, 162))
    canvas.save(SUB / "keyart.png")
    print("  keyart 1500x1000")


def pipeline():
    W, H = 2000, 1180
    im = Image.new("RGB", (W, H), (14, 15, 17))
    d = ImageDraw.Draw(im)
    ft = ImageFont.truetype(SERIF, 46)
    fs = ImageFont.truetype(SANS, 25)
    fm = ImageFont.truetype(SANS, 21)
    fname = ImageFont.truetype(SANS, 23)
    white = (238, 240, 242)
    dim = (150, 156, 164)
    box = (28, 30, 36)
    edge = (74, 82, 92)
    accent = (108, 176, 208)

    d.text((70, 54), "How the film was made", font=ft, fill=white)
    d.text((70, 116), "One image plate per shot · one timeline · all parameters in a single file",
           font=fm, fill=dim)

    def bx(x, y, w, h, title, lines, accent_edge=False):
        d.rounded_rectangle([x, y, x + w, y + h], 12, fill=box,
                            outline=accent if accent_edge else edge, width=2)
        d.text((x + 20, y + 14), title, font=fname, fill=white)
        yy = y + 50
        for ln in lines:
            d.text((x + 20, yy), ln, font=fm, fill=dim)
            yy += 29

    def arrow(x0, y0, x1, y1):
        d.line([(x0, y0), (x1, y1)], fill=edge, width=3)
        import math
        ang = math.atan2(y1 - y0, x1 - x0)
        for s in (0.5, -0.5):
            d.line([(x1, y1), (x1 - 16 * math.cos(ang - s), y1 - 16 * math.sin(ang - s))],
                   fill=edge, width=3)

    bx(70, 200, 330, 150, "story.py", [
        "shots / cards / grade / sound cues",
        "single source of truth"], True)
    bx(70, 400, 330, 170, "plates.py", [
        "de-watermark", "crop 16:9 · grade", "→ 2400 × 1350"])
    bx(470, 400, 330, 170, "render.py", [
        "camera move + overlays", "text masks", "→ rgb24 frame stream"])
    bx(870, 400, 330, 170, "audio.py", [
        "wind / water / sub / bell", "numpy synthesis", "→ 48 kHz stereo wav"])
    bx(1270, 400, 330, 170, "ffmpeg", [
        "x264 veryfast · CRF 21", "3 segments (memory)", "→ seg0/1/2.mp4"])
    bx(870, 660, 330, 150, "assemble.py", [
        "concat + mux", "→ thirty-years.mp4"])
    bx(470, 660, 330, 150, "verify.py", [
        "73 assertions", "exit 1 on any failure"])
    bx(70, 660, 330, 150, "report.py", [
        "storyboard generated", "from story.py (--check)"])
    bx(1270, 660, 330, 150, "site / submission", [
        "reviewer page (Pages)", "stills · keyart · diagram"])

    arrow(235, 350, 235, 400)
    arrow(400, 485, 470, 485)
    arrow(1200, 485, 1270, 485)
    arrow(1435, 570, 1435, 640)
    arrow(1270, 700, 1200, 700)
    arrow(1035, 570, 1035, 660)

    d.text((70, 900), "Gate B: assertions were written before the renderer — the first run failed 7 of 68.",
           font=fs, fill=white)
    d.text((70, 940), "Every number in the case write-up comes from scripts/verify.py, not from the storyboard.",
           font=fs, fill=dim)
    d.text((70, 1000), "Reproducible: same frame renders to identical bytes; plates pinned by sha256 in plates/manifest.json.",
           font=fs, fill=dim)
    d.text((70, 1060), "30.000 s · 1920×1080 · 24 fps · −16 LUFS · no stock footage · no samples",
           font=fs, fill=accent)
    im.save(SUB / "pipeline.png")
    print("  pipeline 2000x1180")


def main():
    SUB.mkdir(exist_ok=True)
    print("[stills]")
    stills()
    print("[keyart]")
    keyart()
    print("[pipeline]")
    pipeline()
    print("done")


if __name__ == "__main__":
    main()
