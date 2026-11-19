#!/usr/bin/env bash
# 一条命令：建片 + 全部断言。
#   bash verify.sh                # 重建图版/声轨/画面，再验
#   bash verify.sh --no-build     # 只验现有成片
set -euo pipefail
cd "$(dirname "$0")"

PY=python
command -v python >/dev/null 2>&1 || PY=py
BUILD=1
[ "${1:-}" = "--no-build" ] && BUILD=0

if [ "$BUILD" = "1" ]; then
  echo "== 1/5 图版 =="
  $PY scripts/plates.py
  echo "== 2/5 声轨 =="
  $PY scripts/audio.py
  echo "== 3/5 画面（三段，逐段独立进程）=="
  $PY scripts/render.py --from 0   --to 240 --out build/seg0.mp4 --crf 21
  $PY scripts/render.py --from 240 --to 480 --out build/seg1.mp4 --crf 21
  $PY scripts/render.py --from 480 --to 720 --out build/seg2.mp4 --crf 21
  echo "== 4/5 拼接与混流 =="
  $PY scripts/assemble.py
fi

echo "== 5/5 断言 =="
$PY scripts/report.py --check
$PY scripts/verify.py

# 投稿视觉与说明页
if [ "$BUILD" = "1" ]; then
  $PY scripts/submission.py
  $PY scripts/site.py
fi

echo "OK"
