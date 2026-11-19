# -*- coding: utf-8 -*-
"""《三十年前的雪》/ THIRTY YEARS —— 唯一事实来源。

片子的一切都从这里长出来：镜头表、文案、字幕时序、音效、调色。
改片子只改这一个文件；docs/02-CREATIVE.md 的镜头表由 scripts/report.py 反向生成并 --check。

为什么是单源：AME-1435 改了时长忘了重生成分镜表，只有在全新 clone 里才被抓到。
"""

TITLE_ZH = "三十年前的雪"
TITLE_EN = "THIRTY YEARS"

FPS = 24
W, H = 1920, 1080

# 片长（秒）。这是 AARON Best Speculative Ad 的投稿版：30 秒硬切在 30.000。
FILM_SEC = 30.0

# 品牌与产品（用的是品牌公开页面上的真实说法，见 docs/04-SOURCES.md）
BRAND = "农夫山泉"
PRODUCT = "长白雪"
PRODUCT_FULL = "农夫山泉 · 长白雪"
SLOGAN = "我们不生产水，我们只是大自然的搬运工"
DISCLOSURE = "水源地影像为 AI 生成示意"

# ---------------------------------------------------------------- 镜头表
# plate:  plates/<name>.png（2400x1350，已去水印、已调色）
# move:   (z0, z1, cx0, cy0, cx1, cy1, ease)
#         z 是放大倍数（1.0 = 整幅），(cx,cy) 是取窗中心，归一化坐标（0..1）
#         ease: "linear" | "in" | "out" | "inout"
#
# 全片的运镜统一向下：观众看到的是**同一次下落**，剪辑点只是加速度，不是场景切换。
SHOTS = [
    dict(
        id="S01", plate="snowfield", start=0.00, end=3.60,
        move=(1.04, 1.16, 0.50, 0.30, 0.52, 0.44, "inout"),
        ov=["snow", "flare", "grain"],
        note="长白山西坡。风把雪横着吹过来，太阳压在脊线上。",
    ),
    dict(
        id="S02", plate="snow-crystal", start=3.60, end=7.20,
        move=(1.00, 1.46, 0.50, 0.52, 0.51, 0.56, "in"),
        ov=["grain", "spark"],
        note="一片雪落在玄武岩上。边缘化开，成一颗水珠。",
    ),
    dict(
        id="S03", plate="fissure", start=7.20, end=12.20,
        move=(1.02, 1.30, 0.50, 0.18, 0.50, 0.66, "inout"),
        ov=["mist", "grain", "drip"],
        note="岩缝里。玄武岩柱往上抽，水贴着石壁往下走。全片唯一一处天光。",
    ),
    dict(
        id="S04", plate="rock-film", start=12.20, end=18.60,
        move=(1.08, 1.22, 0.38, 0.50, 0.62, 0.52, "inout"),
        ov=["film", "thread", "grain"],
        note="岩层里。水在看不见的裂隙里走。一年，两米。",
    ),
    dict(
        id="S05", plate="spring", start=18.60, end=23.40,
        move=(1.02, 1.24, 0.50, 0.42, 0.50, 0.50, "out"),
        ov=["spray", "grain"],
        note="泉眼。水从岩壁里涌出来，落到地下水池。",
    ),
    dict(
        id="S06", plate="bottle", start=23.40, end=27.40,
        move=(1.10, 1.02, 0.50, 0.48, 0.50, 0.52, "out"),
        ov=["grain", "bloom"],
        note="水出了山。瓶身挂着冷凝水，晨光从瓶子里穿过去。",
    ),
    dict(
        id="S07", plate="bottle", start=27.40, end=30.00,
        move=(1.02, 1.02, 0.50, 0.52, 0.50, 0.52, "linear"),
        ov=["endcard"],
        note="末屏。品牌、产品、口号、AI 标注。",
    ),
]

# 叠化：下一个镜头提前多少秒进来。硬切不放这里。
XFADE = {
    ("S03", "S04"): 0.25,
    ("S04", "S05"): 0.25,
    ("S05", "S06"): 0.30,
    ("S06", "S07"): 0.40,
}

# ---------------------------------------------------------------- 文案
# 每张卡：给谁看的一句话。attribution 写清依据，verify.py 会要求非空。
CARDS = [
    dict(id="C1", shot="S02", t_in=4.35, t_out=6.95, text="长白山西坡",
         size=54, place="lower-left", source="品牌官网：长白山西坡自涌冷泉"),
    dict(id="C2", shot="S03", t_in=8.10, t_out=11.85, text="距天池六十公里",
         size=54, place="lower-left", source="品牌官网：距天池 60 公里内"),
    dict(id="C3", shot="S04", t_in=13.20, t_out=17.90, text="三十到六十年",
         size=60, place="lower-left", source="品牌官网：约 30-60 年火山玄武岩深层溶滤"),
    dict(id="C4", shot="S05", t_in=19.60, t_out=23.10, text="恒温七度",
         size=54, place="lower-left", source="品牌官网：恒温约 7℃"),
    dict(id="C5", shot="S06", t_in=25.20, t_out=27.20, text="你喝到的，是三十年前的雪。",
         size=58, place="center-low", source="本片主张（原创）"),
]

ENDCARD = dict(
    t_in=27.60, t_out=30.00,
    brand=PRODUCT_FULL,
    brand_size=72,
    slogan=SLOGAN,
    slogan_size=32,
    disclosure=DISCLOSURE,
    disclosure_size=20,
)

# 品牌色（末屏与字幕取色都从这里来）
INK = (255, 255, 255)
INK_DIM = (255, 255, 255, 0.62)
RULE = (255, 255, 255, 0.30)

# ---------------------------------------------------------------- 调色
# 一条从冷到暖再回到冷的色温曲线：时间在画面里是**颜色**，不是字幕。
# t(秒) -> (暖度 -1..1, 对比 0.8..1.2, 曝光 -0.3..0.3)
GRADE = [
    (0.0, -0.55, 1.10, 0.02),
    (3.6, -0.45, 1.12, 0.00),
    (7.2, -0.62, 1.08, -0.14),
    (12.2, -0.48, 1.14, -0.52),
    (17.8, -0.40, 1.14, -0.48),
    (18.8, 0.02, 1.04, -0.18),
    (23.4, 0.30, 1.00, 0.06),
    (27.4, 0.18, 1.06, 0.00),
    (30.0, 0.10, 1.10, -0.04),
]

# ---------------------------------------------------------------- 声音
# 逐段的音效事件。所有声音都是合成的（numpy），没有采样素材。
AUDIO_CUES = [
    dict(t=0.0, kind="wind", dur=4.2, level=0.55),
    dict(t=0.2, kind="pad", dur=30.0, level=0.30, note="全片低频底噪，一根弦"),
    dict(t=3.55, kind="icecrack", level=0.42),
    dict(t=4.6, kind="shimmer", dur=2.4, level=0.10),
    dict(t=7.20, kind="sub", dur=5.0, level=0.34, note="进山：下潜"),
    dict(t=7.5, kind="drip", level=0.22), dict(t=9.1, kind="drip", level=0.16),
    dict(t=10.4, kind="drip", level=0.20), dict(t=11.6, kind="drip", level=0.14),
    dict(t=12.3, kind="pulse", dur=6.2, level=0.26, note="时间：心跳一样慢"),
    dict(t=12.4, kind="film", dur=6.0, level=0.12),
    dict(t=18.55, kind="spring", dur=4.4, level=0.46),
    dict(t=23.45, kind="pour", dur=2.2, level=0.40),
    dict(t=24.4, kind="bell", level=0.24),
    dict(t=27.5, kind="endtone", dur=2.5, level=0.30),
]

# 响度目标（AARON 是线上评审，按网络投放口径）
LOUDNESS_LUFS = -16.0
TRUE_PEAK_DBTP = -3.0
