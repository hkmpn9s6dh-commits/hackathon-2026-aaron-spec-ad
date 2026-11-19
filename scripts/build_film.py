# -*- coding: utf-8 -*-
"""一条命令把片子从素材建到成片。

    python scripts/build_film.py                 # 全流程
    python scripts/build_film.py --skip-plates --skip-audio   # 只重渲画面
    python scripts/build_film.py --jobs 4 --crf 17

为什么分段并行：单进程约 0.5 s/帧，720 帧要六分钟；四路压到两分内。
每段写自己的文件，绝不让两个 ffmpeg 碰同一个 mp4（中枢教训：会静默损坏）。
中间产物不带 -movflags +faststart（这台机器末尾重写 moov 会写坏 mp4）。
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
OUT = ROOT / "out"
PY = sys.executable
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import story as S  # noqa: E402
from ff import FFMPEG  # noqa: E402


def run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd), flush=True)
    r = subprocess.run([str(c) for c in cmd], **kw)
    if r.returncode != 0:
        raise SystemExit("failed: %s (exit %d)" % (cmd[0], r.returncode))


def total_frames():
    return int(round(S.FILM_SEC * S.FPS))


def split(n, parts):
    step = (n + parts - 1) // parts
    return [(i, min(i + step, n)) for i in range(0, n, step)]


def sha(p):
    h = hashlib.sha256()
    h.update(Path(p).read_bytes())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-plates", action="store_true")
    ap.add_argument("--skip-audio", action="store_true")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--crf", default="17")
    ap.add_argument("--keep-segs", action="store_true")
    a = ap.parse_args()

    BUILD.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)

    if not a.skip_plates:
        print("[1/5] 图版处理", flush=True)
        run([PY, "scripts/plates.py"])

    if not a.skip_audio:
        print("[2/5] 声轨合成", flush=True)
        run([PY, "scripts/audio.py"])

    n = total_frames()
    segs = split(n, a.jobs)
    print("[3/5] 渲染 %d 帧（%d fps，%.2fs）分 %d 段、%d 路并行"
          % (n, S.FPS, n / S.FPS, len(segs), len(segs)), flush=True)

    t0 = time.time()
    procs = []
    for i, (f0, f1) in enumerate(segs):
        out = BUILD / ("seg%d.mp4" % i)
        cmd = [PY, "scripts/render.py", "--from", str(f0), "--to", str(f1),
               "--out", str(out.relative_to(ROOT)), "--crf", a.crf]
        procs.append((subprocess.Popen(cmd, cwd=str(ROOT)), out))
    for p, out in procs:
        if p.wait() != 0:
            raise SystemExit("render failed: %s" % out)
    print("  渲染完成 %.1fs" % (time.time() - t0), flush=True)

    print("[4/5] 拼接", flush=True)
    lst = BUILD / "segs.txt"
    lst.write_text("".join("file '%s'\n" % (BUILD / ("seg%d.mp4" % i)).as_posix()
                           for i in range(len(segs))), encoding="utf-8")
    silent = BUILD / "silent.mp4"
    run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(silent)])

    print("[5/5] 混流", flush=True)
    final = OUT / "thirty-years.mp4"
    run([FFMPEG, "-y", "-loglevel", "error",
         "-i", str(silent), "-i", str(OUT / "audio.wav"),
         "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-shortest", "-movflags", "+faststart", str(final)])

    if not a.keep_segs:
        for i in range(len(segs)):
            (BUILD / ("seg%d.mp4" % i)).unlink(missing_ok=True)

    man = dict(
        film=str(final.relative_to(ROOT)),
        duration_sec=S.FILM_SEC,
        frames=n,
        fps=S.FPS,
        size=[S.W, S.H],
        sha256=sha(final),
        bytes=final.stat().st_size,
        plates=(ROOT / "plates" / "manifest.json").read_text(encoding="utf-8"),
        built_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    (OUT / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    print("wrote", final, "%.1f MB" % (final.stat().st_size / 1e6))


if __name__ == "__main__":
    main()
