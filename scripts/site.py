# -*- coding: utf-8 -*-
"""生成说明页 site/index.html（GitHub Pages 用）。

    python scripts/site.py
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import story as S  # noqa: E402

SITE = ROOT / "site"
SUB = ROOT / "submission"


def main():
    (SITE / "media").mkdir(parents=True, exist_ok=True)
    for src, dst in [
        (ROOT / "out" / "thirty-years.mp4", SITE / "media" / "thirty-years.mp4"),
        (SUB / "keyart.png", SITE / "media" / "keyart.png"),
        (SUB / "pipeline.png", SITE / "media" / "pipeline.png"),
    ]:
        if src.exists():
            shutil.copyfile(src, dst)
    for f in sorted((SUB / "stills").glob("*.jpg")):
        shutil.copyfile(f, SITE / "media" / f.name)

    man = {}
    if (ROOT / "out" / "manifest.json").exists():
        man = json.loads((ROOT / "out" / "manifest.json").read_text(encoding="utf-8"))

    stills = [("01-snowfield.jpg", "山外", "长白山西坡。风把雪横着吹过来。"),
              ("02-snowflake.jpg", "一片雪", "落在玄武岩上，边缘化开。"),
              ("03-fissure.jpg", "进山", "岩缝里，全片唯一一处天光。"),
              ("04-thirty-years.jpg", "三十年", "水在岩层里走。三十到六十年。"),
              ("05-spring.jpg", "出泉", "从岩壁涌出来，恒温七度。"),
              ("06-bottle.jpg", "上桌", "你喝到的，是三十年前的雪。")]

    cards = "".join(
        '<figure><img src="media/%s" alt="%s" loading="lazy">'
        '<figcaption><b>%s</b>%s</figcaption></figure>' % (f, cap, tag, cap)
        for f, tag, cap in stills)

    html = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>三十年前的雪 — AARON Awards 2027 · Best Speculative Ad</title>
<style>
 :root{--ink:#f2f0ec;--dim:#a7a49e;--bg:#0b0b0c;--line:#2a2a2c}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"Noto Serif SC","Songti SC",serif;line-height:1.85;
  -webkit-font-smoothing:antialiased}
 .wrap{max-width:1080px;margin:0 auto;padding:0 28px}
 header{padding:96px 0 40px}
 .kicker{font-family:"Noto Sans SC",system-ui,sans-serif;font-size:13px;letter-spacing:.28em;
  color:var(--dim);text-transform:uppercase}
 h1{font-size:clamp(38px,6vw,72px);line-height:1.12;margin:22px 0 10px;font-weight:400}
 .en{font-family:"Noto Sans SC",sans-serif;font-size:14px;letter-spacing:.34em;color:var(--dim)}
 .lede{font-size:clamp(18px,2.2vw,24px);margin:34px 0 0;max-width:44ch}
 .lede b{font-weight:400;color:#fff}
 video{width:100%;display:block;background:#000;margin:44px 0 0;border:1px solid var(--line)}
 .meta{display:flex;gap:28px;flex-wrap:wrap;font-family:"Noto Sans SC",sans-serif;
  font-size:13px;color:var(--dim);padding:16px 0 0;border-bottom:1px solid var(--line)}
 section{padding:64px 0;border-bottom:1px solid var(--line)}
 h2{font-size:14px;letter-spacing:.26em;color:var(--dim);font-weight:400;
  font-family:"Noto Sans SC",sans-serif;margin:0 0 28px}
 .facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:26px}
 .facts div{font-size:15px}
 .facts b{display:block;font-size:26px;font-weight:400;margin-bottom:6px}
 .facts span{color:var(--dim);font-family:"Noto Sans SC",sans-serif;font-size:13px}
 .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:22px}
 figure{margin:0}
 figure img{width:100%;display:block;border:1px solid var(--line)}
 figcaption{font-size:13px;color:var(--dim);padding-top:10px;
  font-family:"Noto Sans SC",sans-serif}
 figcaption b{color:var(--ink);font-weight:400;margin-right:10px;letter-spacing:.1em}
 img.plate{width:100%;display:block;border:1px solid var(--line);background:#111}
 ol{padding-left:1.2em} ol li{margin:.4em 0}
 table{width:100%;border-collapse:collapse;font-family:"Noto Sans SC",sans-serif;font-size:14px}
 td,th{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
 th{color:var(--dim);font-weight:400;letter-spacing:.1em;font-size:12px}
 footer{padding:56px 0 96px;color:var(--dim);font-family:"Noto Sans SC",sans-serif;font-size:13px}
 a{color:#cfe3ee}
</style></head><body>
<div class="wrap">
<header>
  <div class="kicker">AARON Awards 2027 · 08 Best Speculative Ad · spec work</div>
  <h1>三十年前的雪</h1>
  <div class="en">THIRTY YEARS</div>
  <p class="lede">农夫山泉卖的不是水，是水源地。它的水广告一直在<b>山的外面</b>拍。
  没有人拍过山的里面那三十年——因为任何摄影机都进不去。<br><br>
  <b>你喝到的，是三十年前的雪。</b></p>
</header>

<video controls playsinline preload="metadata" poster="media/keyart.png">
  <source src="media/thirty-years.mp4" type="video/mp4">
</video>
<div class="meta">
  <span>30.000 s</span><span>1920×1080</span><span>24 fps</span>
  <span>−16 LUFS</span><span>68 assertions</span><span>no stock footage</span>
</div>

<section>
  <h2>THE FACTS THE FILM IS BUILT ON</h2>
  <div class="facts">
    <div><b>西坡</b><span>长白山西坡自涌冷泉</span></div>
    <div><b>60 km</b><span>距天池六十公里内</span></div>
    <div><b>30–60 年</b><span>火山玄武岩深层溶滤</span></div>
    <div><b>7 ℃</b><span>恒温，自己涌出来</span></div>
  </div>
</section>

<section>
  <h2>ONE CONTINUOUS FALL — SEVEN SHOTS, ALL MOVING DOWN</h2>
  <div class="grid">__CARDS__</div>
</section>

<section>
  <h2>HOW IT WAS MADE</h2>
  <img class="plate" src="media/pipeline.png" alt="pipeline diagram">
  <p style="color:var(--dim);font-size:15px;margin-top:22px">
  六张生成式图版，一条时间轴，一套程序化叠加与调色，全部参数集中在一个文件里。
  运镜、雪、雾、水线、水花、颗粒、字幕、声轨都由代码逐帧算出；
  同帧两次渲染逐字节相同，图版的 sha256 钉在 <code>plates/manifest.json</code>。
  </p>
</section>

<section>
  <h2>WHAT WAS CHECKED</h2>
  <table>
    <tr><th>组</th><th>条数</th><th>判据</th></tr>
    <tr><td>A 容器</td><td>9</td><td>30.000 s / 1920×1080 / 24 fps / h264 High / 720 帧 / aac 48k</td></tr>
    <tr><td>B 响度</td><td>3</td><td>−16.0 ±0.5 LUFS；真峰 ≤ −1.0 dBTP</td></tr>
    <tr><td>C 版式</td><td>22</td><td>安全区、停留 ≥2 s、落在所属镜头内、互不重叠、末屏三件</td></tr>
    <tr><td>D 文字</td><td>5</td><td>逐帧取像素：对比 ≥3.0，亮像素 ≥300</td></tr>
    <tr><td>E 末屏</td><td>6</td><td>品牌 / 口号 / AI 标注都有字形像素</td></tr>
    <tr><td>F 无脸</td><td>11</td><td>肤色像素 &lt;1%；开场不死黑</td></tr>
    <tr><td>G 可复现</td><td>12</td><td>逐字节一致、图版 sha256、无水印残留</td></tr>
  </table>
  <p style="color:var(--dim);font-size:15px;margin-top:22px">
  断言写在渲染器之前。第一次跑挂 7 条，逐条改到 0。
  </p>
</section>

<section>
  <h2>CREDITS &amp; DISCLOSURE</h2>
  <table>
    <tr><th>张一</th><td>创意、导演、剪辑、品牌策略</td></tr>
    <tr><th>CB 主驾</th><td>剧本与分镜、生成式图版、渲染管线、声轨合成、断言与举证</td></tr>
    <tr><th>品牌</th><td>农夫山泉 · 长白雪（本片为未受委托的 spec 作品）</td></tr>
  </table>
  <p style="color:var(--dim);font-size:14px;margin-top:18px">
  画面由生成式模型出图、由自写渲染器完成运镜与调色；声轨为 numpy 合成，无采样素材。
  画面中没有任何真人。水源地影像为 AI 生成示意。
  </p>
</section>

<footer>
  仓库 <a href="https://github.com/hkmpn9s6dh-commits/hackathon-2026-aaron-spec-ad">hackathon-2026-aaron-spec-ad</a>
  　·　成片 sha256 <code>__SHA__</code>　·　__DATE__
</footer>
</div></body></html>
"""

    html = (html.replace("__CARDS__", cards)
            .replace("__SHA__", man.get("sha256", "")[:16])
            .replace("__DATE__", "2026-11-19"))
    (SITE / "index.html").write_text(html, encoding="utf-8")
    print("wrote", SITE / "index.html")


if __name__ == "__main__":
    main()
