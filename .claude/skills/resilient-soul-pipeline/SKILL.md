---
name: resilient-soul-pipeline
description: >
  MASTER pipeline for The Resilient Soul YouTube channel (@TheResilientSoul-q6i — Stoic
  philosophy, resilience, emotional healing; faceless narrated long-form). Use for ANY request to
  make a new video for the channel: "make the next video", "new Resilient Soul video", "find a
  topic and make a video", "what should I post next", or to resume one ("continue the video",
  "where are we on the stoic video"). Sequences keyword research → viral blueprint + learning →
  at least 3 titles → user picks → script → narration → visuals → music → render → QA →
  thumbnail/upload metadata → review canvas. Not for editing camera footage (video-edit-pipeline).
---

# resilient-soul-pipeline — keyword to finished video

```
[0] init / resume ─ soul.py status <p>
[1] niche-keyword-research ─ vidIQ: what the niche searches → research/keywords.json
[2] viral-blueprint + learning ─ vidIQ outliers for the primary keyword → viral/*,
        evolution begin → refresh → sync → brief.md
[3] title-ideation ─ ≥ 3 keyword-led titles, vidIQ-scored ─▶ USER CHOOSES ◀─ (hard stop)
[4] narration-script ─ script.md (verified quotes) → scenes.json, thumbnail-plan.md, packaging.md
        evolution apply → verify            ─▶ user OKs the script ◀─
[5] faceless-video-build
      narrate (ElevenLabs, approved spend) → re-apply/verify → visuals → music bed
      → render → video-qa → chapters + thumbnail + upload.json → video-review-canvas
[6] revisions ─ new version files, same canvas slug
```

## Stage 0 — intake / resume

- Read `MASTER_CONTEXT.md` (projects directory, past topics, reviewer habits) and
  `channel/channel.json` (niche, voice, visual style, defaults).
- New video: `python3 tools/soul/soul.py init <projects dir>/<slug>`.
  Existing: `python3 tools/soul/soul.py status <p>` → continue at `next`. Never repeat paid
  research for a resumed project.
- Money map — say it before spending: vidIQ ≈ 5 credits per call (whole run ≈ 80–130 credits:
  keywords 20–30, blueprint ~60, titles 15–25); ElevenLabs narration ≈ the script's character
  count (~7–10k), music bed one generation; image/clip generation per provider.

## Stage 1 — keywords

Run `niche-keyword-research`. Agree a primary keyword with the user (or take the top
recommendation when the user said "you choose").

## Stage 2 — blueprint + learning (required for new videos)

`evolution/learn.py begin <p> --niche 'stoic philosophy resilience' --language en --market US --format long`
(keep the niche string stable across videos so memory accumulates). Then run `viral-blueprint`
with the **primary keyword** as the niche query (`contentType="long"`), saving vidIQ responses
inside the run's evidence directory; `refresh` + `sync`; read `brief.md`. Skip only if the
user opts out for this video.

## Stage 3 — titles (user decision)

Run `title-ideation`: at least three distinct candidates built on the primary keyword and the
blueprint's title patterns, checked and vidIQ-scored. **Stop and let the user choose.** If
the user is away (scheduled run), recommend the top-scored title, record that choice as
provisional in `titles.json`, and still stop before paid narration.

## Stage 4 — script

Run `narration-script`. Clear `verify_quotes` with `the-stoic-library:stoic-sources`. Write
the learning application JSON (see `evolution/SCHEMA.md`): facets → script `script.md`,
thumbnail `thumbnail-plan.md`, hashtags/tags/description `packaging.md`, frames
`scenes.json`; production_inputs `["visuals/prompts.md"]`. `apply` + `verify`. Show the user
the script (or hook + chapter list) and get a go before narration.

## Stage 5 — build

Run `faceless-video-build` end to end. Re-apply + verify after narration retimes
`scenes.json`. Deliver on the review canvas; the reply leads with the URL, then the chosen
title, runtime, chapters and what QA found.

## Rules that hold everywhere

- Media and research stay in the projects directory, never in this repo.
- Originality: blueprint = structure; no copied sentences, titles, thumbnails or footage.
- Truthfulness: real quotes only, no invented studies, no medical claims — this channel talks
  to people in pain; point to professional help when a topic touches crisis (see channel rules
  in MASTER_CONTEXT.md).
- New versions are new files. Uploading to YouTube is the user's action.
- Generic lessons from a production go into the relevant skill; personal details go into
  MASTER_CONTEXT.md; dated notes into SESSION_LOG.md.
