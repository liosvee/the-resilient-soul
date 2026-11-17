---
name: narration-script
description: >
  Write the narration script for a chosen Resilient Soul title: a faceless, voiced long-form
  video (8–12 min) on Stoic philosophy, resilience and emotional healing, structured into
  chapters and visual beats, with verified quotes, then lint it and split it into timed scenes
  for narration and rendering. Use after a title is chosen (title-ideation), and for "write
  the script", "rewrite the hook", "make the script shorter/longer", "add a chapter". Not for
  picking the topic or title.
---

# narration-script — the words the voice will say

Inputs: the chosen title (`titles.json.chosen`), `research/keywords.json`, the active learning
brief (`.evolution/runs/<id>/brief.md`) and `viral/blueprint.md` when present.
Outputs: `script.md`, `scenes.json`, `thumbnail-plan.md`, `packaging.md`.

## Voice of the channel

From `channel/channel.json → voice_and_tone`: compassionate, grounded, direct. Talk to one
person who is hurting ("you"), then hand them something they can practise tonight. Stoicism is
the toolkit, healing is the point. Plain words, short sentences, room to breathe. No guru-speak,
no mocking the viewer, no invented statistics.

## Structure (≈ 1,100–1,600 words at 140 wpm)

```markdown
# <chosen title>

## <Intro chapter name>
[visual: rain on a window at night, a figure sitting alone]
Hook — name the viewer's pain in their words and promise the payoff within ~30 seconds.
Say the primary keyword naturally in the first two sentences.

## <Lesson 1 name>
[visual: …]
Idea → why it works (Stoic source, verified) → a concrete situation → one practice.

… 4–7 lesson chapters, each with its own [visual: …] beats …

## <Closing chapter name>
Callback to the hook, the one sentence to remember, then the channel CTA
(channel.json → cta, in your own words).
```

- `## ` headings become YouTube chapters (need ≥ 3, each ≥ 10 s). Name them for viewers.
- `[visual: …]` lines describe what is on screen for the paragraphs that follow — concrete,
  filmable, no on-screen text. Change the visual every 1–3 paragraphs; a scene is one paragraph
  (short paragraphs merge with the next).
- One idea per paragraph, 2–5 sentences, sentences under ~30 words — the narrator breathes at
  paragraph breaks.
- Apply the learning brief: address each active rule for the script facet with an exact
  excerpt (it goes into the `apply` receipt). Follow the blueprint's beat structure, never its
  words.

## Quotes must be real

Every line attributed to Marcus Aurelius, Seneca, Epictetus or another Stoic must be checked
against the primary text with the `the-stoic-library:stoic-sources` skill (exact wording, the
named translation, the reference — e.g. *Meditations* 4.3). Unverifiable → paraphrase it as an
idea ("Seneca argued that…") or cut it. The linter lists every quoted line under
`verify_quotes`; clear that list before narration.

## Check and split

```bash
python3 tools/soul/soul.py script lint <project>/script.md
python3 .claude/skills/viral-blueprint/scripts/blueprint.py check <project>/viral/blueprint.json --script <project>/script.md   # if a blueprint exists
python3 tools/soul/soul.py script scenes <project>/script.md -o <project>/scenes.json
python3 tools/soul/soul.py visuals plan <project>/scenes.json
```

Lint warns on runtime outside 8–12 min, a hook that never addresses the viewer, < 3
chapters, missing CTA, over-long sentences and paragraphs with no visual note.

## Packaging drafts (learning facets)

Write alongside the script, because `evolution/learn.py apply` binds them:

- `thumbnail-plan.md` — background image idea (one subject, strong contrast, room for text on
  the left), ≤ 5 words of thumbnail text that complement (not repeat) the title, accent colour.
- `packaging.md` — description (first 150 characters carry the primary keyword and the
  promise; `{{CHAPTERS}}` placeholder; channel links), 3–5 hashtags, tags ≤ 500 characters from
  the keyword shortlist. Mirror the final values into `upload.json`.
- `scenes.json` is the storyboard (frames facet); `visuals/prompts.md` is a production input.

Show the user the script (or the hook + chapter list for a quick yes) before narration —
narration spends ElevenLabs credits.
