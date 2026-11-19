# -*- coding: utf-8 -*-
"""把三段画面拼起来、混上声轨、写 manifest。

    python scripts/assemble.py            # 默认 build/seg0..2.mp4 + out/audio.wav
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import story as S  # noqa: E402
from ff import FFMPEG  # noqa: E402


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg failed: " + r.stderr[-600:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segs", default="build/seg0.mp4,build/seg1.mp4,build/seg2.mp4")
    ap.add_argument("--audio", default="out/audio.wav")
    ap.add_argument("--out", default="out/thirty-years.mp4")
    a = ap.parse_args()

    segs = [ROOT / x for x in a.segs.split(",")]
    for s in segs:
        if not s.exists():
            raise SystemExit("missing segment: %s" % s)

    lst = ROOT / "build" / "segs.txt"
    # ffmpeg 是 Windows 程序，清单里必须写 Windows 路径
    lst.write_text("".join("file '%s'\n" % s.as_posix().replace("/c/", "C:/")
                           for s in segs), encoding="utf-8")
    silent = ROOT / "build" / "silent.mp4"
    run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(silent)])

    final = ROOT / a.out
    final.parent.mkdir(exist_ok=True)
    run([FFMPEG, "-y", "-loglevel", "error",
         "-i", str(silent), "-i", str(ROOT / a.audio),
         "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-shortest", "-movflags", "+faststart", str(final)])

    h = hashlib.sha256(final.read_bytes()).hexdigest()
    man = dict(
        film=str(final.relative_to(ROOT)).replace("\\", "/"),
        seconds=S.FILM_SEC, frames=int(round(S.FILM_SEC * S.FPS)),
        fps=S.FPS, size=[S.W, S.H], sha256=h, bytes=final.stat().st_size,
        plates=json.loads((ROOT / "plates" / "manifest.json").read_text(encoding="utf-8")),
        built_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    (ROOT / "out" / "manifest.json").write_text(
        json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote %s  %.1f MB  sha256=%s" % (final, final.stat().st_size / 1e6, h[:16]))


if __name__ == "__main__":
    main()
