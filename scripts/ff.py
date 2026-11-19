# -*- coding: utf-8 -*-
"""找到 ffmpeg / ffprobe。Git Bash 的 PATH 里有 shim，Windows 的 CreateProcess 认不到。"""
import os
import shutil
from pathlib import Path

CANDIDATES = [
    r"C:\Users\张一\AppData\Local\Microsoft\WinGet\Packages"
    r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin",
    r"C:\Program Files\ffmpeg\bin",
    r"C:\ffmpeg\bin",
]


def _find(name):
    p = shutil.which(name)
    if p and os.path.isfile(p):
        return p
    for d in CANDIDATES:
        q = Path(d) / (name + ".exe")
        if q.exists():
            return str(q)
    raise SystemExit(f"找不到 {name}：改 scripts/ff.py 里的 CANDIDATES")


FFMPEG = _find("ffmpeg")
FFPROBE = _find("ffprobe")
