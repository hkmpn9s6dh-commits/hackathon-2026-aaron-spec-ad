# 三十年前的雪 / THIRTY YEARS

农夫山泉 · 长白雪的 30 秒 spec 广告。投稿 **AARON Awards 2027 · 08 Best Speculative Ad**。

> **你喝到的，是三十年前的雪。**

一句话说完这支片子：农夫山泉八年来的水广告都在**山的外面**拍——雪、鹿、森林、四季；
没有人拍过**山的里面**那三十年。这支片子是一次**不可能被拍到的连续下坠**：
雪花落在玄武岩上化开 → 顺着岩缝进山 → 在岩层里走三十年 → 从泉眼涌出 → 进到瓶子里。
这段路任何摄影机都进不去，只有生成式影像能拍。

- 成片：`out/thirty-years.mp4`（30.000 s / 1920×1080 / 24 fps / H.264 + AAC / −16 LUFS）
- 说明页：`site/index.html`（线上见仓库 Pages）
- 分镜与字幕：`docs/02-CREATIVE.md`（由 `story.py` 反向生成，不允许手改）

## 一条命令重建

```bash
python scripts/plates.py        # raw 图版 → 去水印 / 裁 16:9 / 调色 / 放大
python scripts/audio.py         # 合成声轨（无采样素材）
python scripts/render.py --from 0 --to 240 --out build/seg0.mp4
python scripts/render.py --from 240 --to 480 --out build/seg1.mp4
python scripts/render.py --from 480 --to 720 --out build/seg2.mp4
python scripts/assemble.py      # 拼接 + 混流 + 写 out/manifest.json
python scripts/verify.py        # 73 条断言
```

或一条：

```bash
bash verify.sh                  # 建片 + 全部断言；--no-build 只验现有成片
```

依赖：Python 3.8+（numpy、Pillow）、ffmpeg（含 ffprobe）。不需要联网、不需要 npm。

## 为什么分成三段渲染

单进程 ~0.9 s/帧，720 帧一次跑会超过本机单条命令的时间上限，也会把内存吃满。
三段各自写自己的 mp4，最后用 concat 拼接——**绝不让两个 ffmpeg 碰同一个文件**
（会静默损坏，判据是抽帧 0/0）。

## 目录

| 路径 | 是什么 |
| --- | --- |
| `story.py` | 唯一事实来源：镜头、文案、调色曲线、音效事件 |
| `plates/` | 六张图版（`raw/` 是生成原图，`manifest.json` 存 sha256） |
| `scripts/` | 图版处理、逐帧渲染、声轨合成、拼接、断言、分镜反向生成 |
| `docs/` | 任务、赛事原文、创作、管线、材料出处、提交文案、复盘、UI |
| `proof/` | 断言输出、关键帧、盲读记录 |
| `site/` | 说明页（Pages） |
| `out/` | 成片、声轨、manifest（不进 Git） |

## 素材与披露

六张图版由生成式模型出图；运镜、粒子、调色、字幕、声轨由 `scripts/` 里的代码生成。
片尾标注「水源地影像为 AI 生成示意」。完整披露与 credits 见 `docs/05-SUBMISSION.md`。
