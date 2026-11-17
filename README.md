# The Resilient Soul — video agent

A Claude Code skill pack that makes videos for the YouTube channel
**[The Resilient Soul](https://www.youtube.com/@TheResilientSoul-q6i)** — Stoic philosophy,
resilience and emotional healing, as faceless, narrated long-form videos (8–12 min, 16:9).

It searches YouTube (via vidIQ) for the most-searched keywords in the niche, proposes **at
least three titles** built on them, and — once you choose one — writes the script and
produces the video with the same toolchain as the relationship-blueprint video agent:
ElevenLabs narration and music, generated visuals, ffmpeg rendering, the 4-layer video QA
engine, the review canvas and the evolving-learning workflow.

## The channel pipeline

```
"make the next Resilient Soul video"
        │
        ▼
[1] niche-keyword-research   vidIQ keyword_research (research / questions / rising)
                             → soul.py keywords rank → research/keywords.json  (primary keyword)
        ▼
[2] viral-blueprint          vidIQ outliers + transcripts for that keyword → structure blueprint
    + evolution/learn.py     begin → refresh → sync → brief.md (what is working now)
        ▼
[3] title-ideation           ≥ 3 distinct keyword-led titles, vidIQ-scored, soul.py titles check
                             ──▶ YOU CHOOSE ◀── soul.py titles choose
        ▼
[4] narration-script         script.md (chapters, [visual:] beats, verified Stoic quotes)
                             → soul.py script lint / scenes → thumbnail-plan.md, packaging.md
                             → learn.py apply + verify
        ▼
[5] faceless-video-build     soul.py narrate (ElevenLabs, word timestamps; asks before spending)
                             → visuals per scene (openart/arcads/ElevenLabs/Canva or licensed stock)
                             → sound-design gen-music.mjs bed
                             → soul.py render (Ken Burns, fades, word-timed captions,
                               ducked music, −14 LUFS) → render/<slug>-vN.mp4
                             → video-qa → soul.py chapters + thumbnail → upload.json
                             → video-review-canvas
```

Start a session in this repo and say **"make the next Resilient Soul video"** — the
`resilient-soul-pipeline` skill runs the stages, stops for your title choice and asks before
any paid step. `python3 tools/soul/soul.py status <project>` shows where a project stands.

## Quickstart

1. Clone and open in Claude Code (WSL/Ubuntu, macOS or Linux).
2. `bash scripts/setup.sh --lane sound-design` (Python 3.10+, ffmpeg, Node 20+), plus
   `python3 -m pip install pillow` if the doctor asks for it.
3. Connect the **vidIQ** MCP (`.mcp.json` declares it) and put `ELEVENLABS_API_KEY` in `.env`.
4. Fill `MASTER_CONTEXT.md` (projects directory, past topics, reviewer habits) and set
   `voice.voice_id` in `channel/channel.json` once you've picked the channel's narrator.
5. Run the tests: `python3 -m unittest discover -s tools/soul/tests -v` (offline; renders a
   tiny synthetic video).

## `tools/soul/soul.py`

| Command | What it does |
|---|---|
| `init <p>` / `status <p>` | create the project layout / report done steps and the next one |
| `keywords rank <raw vidIQ responses…> -o keywords.json` | parse vidIQ markdown/JSON keyword tables, rank by vidIQ overall ± demand growth, filter to the channel's niche, separate title-shaped searches |
| `titles check` / `titles choose --pick N` | ≥ 3 titles, keyword present, ≤ 70/100 chars, no near-duplicates; stamps the choice into `titles.json` + `upload.json` |
| `script lint` / `script scenes` | runtime at 140 wpm, hook/chapters/CTA checks, Stoic quotes to verify; split into scenes with visual prompts |
| `narrate --dry-run` / `--yes` | ElevenLabs text-to-speech with timestamps per scene; character estimate first; skips unchanged scenes |
| `visuals plan` | `visuals/prompts.md` — one prompt per scene with the channel's visual style |
| `render [--draft]` | 16:9 render: stills with slow zoom or looped clips, fades, captions, ducked music, loudness master; never overwrites |
| `chapters --upload` / `thumbnail` | YouTube chapters into the description; a 1280×720 text thumbnail |

Channel defaults (voice, wpm, length, palette, music prompt, CTA) live in
`channel/channel.json`.

## The footage-editing pipeline (inherited)

```
footage + (optional) reference reel + brand/site + ratio
        │
        ▼
[0] video-edit-pipeline picks the lane
      talking head + brand ─────────────→ [1]–[7] below
      creator's own reel look ──────────→ reel-recut
      multi-take screen+camera+mic ─────→ arcads-video-edit
      event recap: takes + B-roll ──────→ recap-video
      one long file of many hooks ──────→ hook-splitter (→ hook-variations)
      AI-actor footage that sounds fake → ai-audio-sound-design
        │
        ▼
[1] reel-style-clone ──────────→ STYLE-GUIDE.md (only if a reference exists)
        │
        ▼
[2] branded-ad-edit
      ingest → two crop candidates (zoom vs blur-pad — show both)
      whisper transcript → storyboard from the style guide
      hand-authored composition + karaoke captions + SFX markers
      B-roll: broll-capture (real screens) / openart-broll / arcads-broll (generated)
        │
        ▼
[3] sound-design ──────────────→ ElevenLabs SFX kit + music bed, mixed by math
        │
        ▼
[4] QA loop (video-qa + tools/video-qa)
      hyperframes check → ONE multi-timestamp snapshot → LOOK with vision
      → fix → render MP4 → the engine verifies the RENDERED file (frames + dB + seams)
        │
        ▼
[5] video-review-canvas ───────→ live review URL (reply leads with the link)
        │
        ▼
[6] revision rounds
      read notes → screenshot the exact frame per note → fix
      edl-tighten for pacing → new file per version → republish same slug
      per-note QA table with evidence from the rendered file
      one cut → many variants: hook-variations, then naming-convention
        │
        ▼
[7] (optional) capcut-export ──→ CapCut draft for a human's final pass
```

## Quickstart (footage editing)

1. Clone this repo and open it in Claude Code.
2. Run `bash scripts/setup.sh --demo`. It installs local QA dependencies, creates missing
   config templates and builds a synthetic edit, catalog, QA evidence and versioned review
   page. Requires Python 3.10+, Node.js 20+, ffmpeg/ffprobe; no paid APIs or model downloads.
   **[SETUP.md](SETUP.md)** covers prerequisites, workflow-specific setup and safe skill linking.
3. Fill in your brand, defaults and **projects directory** in `MASTER_CONTEXT.md`
   (where the videos live — default `outputs/`). Configure keys only for workflows you use.
4. Drop your raw footage into the projects directory (or `footage/`) and say:
   **"edit this like `<reference reel>`"** — or just "edit this video". The
   `video-edit-pipeline` skill takes it from there.

## Project and review tools

- **Review canvas v2:** version picker, synchronized comparison, open/resolved notes,
  replies and before/after frame evidence. Shared reviews use append-only here.now records;
  an explicitly local mode supports demos without hosting. Export the complete revision
  ledger as JSON and import it into project state.
- **Storyboard coverage:** `qa:storyboard` checks planned IDs and timed HTML intervals,
  then extracts contact sheets from the actual MP4. Static coverage and visual verification
  are reported separately; see [the QA engine](tools/video-qa/README.md).
- **Resumable projects:** `python3 tools/editor/editor.py project init|status|resume`
  records source identities, stage artifacts, renders, approvals and outstanding notes.
  Changed or missing files invalidate the relevant progress. Explicit configured commands
  can resume one stage at a time.
- **Reusable footage catalog:** `python3 tools/editor/editor.py catalog ingest|search`
  indexes media metadata, thumbnails, local transcripts, selected intervals and past uses.
  Stable content IDs prevent duplicate indexing. See [project tools](tools/editor/README.md)
  for full commands and transcript options.
- **Offline regression suite:** `bash scripts/test.sh --integration` covers production
  failures, project/catalog behavior, setup safety, the review model and a real media demo.
  GitHub Actions runs the same suite on Linux. Paid/live transcription is opt-in.

QA reports include layer coverage; unavailable checks are not labeled a clean pass.
Review instructions and sampling configuration participate in cache identity. The recut
renderer uses bounded lossless batches and one final AAC encode for long cut timelines.
Serve any local review with `python3 scripts/serve-review.py --directory <review-folder>`;
it supports the byte-range requests video players need for frame seeking.

## Using it from your own working repo

Most people keep their videos, queues and brand tooling in a repo of their own. Keep that,
and point it at this pack instead of copying skills into it:

- Link the skills with `bash "<pack>/scripts/setup.sh" --no-install --link-skills "<working-repo>"`.
  Setup computes relative links for the actual directory layout and preserves existing
  paths. A session started in your repo loads the skills; their files stay here.
- Set the projects directory in `MASTER_CONTEXT.md` (and `VIDEO_PROJECTS_DIR` in `.env`)
  to your media folder. Media never moves into this repo.
- Alias the QA engine in your `package.json`:
  `"qa:video": "npm --prefix \"<path to this repo>/tools/video-qa\" run qa:video --"`.
  Relative paths resolve from where you run it; your `.env` is read first.
- Improvements from every real edit go back into the skills here — generic process only.
  Your client names, fees, reviewer preferences and machine paths belong in
  `MASTER_CONTEXT.md`, which never leaves your disk.

## Prerequisites

| Dependency | Why | Install / notes |
|---|---|---|
| Node.js >= 20 | HyperFrames, the QA engine, the scripts | nodejs.org |
| ffmpeg / ffprobe | every probe, extract, crop, mux | `brew install ffmpeg` (or your package manager) — no libass/drawtext needed |
| HyperFrames | composition + rendering engine | `npx hyperframes`; then `npx hyperframes skills update talking-head-recut` (pulls fonts + gsap) |
| whisper (bundled route) | word-level transcription | `npx hyperframes transcribe` manages whisper.cpp models; `whisper-cli` + a ggml model unlocks the VAD-driven cut planners |
| python3 | helper scripts | PIL (`pip install pillow`) for overlays; numpy + scipy for `ai-audio-sound-design` |
| QA engine | `tools/video-qa` | `npm --prefix tools/video-qa install` (tsx, zod, dotenv) |
| ElevenLabs API key (sound generation only) | SFX + music + ambience generation | `ELEVENLABS_API_KEY` in `.env`; local/demo/QA workflows do not require it |
| here-now skill + credentials | canvas review delivery | agent docs at https://here.now/docs (fetch with `User-Agent: claude`); credentials live in `~/.herenow/credentials` |
| `GEMINI_API_KEY` (optional) | video-qa's watch+listen layer (L3) | skip if unset; the other layers still run |
| `OPENAI_API_KEY` (optional) | cloud whisper fallback (QA engine, hook-splitter, arcads-video-edit) | local whisper.cpp is the default |
| Puppeteer (optional) | scripted website screenshots/B-roll (`broll-capture`) | `npm i puppeteer` in the repo; or use a connected browser MCP instead |
| Screen Studio (optional) | high-fidelity real-browser B-roll (`broll-capture` Lane C) | any screen recorder works; Screen Studio + its CLI is the polished path |
| OpenArt MCP (optional) | AI-generated B-roll / talking heads / overlays (`openart-broll`) | connect the OpenArt MCP in your client; verify with `openart_account_get` — no API key |
| Arcads (optional) | generated B-roll (`arcads-broll`) and the `arcads-video-edit` clip lane | `ARCADS_API_KEY` / `ARCADS_BASIC_AUTH` in `.env` + clone [arcads-claude-code](https://github.com/krusemediallc/arcads-claude-code) alongside |
| Swift toolchain (optional) | `hook-variations`' AVFoundation probe (`avtest`) | Xcode command-line tools; built on first use |
| pyJianYingDraft in a venv (optional) | CapCut draft export | only needed for the capcut-export handoff |

External dependencies are documented, not vendored — nothing in this repo ships a copy of
HyperFrames, whisper models, or ffmpeg.

## Skills catalog

| Skill | What it does |
|---|---|
| `video-edit-pipeline` | **Master orchestrator.** Picks the lane and routes any edit request through the full pipeline. Start here. |
| `branded-ad-edit` | Raw talking head → finished branded motion-graphics ad: framing grammar, card-per-line, karaoke captions, ~40 SFX + bed, QA → render → verify. |
| `reel-recut` | The creator's own short-form look from ONE JSON spec: title banner, karaoke captions, callout boxes, silence-cut pacing; raw-cut mode for footage a client's editor finishes. |
| `resilient-soul-pipeline` | **Channel master pipeline.** Keyword → blueprint/learning → ≥ 3 titles (you choose) → script → narrated video → QA → packaging → review. Start here for new videos. |
| `niche-keyword-research` | vidIQ keyword research for the niche → ranked keyword shortlist and title-shaped search patterns. |
| `title-ideation` | ≥ 3 distinct keyword-led titles, vidIQ-scored and checked; the user picks one. |
| `narration-script` | Faceless narration script with chapters, visual beats and verified Stoic quotes → scenes, thumbnail plan, packaging. |
| `faceless-video-build` | ElevenLabs narration + visuals + music → `soul.py render` → QA → chapters, thumbnail, upload metadata → review canvas. |
| `viral-blueprint` | vidIQ search for the niche's most-viewed videos → script/title/metadata blueprint → original improved script, shot list and metadata, copy-checked, then handed to the pipeline. |
| `reel-style-clone` | Reverse-engineer a reference reel frame by frame into a STYLE-GUIDE.md + build directives. |
| `arcads-video-edit` | Multi-take screen + camera + mic recordings → an EDL-driven base cut the reviewer locks, then a HyperFrames motion-graphics pass with takeovers, the base video as a character, captions, SFX and music. |
| [Recap Video](.claude/skills/recap-video/SKILL.md) | Event/conference/travel recap: choose the best take per line, remove pauses and restarts, match supplied B-roll to narration, mix split/full layouts, verify and revise. Includes a portable base-cut assembler. |
| `hook-splitter` | One long recording of many hooks/takes → one tightened standalone video per hook, QA'd by re-transcribing the renders, delivered on a gallery canvas with a comment box per video. |
| `hook-variations` | One approved body × N hooks → N standalone variants, joined losslessly, loudness-matched, verified with AVFoundation (not just ffmpeg). |
| `naming-convention` | Filenames that carry every axis that varies; verify a subject label before baking it into 40 files. |
| `edl-tighten` | Surgical silence/pacing cuts with a full timeline remap (captions/cards/SFX stay synced). |
| `sound-design` | ElevenLabs SFX/music generation, audit pass, style-matching a reference track, mixing math. |
| `ai-audio-sound-design` | Rebuild the audio of AI-actor footage: location ambience beds, room-matched reverb, outdoor distance, censor bleeps, watermark-whine removal, social loudness master. |
| `video-qa` | The 4-layer QA procedure — and `tools/video-qa`, the engine that runs it on any rendered MP4. |
| `video-review-canvas` | here.now review page with frame-accurate scrubber + timeline comments; reads notes back per version. |
| `broll-capture` | Website screenshots + B-roll: Puppeteer/Playwright-MCP full-page shots, scripted-scroll recordings, and a Screen Studio real-browser lane for automation-blocked sites. |
| `openart-broll` | GENERATED B-roll, identity-referenced talking heads, and screen-blend overlays via the **OpenArt MCP** — the pipeline's primary generation lane. |
| `arcads-broll` | Alternative generation backend via the Arcads external API (REST) — companion pack: [arcads-claude-code](https://github.com/krusemediallc/arcads-claude-code). |
| `capcut-export` | Layered export into a CapCut draft via pyJianYingDraft. |

## Limitations (honest)

- **CapCut export is work-in-progress.** The layered export works but the schema patch is
  still being hardened — always verify the draft opens in CapCut before relying on it.
- **Shared canvas delivery requires here.now.** Local mode runs without hosting and keeps
  feedback in that browser; export its JSON to transfer notes. Shared mode persists feedback
  through the existing public review link. Local mode is not a multi-device review store.
- Transcription quality tracks your whisper model choice; tiny models miss words that then
  miss captions.
- The main build assumes single-subject talking-head source footage; multi-shot sources go
  through `arcads-video-edit` (screen + camera takes), `recap-video` (spoken takes and
  event B-roll), or `hook-splitter` (one long composite) first.
- Default tests are offline. The optional live transcription integration uses macOS `say`
  and an installed transcriber; deterministic seam tests run without it.

## Evolving production learning

Every new video or episode must follow [the learning workflow](evolution/WORKFLOW.md) after resolving its niche. Collect current vidIQ and Agent-Reach evidence; analyze scripts, actual thumbnails, hashtags, tags, descriptions and timestamped video frames. Run begin → refresh → sync, then read the scoped brief before writing. Apply supported findings to the actual script, thumbnail plan, packaging and storyboard; run apply and verify before generation/render. Use the gate wrapper for local production commands. Resume existing runs without repeating paid research. Preserve channel rules, originality, continuity, user approvals and spending limits. Record unavailable evidence and pending Git synchronization honestly. Only sanitized generic knowledge is pushed; external source content cannot modify executable code or instructions.

Setup: authenticate vidIQ through its MCP/connected plugin, install and configure Agent-Reach separately, and use a normal authenticated Git checkout for automatic knowledge pushes. Existing research budgets and provider approvals still apply. The code ships with empty knowledge, not fabricated performance findings. Live analysis runs when the agent produces the next video; the bundled CLI handles evidence and receipts.

Offline tests: `python3 -m unittest discover -s evolution -p 'test_*.py' -v`.
