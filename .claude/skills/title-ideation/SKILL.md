---
name: title-ideation
description: >
  Turn the ranked keyword shortlist (and the viral blueprint's winning title patterns) into AT
  LEAST 3 distinct, keyword-led YouTube titles for The Resilient Soul, score them with vidIQ,
  and let the user choose one before any script is written. Use after niche-keyword-research,
  and for "give me title ideas", "which title should I use", "score these titles",
  "rewrite my title". Not for keyword discovery (niche-keyword-research) or thumbnails.
---

# title-ideation — three or more titles, one choice, then write

Inputs: `research/keywords.json` (primary keyword chosen) and, when present,
`viral/blueprint.md` + `viral/selection.json` from `viral-blueprint`.
Output: `titles.json` with ≥ 3 checked, scored candidates and the user's `chosen` pick;
`upload.json.title` filled.

## 1 · Draft (no credits)

Write **5–6** candidates, each on a *different* angle so the choice is real:

| Angle | Shape |
|---|---|
| Promise / list | "7 Stoic Lessons to …" — number + outcome |
| Pain → relief | "How to Stop … (Stoic Wisdom for …)" |
| Question / curiosity | "Why … Even When …?" |
| Authority | "Marcus Aurelius on …" / "Seneca's Rule for …" |
| Identity | "Become the Person Who …" |

Rules (enforced by the checker):
- Each title contains its target keyword's words (`keyword` field; defaults to the primary).
- ≤ 70 characters to stay untruncated (hard limit 100). Put the keyword early.
- No two titles ≥ 75 % alike. Not mostly CAPS — one emphasised word at most.
- Use the blueprint's title **pattern**, never its wording (`blueprint.py check --title`).
- Promise only what the script will deliver; no fake quotes, no invented studies.

```json
{
  "primary_keyword": "stoic teachings",
  "titles": [
    {"title": "…", "keyword": "stoic teachings", "angle": "promise/list", "vidiq_score": null},
    …
  ],
  "chosen": null
}
```

## 2 · Score (vidIQ, 5 credits each)

Score the best 3–5 drafts: `vidiq_score_title title="…" type="long" channelId="UCc0FLEsKcwu8N2oNTseGtuw"`.
Record each `vidiq_score` in `titles.json`. Optionally `vidiq_generate_titles` for extra
options, and `vidiq_youtube_preview` to see the top picks beside real competitors. State the
credit estimate first.

## 3 · Check

```bash
python3 tools/soul/soul.py titles check <project>/titles.json --keywords <project>/research/keywords.json
python3 .claude/skills/viral-blueprint/scripts/blueprint.py check <project>/viral/blueprint.json --title "<each title>"   # if a blueprint exists
```

ERROR blocks (fewer than 3 titles, missing keyword, near-duplicates, > 100 chars). Warnings are
for judgment.

## 4 · The user chooses

Present **at least 3** titles as a numbered list: title · keyword · chars · vidIQ score · one
line on the angle, with your recommendation first. Use AskUserQuestion when available. Do not
proceed to the script until a title is chosen. Then:

```bash
python3 tools/soul/soul.py titles choose <project>/titles.json --pick <N>
```

This stamps `chosen` and writes the title into `upload.json`. If the user edits the wording,
update the candidate in `titles.json`, re-check, then choose.
