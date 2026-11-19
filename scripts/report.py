# -*- coding: utf-8 -*-
"""从 story.py 反向生成分镜表与字幕表，避免文档和片子对不上。

    python scripts/report.py            # 写 docs/_storyboard.md
    python scripts/report.py --check    # 只比对，不一致退出 1
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import story as S  # noqa: E402

OUT = ROOT / "docs" / "_storyboard.md"

HEAD = """<!-- 由 scripts/report.py 从 story.py 生成；不要手改，改 story.py 再跑一次 -->

## 镜头表

| # | 时间 | 秒 | 图版 | 运镜 | 叠加 | 这一镜在做什么 |
| --- | --- | --- | --- | --- | --- | --- |
"""

TAIL = """
## 字幕卡

| 卡 | 出现 | 停留 | 位置 | 字号 | 文案 | 出处 |
| --- | --- | --- | --- | --- | --- | --- |
"""


def build():
    lines = [HEAD]
    for sh in S.SHOTS:
        mv = sh["move"]
        move = "%s %.2f→%.2f，中心 (%.2f,%.2f)→(%.2f,%.2f)" % (
            mv[6], mv[0], mv[1], mv[2], mv[3], mv[4], mv[5])
        lines.append("| %s | %.2f–%.2f | %.2f | `%s` | %s | %s | %s |\n" % (
            sh["id"], sh["start"], sh["end"], sh["end"] - sh["start"],
            sh["plate"], move, "、".join(sh["ov"]), sh["note"]))
    lines.append(TAIL)
    for c in S.CARDS:
        lines.append("| %s | %.2f s | %.2f s | %s | %d px | %s | %s |\n" % (
            c["id"], c["t_in"], c["t_out"] - c["t_in"], c["place"], c["size"],
            c["text"], c["source"]))
    e = S.ENDCARD
    lines.append("| END | %.2f s | %.2f s | 左下三行 | %d / %d / %d px | %s ｜ %s ｜ %s | 品牌公开页 |\n" % (
        e["t_in"], e["t_out"] - e["t_in"], e["brand_size"], e["slogan_size"],
        e["disclosure_size"], e["brand"], e["slogan"], e["disclosure"]))
    lines.append("\n合计 %.3f 秒，%d 帧 @ %d fps，%dx%d。\n" % (
        S.FILM_SEC, int(round(S.FILM_SEC * S.FPS)), S.FPS, S.W, S.H))
    return "".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    txt = build()
    if a.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != txt:
            print("docs/_storyboard.md 与 story.py 不一致：跑 python scripts/report.py")
            return 1
        print("storyboard in sync")
        return 0
    OUT.write_text(txt, encoding="utf-8")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
