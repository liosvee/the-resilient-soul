---
name: niche-keyword-research
description: >
  Find the highest-searched, winnable YouTube keywords in The Resilient Soul's niche (Stoic
  philosophy, resilience, emotional healing, moving on, self-mastery) with vidIQ keyword
  research, then rank them into a shortlist that drives the video's titles. Use as the FIRST
  step of every new video, and for "what should my next video be about", "find keywords for
  my channel", "what are people searching in this niche", "find trending stoic topics". Not for
  scoring a finished title (title-ideation) or for viral-video structure (viral-blueprint).
---

# niche-keyword-research — what is the niche searching for right now?

Output: `<project>/research/keywords.json` + `keywords.md` — a ranked shortlist of target
keywords and a list of title-shaped searches (patterns, not targets). The next stage
(`title-ideation`) must build every title on one of these keywords.

## Before you start

- `python3 tools/soul/soul.py init <projects dir>/<slug>` creates the project folders.
  Use a working slug like `2026-11-stoic-next`; rename later if the topic settles.
- Read `channel/channel.json`: `seed_keywords`, `relevance_terms`, `niche`, market `US`, `en`.
  `MASTER_CONTEXT.md` may name topics already covered — avoid repeating a recent video.
- **Cost.** Each `vidiq_keyword_research` call is 5 vidIQ credits. A normal run is 4–6 calls
  (20–30 credits). Check `vidiq_balance`, state the estimate, then collect. Never auto-retry a
  charged call; never repeat research for a resumed project — reuse `research/raw/`.

## 1 · Collect (vidIQ MCP)

Pick 2–3 seeds that fit what the channel wants to make next (ask the user if they have a topic
in mind; otherwise rotate through `seed_keywords`). For each seed, save the **verbatim**
response to `research/raw/<mode>-<seed>.md` (the tool returns markdown tables; JSON also works):

```
vidiq_keyword_research  mode="research"   keyword="<seed>"  limit=25         # volume, competition, related
vidiq_keyword_research  mode="questions"  keyword="<seed>"  limit=25         # what viewers literally ask
vidiq_keyword_research  mode="rising"     niche="stoicism resilience self improvement"  limit=50  # growing demand (once per run)
```

Optional when a seed looks strong: `mode="matching_terms"` for long-tail variants that keep
every seed word. Relay the tool's `Note:` lines — null is unknown, not zero.

## 2 · Rank

```bash
python3 tools/soul/soul.py keywords rank <project>/research/raw/*.md \
  -o <project>/research/keywords.json --top 15
```

Ranking = vidIQ `overall` (its volume-vs-competition blend) nudged by demand growth (±growth/10,
capped at ±10). Dropped: volume < 40, competition > 70, rows off the channel's
`relevance_terms`, and title-shaped rows (7+ words or "10 stoic …"), which are kept separately
as **title patterns** — proof of what packaging already wins searches. Tune with
`--min-volume`, `--max-competition`, `--must-match` (repeatable).

## 3 · Decide with the user

Show the top 5–8 from `keywords.md` with volume, competition and growth, plus the title
patterns, and recommend a **primary keyword** — prefer high opportunity with competition
under ~55 and an angle the channel can own (emotional healing + Stoic practice, not generic
history). Note one or two secondary keywords for the description/tags.

Write the choice into the project's `titles.json` stub:

```json
{"primary_keyword": "<chosen>", "secondary_keywords": ["…"], "titles": [], "chosen": null}
```

## Honest limits

- vidIQ volumes are estimates; "high searched" means high within this sample of seeds.
- A keyword's search volume says nothing about whether *this* channel's video will rank — new
  channels win on specific, emotionally precise angles more than on head terms like "stoicism".
- Save raw responses with the project, never in this repo.
