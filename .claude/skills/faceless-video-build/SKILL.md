---
name: faceless-video-build
description: >
  Produce the finished Resilient Soul video from an approved script: ElevenLabs narration with
  word timestamps, one generated/licensed visual per scene, an ElevenLabs music bed, a 16:9
  ffmpeg render with slow Ken Burns motion, soft fades and word-timed captions, ducked music at
  −14 LUFS, then video-qa, a thumbnail, chapters and the review canvas. Use for "make the
  video", "narrate it", "render it", "generate the visuals", "add music", or a revision of a
  rendered version. Not for writing the script (narration-script) or editing camera footage
  (video-edit-pipeline).
---

# faceless-video-build — script → finished MP4

Uses the same tools as the rest of this pack: ElevenLabs (voice + `sound-design` music),
ffmpeg/ffprobe, the image/clip generators (`openart-broll`, `arcads-broll`, or the connected
ElevenLabs / Canva / vidIQ image tools), `video-qa`, `video-review-canvas`, `naming-convention`.

All commands run from this repo; `<p>` is the project folder.

## Gate: learning applied

Before anything paid, `evolution/learn.py apply <p> <application.json>` must bind `script.md`,
`thumbnail-plan.md`, `packaging.md`, `scenes.json` (frames) and production input
`visuals/prompts.md`; then `learn.py verify <p>`. `soul.py narrate` and `soul.py render`
refuse an unbound `scenes.json`. Narration writes measured timings into `scenes.json`, so
**re-run apply + verify after narration** (the workflow expects this) before the final render.

## 1 · Voice (ElevenLabs — costs characters)

- Voice: `channel.json → voice.voice_id`. If it is null, pick one with the user: list voices
  (ElevenLabs MCP `creative_list_voices`, or the ElevenLabs voice library) matching
  `voice.description`, play two candidates on the hook paragraph, save the choice in
  `channel.json`. Keep the same voice across videos — it is the channel's identity.
- Estimate, get approval, then generate:

```bash
python3 tools/soul/soul.py narrate <p>/scenes.json --dry-run        # characters + scene count
python3 tools/soul/soul.py narrate <p>/scenes.json --yes            # after the user approves
```

One `with-timestamps` request per scene (previous/next text passed for natural continuity),
saved as `audio/scene-NNN.mp3` + `.align.json`. Existing scenes are skipped; edit a paragraph
and only that scene regenerates. Listen to the first two scenes before trusting the rest:
pronunciation of Greek/Latin names (Epictetus, Zeno, *eudaimonia*) — respell in the script
if needed.

## 2 · Visuals — one per scene

`soul.py visuals plan <p>/scenes.json` writes `visuals/prompts.md`: each scene's prompt +
`channel.json → visual_style`, its narration and on-screen seconds. Produce
`visuals/scene-NNN.png|jpg|mp4` (16:9, ≥ 1920×1080):

- Stills: generate with the image tool available (openart-broll / arcads-broll Nano Banana,
  ElevenLabs `creative_generate_image`, Canva `generate-image`). Stills get slow alternating
  zoom-in/zoom-out, so one strong composition per scene is enough.
- Motion: for chapter openers and the hook, a 5–10 s generated clip (Veo/Kling/Seedance via
  openart-broll or arcads-broll) — clips loop to fill the scene, so prefer seamless motion
  (rain, waves, clouds, candle flame).
- Licensed stock (Pixabay etc.) is fine — record the source URL in `visuals/SOURCES.md`.
  Never competitor footage, never real people's likenesses, no text in images.
- State per-image/clip cost before a batch. Re-run `visuals plan` to see what is missing.
- Look at every visual before render (contact sheet): consistent palette, no warped hands or
  faces, no stray text/watermarks.

## 3 · Music bed (ElevenLabs — costs credits)

```bash
node .claude/skills/sound-design/scripts/gen-music.mjs --prompt "<channel.json music_prompt>" \
  --seconds 120 --out <p>/music/bed.mp3
```

A 2-minute bed loops under the whole video (fades out over the last 4 s). Render ducks it under
the voice (sidechain) at `music_db` (−24 dB) and masters to −14 LUFS / −1.5 dBTP.

## 4 · Render

```bash
python3 tools/soul/soul.py render <p>/scenes.json --draft    # placeholders allowed, fast preset, no learning gate
python3 tools/soul/soul.py render <p>/scenes.json            # final: render/<slug>-vN.mp4 (never overwrites)
```

Per scene: visual with motion + 0.5 s fade in/out, word-timed caption chunks (≤ 6 words, lower
band, Pillow-rendered — no libass needed), narration padded by the scene/chapter gap. Scenes
are concatenated, music mixed, loudness normalised. `--no-captions` for a clean version,
`--size 1280x720` for a quick check.

## 5 · QA — verify the rendered file

```bash
npm --prefix tools/video-qa run qa:video -- --video <p>/render/<slug>-vN.mp4
```

Then look yourself: extract a frame per chapter start and a few caption moments, check the
captions don't cover the subject, the voice/music balance in dB, and that the duration matches
`scenes.json.total_seconds`. Compare against the learning brief and the thumbnail plan; record
differences in the QA notes.

## 6 · Packaging

```bash
python3 tools/soul/soul.py chapters <p>/scenes.json --upload <p>/upload.json
python3 tools/soul/soul.py thumbnail --image <p>/visuals/<best>.png --text "<≤5 words>" -o <p>/thumbnail.png
```

Optionally score/refine with `vidiq_score_thumbnail` / `vidiq_generate_thumbnail` (credits).
`upload.json` = chosen title, description with chapters, tags, hashtags. Uploading is the
user's call — never publish automatically.

## 7 · Deliver and revise

Publish the render on `video-review-canvas` (reply leads with the URL). Notes → fix the script
paragraph, visual or mix → regenerate only what changed → new version file → same canvas slug.
Run `soul.py status <p>` any time to see the next step.
