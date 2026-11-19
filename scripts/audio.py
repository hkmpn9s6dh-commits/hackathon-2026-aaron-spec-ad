# -*- coding: utf-8 -*-
"""合成《三十年前的雪》的声轨。

没有采样素材：风、水、冰裂、低频、钟声全部由 numpy 合成，
混响用一段指数衰减的噪声做 IR。最后按网络投放口径归一响度。

用法：
    python scripts/audio.py            # 写 out/audio.wav（48k / 16bit / 立体声 / 30.000s）
"""
import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import story as S  # noqa: E402
from ff import FFMPEG, FFPROBE  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SR = 48000
DUR = S.FILM_SEC
N = int(round(DUR * SR))
rng = np.random.default_rng(20261119)


# ------------------------------------------------------------------ 基础件
def t_axis(n):
    return np.arange(n, dtype=np.float32) / SR


def fade(x, a=0.01, b=0.05):
    n = len(x)
    na, nb = max(1, int(a * SR)), max(1, int(b * SR))
    w = np.ones(n, dtype=np.float32)
    w[:na] = np.linspace(0, 1, na) ** 2
    w[-nb:] = np.linspace(1, 0, nb) ** 2
    return x * w


def noise(n):
    return rng.normal(0, 1, n).astype(np.float32)


def fft_filter(x, lo=None, hi=None, order=4):
    """频域带通。比手写 IIR 快，也够干净。"""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR).astype(np.float32)
    m = np.ones_like(f)
    if lo:
        m *= 1.0 / (1.0 + (lo / np.maximum(f, 1.0)) ** order)
    if hi:
        m *= 1.0 / (1.0 + (f / hi) ** order)
    return np.fft.irfft(X * m, n=n).astype(np.float32)


def sweep_filter(x, bands, order=4):
    """分段带通再交叉淡化：给"音色随时间变化"用。"""
    n = len(x)
    out = np.zeros(n, dtype=np.float32)
    seg = max(1, n // len(bands))
    win = np.ones(n, dtype=np.float32)
    for i, (lo, hi) in enumerate(bands):
        y = fft_filter(x, lo, hi, order)
        a, b = i * seg, min(n, (i + 1) * seg)
        w = np.ones(n, dtype=np.float32)
        w[:a] = 0
        w[b:] = 0
        edge = max(1, seg // 3)
        if a > 0:
            w[a:a + edge] = np.linspace(0, 1, min(edge, n - a))
        if b < n:
            w[b:b + edge] = np.linspace(1, 0, min(edge, n - b))
        out += y * w
    return out * win


def env_exp(n, attack=0.005, decay=0.3):
    t = t_axis(n)
    e = np.exp(-t / max(1e-4, decay))
    na = max(1, int(attack * SR))
    e[:na] *= np.linspace(0, 1, na)
    return e.astype(np.float32)


# ------------------------------------------------------------------ 乐器/音效
def wind(dur, level):
    n = int(dur * SR)
    l = fft_filter(noise(n), 90, 900, 3)
    r = fft_filter(noise(n), 90, 900, 3)
    t = t_axis(n)
    lfo = 0.55 + 0.45 * np.sin(2 * np.pi * 0.13 * t + 0.6) * np.sin(2 * np.pi * 0.07 * t)
    g = lfo * np.exp(-t / (dur * 0.9))
    g[:int(0.4 * SR)] *= np.linspace(0, 1, int(0.4 * SR))
    return np.stack([l * g, r * g]) * level


def pad(dur, level):
    n = int(dur * SR)
    t = t_axis(n)
    out = np.zeros((2, n), dtype=np.float32)
    base = [55.0, 82.5, 110.0, 164.81]
    for i, f0 in enumerate(base):
        vib = 1.0 + 0.0015 * np.sin(2 * np.pi * (0.07 + 0.013 * i) * t)
        ph = 2 * np.pi * f0 * np.cumsum(vib) / SR
        amp = 0.5 / (1 + i * 0.7)
        for ch in (0, 1):
            d = 1.0 + (0.0006 if ch else -0.0006) * i
            out[ch] += (np.sin(ph * d).astype(np.float32) * amp)
    # 一点噪声垫底，让低频有"空气"
    bed = fft_filter(noise(n), 40, 300, 3) * 0.06
    out[0] += bed
    out[1] += np.roll(bed, 733)
    e = np.minimum(1.0, t / 3.0) * np.minimum(1.0, (dur - t) / 4.0)
    return out * e.astype(np.float32) * level


def icecrack(level):
    n = int(0.5 * SR)
    t = t_axis(n)
    body = fft_filter(noise(n), 1200, 9000, 3) * env_exp(n, 0.002, 0.05)
    ring = np.zeros(n, dtype=np.float32)
    for f, a in [(1850, 0.5), (2680, 0.34), (3900, 0.2)]:
        ring += (np.sin(2 * np.pi * f * t) * np.exp(-t / 0.12) * a).astype(np.float32)
    x = body * 1.2 + ring * 0.5
    return np.stack([x, np.roll(x, 97)]) * level


def shimmer(dur, level):
    n = int(dur * SR)
    t = t_axis(n)
    x = np.zeros(n, dtype=np.float32)
    for f, a in [(2360, 0.4), (3140, 0.3), (4210, 0.22), (5300, 0.12)]:
        trem = 0.6 + 0.4 * np.sin(2 * np.pi * (3.1 + f / 4000) * t + f)
        x += (np.sin(2 * np.pi * f * t + 0.3) * trem * a).astype(np.float32)
    e = np.minimum(1.0, t / 0.6) * np.exp(-t / (dur * 0.7))
    return np.stack([x * e, np.roll(x * e, 311)]) * level * 0.5


def sub(dur, level):
    n = int(dur * SR)
    t = t_axis(n)
    f = 64.0 * np.exp(-t / (dur * 0.55)) + 24.0
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph).astype(np.float32)
    rum = fft_filter(noise(n), 25, 120, 3) * 0.5
    e = np.minimum(1.0, t / 0.35) * np.exp(-t / (dur * 0.8))
    y = (x * 0.8 + rum) * e
    return np.stack([y, y]) * level


def drip(level):
    n = int(1.2 * SR)
    t = t_axis(n)
    f0 = float(rng.uniform(900, 1500))
    x = np.sin(2 * np.pi * f0 * t * (1.0 - 0.25 * t / 0.3)).astype(np.float32) * np.exp(-t / 0.055)
    click = fft_filter(noise(n), 2000, 9000, 3) * np.exp(-t / 0.008) * 0.4
    y = fade(x + click, 0.001, 0.05)
    return np.stack([y, np.roll(y, 211)]) * level


def pulse(dur, level):
    n = int(dur * SR)
    t = t_axis(n)
    out = np.zeros(n, dtype=np.float32)
    k = 0
    while k * 1.15 < dur:
        s = int(k * 1.15 * SR)
        m = min(n - s, int(0.5 * SR))
        if m <= 0:
            break
        tt = t_axis(m)
        thump = np.sin(2 * np.pi * 46.0 * tt) * np.exp(-tt / 0.16)
        thump += fft_filter(noise(m), 60, 240, 3) * np.exp(-tt / 0.09) * 0.35
        out[s:s + m] += thump.astype(np.float32)
        k += 1
    e = np.minimum(1.0, t / 0.5) * np.minimum(1.0, (dur - t) / 0.5)
    return np.stack([out * e, out * e]) * level


def film(dur, level):
    n = int(dur * SR)
    t = t_axis(n)
    x = fft_filter(noise(n), 700, 2600, 3)
    ticks = np.zeros(n, dtype=np.float32)
    for _ in range(int(dur * 9)):
        s = int(rng.uniform(0, dur - 0.05) * SR)
        m = int(0.03 * SR)
        tt = t_axis(m)
        ticks[s:s + m] += (np.sin(2 * np.pi * rng.uniform(2400, 5200) * tt) *
                           np.exp(-tt / 0.004)).astype(np.float32) * rng.uniform(0.2, 0.8)
    y = (x * 0.35 + ticks * 0.5)
    e = np.minimum(1.0, t / 0.8) * np.minimum(1.0, (dur - t) / 0.8)
    return np.stack([y * e, np.roll(y * e, 421)]) * level


def spring(dur, level):
    n = int(dur * SR)
    t = t_axis(n)
    src = noise(n)
    y = sweep_filter(src, [(250, 900), (400, 1800), (600, 3200), (500, 2200)], 3)
    bubbles = np.zeros(n, dtype=np.float32)
    for _ in range(int(dur * 22)):
        s = int(rng.uniform(0, dur - 0.1) * SR)
        m = int(0.05 * SR)
        tt = t_axis(m)
        f = float(rng.uniform(500, 1900))
        bubbles[s:s + m] += (np.sin(2 * np.pi * f * tt) *
                             np.exp(-tt / 0.012)).astype(np.float32) * rng.uniform(0.15, 0.5)
    e = np.minimum(1.0, t / 0.25) * np.minimum(1.0, (dur - t) / 0.9)
    y = (y * 0.9 + bubbles) * e
    return np.stack([y, np.roll(y, 157)]) * level


def pour(dur, level):
    n = int(dur * SR)
    t = t_axis(n)
    x = sweep_filter(noise(n), [(900, 5000), (500, 2600), (300, 1500)], 3)
    gurgle = 0.55 + 0.45 * np.sin(2 * np.pi * 9.0 * t + np.sin(2 * np.pi * 1.7 * t))
    e = np.minimum(1.0, t / 0.12) * np.exp(-t / (dur * 0.8))
    y = x * gurgle * e
    return np.stack([y, np.roll(y, 263)]) * level


def bell(level):
    n = int(3.0 * SR)
    t = t_axis(n)
    x = np.zeros(n, dtype=np.float32)
    for f, a, d in [(880, 0.5, 1.6), (1320, 0.26, 1.1), (1976, 0.14, 0.7), (2640, 0.08, 0.5)]:
        x += (np.sin(2 * np.pi * f * t) * np.exp(-t / d) * a).astype(np.float32)
    return np.stack([x, np.roll(x, 173)]) * level


def endtone(dur, level):
    n = int(dur * SR)
    t = t_axis(n)
    x = np.zeros(n, dtype=np.float32)
    for f, a in [(55.0, 0.6), (82.5, 0.35), (110.0, 0.22), (164.8, 0.10)]:
        x += (np.sin(2 * np.pi * f * t) * a).astype(np.float32)
    e = np.minimum(1.0, t / 1.0) * np.minimum(1.0, (dur - t) / 0.8)
    return np.stack([x * e, np.roll(x * e, 401)]) * level


# ------------------------------------------------------------------ 混响
def make_ir(sec=2.0, decay=0.62):
    n = int(sec * SR)
    t = t_axis(n)
    ir = np.zeros((2, n), dtype=np.float32)
    for ch in (0, 1):
        k = rng.normal(0, 1, n).astype(np.float32)
        k *= np.exp(-t / decay)
        k[:int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))
        ir[ch] = k / np.sqrt((k ** 2).sum())
    return ir


def convolve(x, ir):
    n = len(x) + len(ir) - 1
    nf = 1 << (n - 1).bit_length()
    X = np.fft.rfft(x, nf)
    H = np.fft.rfft(ir, nf)
    y = np.fft.irfft(X * H, nf)[:len(x)]
    return y.astype(np.float32)


# ------------------------------------------------------------------ 装配
def build():
    dry = np.zeros((2, N), dtype=np.float32)
    send = np.zeros((2, N), dtype=np.float32)

    def put(x, at, snd=0.0, gain=1.0):
        s = int(round(at * SR))
        if s >= N:
            return
        m = min(x.shape[1], N - s)
        dry[:, s:s + m] += x[:, :m] * gain
        if snd:
            send[:, s:s + m] += x[:, :m] * gain * snd

    for cue in S.AUDIO_CUES:
        k = cue["kind"]
        d = cue.get("dur", 1.0)
        lv = cue["level"]
        if k == "wind":
            put(wind(d, lv), cue["t"])
        elif k == "pad":
            put(pad(d, lv), cue["t"], 0.35)
        elif k == "icecrack":
            put(icecrack(lv), cue["t"], 0.55)
        elif k == "shimmer":
            put(shimmer(d, lv), cue["t"], 0.7)
        elif k == "sub":
            put(sub(d, lv), cue["t"], 0.25)
        elif k == "drip":
            put(drip(lv), cue["t"], 0.85)
        elif k == "pulse":
            put(pulse(d, lv), cue["t"], 0.2)
        elif k == "film":
            put(film(d, lv), cue["t"], 0.4)
        elif k == "spring":
            put(spring(d, lv), cue["t"], 0.45)
        elif k == "pour":
            put(pour(d, lv), cue["t"], 0.35)
        elif k == "bell":
            put(bell(lv), cue["t"], 0.8)
        elif k == "endtone":
            put(endtone(d, lv), cue["t"], 0.3)
        else:
            raise SystemExit("unknown cue: " + k)

    wet = np.stack([convolve(send[0], make_ir()[0]), convolve(send[1], make_ir()[1])])
    mix = dry + wet * 0.55

    # 全片动态：开场轻 → 进山下潜 → 岩层里最静 → 泉眼涨起来 → 末屏收干净。
    # 不做这条包络，pad 会把每一段都压成同一个响度，30 秒就没有起伏了。
    curve = [(0.0, 1.00), (3.6, 0.95), (5.0, 0.80), (7.2, 1.18), (12.2, 0.74),
             (13.2, 0.58), (18.0, 0.58), (18.7, 1.16), (22.4, 1.00),
             (23.4, 0.84), (27.3, 0.60), (28.6, 0.72), (30.0, 0.48)]
    tt = np.arange(N, dtype=np.float32) / SR
    g = np.ones(N, dtype=np.float32)
    for i in range(len(curve) - 1):
        t0, v0 = curve[i]
        t1, v1 = curve[i + 1]
        m = (tt >= t0) & (tt <= t1)
        k = (tt[m] - t0) / max(1e-6, (t1 - t0))
        k = k * k * (3 - 2 * k)
        g[m] = v0 + (v1 - v0) * k
    g[tt < curve[0][0]] = curve[0][1]
    g[tt > curve[-1][0]] = curve[-1][1]
    mix *= g

    # 尾部收干净：最后 0.4 秒淡出
    tail = int(0.4 * SR)
    mix[:, -tail:] *= np.linspace(1, 0, tail) ** 1.5

    # 软限幅
    mix = np.tanh(mix * 1.25) / 1.25
    mix = mix / max(1e-6, np.abs(mix).max()) * 0.89
    return mix


def write_wav(path, mix):
    import wave
    pcm = np.clip(mix.T * 32767.0, -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def loudnorm(src, dst):
    """两遍 loudnorm：先量，再按量到的值归一到目标。"""
    def measure(path):
        p = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path),
                            "-af", "loudnorm=I=%s:TP=%s:print_format=json" %
                            (S.LOUDNESS_LUFS, S.TRUE_PEAK_DBTP),
                            "-f", "null", "-"], capture_output=True, text=True)
        txt = p.stderr
        i = txt.rfind("{")
        import json
        return json.loads(txt[i:txt.rfind("}") + 1])

    m = measure(src)
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(src),
                    "-af", "loudnorm=I=%s:TP=%s:LRA=11:measured_I=%s:measured_TP=%s:"
                           "measured_LRA=%s:measured_thresh=%s:offset=%s" % (
                               S.LOUDNESS_LUFS, S.TRUE_PEAK_DBTP,
                               m["input_i"], m["input_tp"], m["input_lra"],
                               m["input_thresh"], m["target_offset"]),
                    "-ar", str(SR), "-ac", "2", str(dst)], check=True)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/audio.wav")
    a = ap.parse_args()
    (ROOT / "out").mkdir(exist_ok=True)
    raw = ROOT / "out" / "_bed.wav"
    mix = build()
    write_wav(raw, mix)
    m = loudnorm(raw, ROOT / a.out)
    print("bed:", m["input_i"], "LUFS ->", S.LOUDNESS_LUFS)
    print("wrote", ROOT / a.out)


if __name__ == "__main__":
    main()
