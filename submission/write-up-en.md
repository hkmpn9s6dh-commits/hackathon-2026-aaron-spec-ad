# Project write-up (English, for the AARON entry form)

## The challenge

Nongfu Spring does not sell water. It sells a water source. For eight years its water films
have been shot **outside the mountain** — snow, deer, forest, four seasons. Viewers remember
"it is clean up there". They do not remember **why this bottle can only come from there**.

What separates Changbai Snow from every other bottled water is a fact no camera can reach:
the water travels **thirty to sixty years** through volcanic basalt before it emerges.
That journey happens inside rock fissures. It has never been filmed, so it has never become
a line of copy.

The brief for this spec film: **turn that impossible journey into thirty seconds.**

## The creative and technical approach

**One proposition: what you drink is snow from thirty years ago.**

The film is a **single continuous fall**. Seven shots, every camera move downward; cuts read as
acceleration, not as scene changes:

snow lands on basalt and melts → the drop enters a fissure → thirty years inside the rock →
the spring pushes out → the bottle.

Four fact cards, all quoting the brand's own published wording (west slope / sixty kilometres from
the caldera lake / thirty to sixty years / a constant seven degrees), then the proposition, then
brand, product, slogan and an AI disclosure.

**Technically this is a reproducible pipeline, not a lucky generation:**

| Layer | Method |
| --- | --- |
| Plates | six generated stills → watermark removal → 16:9 crop → unified grade → 2400×1350 |
| Time | one 30.000 s timeline; dissolves let the next shot enter 0.25–0.40 s early |
| Camera | one crop-window path per shot (zoom + centre + easing), all downward |
| Overlays | snow, mist, flare, water thread, spray, grain — computed per frame, no stock assets |
| Grade | a single colour-temperature curve across the film: cold → colder → warm inside the rock → brightest at the spring → neutral end card |
| Sound | numpy synthesis only: wind, water, sub drop, ice crack, pulse, bell; convolution reverb from a noise IR; two-pass loudnorm to −16 LUFS |
| Assertions | 68 checks: container, loudness, safe area, card timing, end-card elements, no faces, no watermark, byte-identical re-render |

**Why this approach:** the film needs the continuity of **one space**; shot-by-shot video generation
cannot hold the same fissure together. And a pipeline rebuildable with one command is exactly the
kind of workflow AARON treats as work in its own right.

## The results

- 30.000 s / 1920×1080 / 24 fps / H.264 + AAC / −16 LUFS / 41.7 MB
- 68 of 73 assertions pass (`python scripts/verify.py`)
- A fresh clone rebuilds the film from the README alone (`proof/clone-verify.log`)
- One continuous fall; five semantic layers (outside / entering / inside time / emerging / product)
  separated by **colour temperature** rather than by cuts

## Credits

- Zhang Yi — creative, direction, edit, brand strategy
- CB (an AI agent on CodeBuddy / WorkBuddy) — script and storyboard, generated plates,
  render pipeline, sound synthesis, assertions
- Nongfu Spring — brand and product. This is **unsolicited spec work**; no commission,
  no relationship with the brand.

## AI disclosure

The six image plates were produced with a generative image model; camera moves, overlays, grade,
typography and the entire soundtrack were produced by code in this repository (no stock footage,
no audio samples). No human appears on screen. The end card states that the water-source imagery
is AI-generated.
