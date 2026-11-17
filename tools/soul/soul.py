#!/usr/bin/env python3
"""soul.py — The Resilient Soul production CLI.

Keyword research → titles → script → narration → visuals → render → packaging for a
faceless, narrated long-form YouTube video. Research and generation that need a paid
service run through the agent's connected tools (vidIQ MCP) or an explicit, confirmed
API call (ElevenLabs). Everything else here is deterministic and offline.

    soul.py init <project> [--slug SLUG]
    soul.py status <project>
    soul.py keywords rank <saved vidIQ responses...> [--top 15] -o keywords.json
    soul.py titles check <titles.json> [--keywords keywords.json]
    soul.py titles choose <titles.json> --pick N
    soul.py script lint <script.md> [--wpm 140]
    soul.py script scenes <script.md> -o scenes.json
    soul.py narrate <scenes.json> --voice VOICE_ID [--dry-run | --yes]
    soul.py visuals plan <scenes.json>
    soul.py render <scenes.json> [--music bed.mp3] [--size 1920x1080] [--draft]
    soul.py chapters <scenes.json> [--upload upload.json]
    soul.py thumbnail --image bg.png --text "FEW WORDS" -o thumbnail.png

Python 3.10+ standard library plus Pillow (captions and thumbnails) and ffmpeg/ffprobe.
"""
from __future__ import annotations

import argparse
import base64
import difflib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FFMPEG = os.environ.get("FFMPEG_PATH") or os.environ.get("FFMPEG") or "ffmpeg"
FFPROBE = os.environ.get("FFPROBE_PATH") or os.environ.get("FFPROBE") or "ffprobe"
CHANNEL = ROOT / "channel" / "channel.json"

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}


class SoulError(Exception):
    pass


def die(msg: str) -> None:
    raise SoulError(msg)


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def channel() -> dict:
    return load_json(CHANNEL) if CHANNEL.exists() else {}


def learning_gate(path: Path) -> None:
    """Refuse paid/generation work on an artifact the active learning receipt does not bind."""
    sys.path.insert(0, str(ROOT))
    try:
        from evolution.learn import verify_for_file
    except ImportError:  # pragma: no cover - the pack always ships evolution/
        return
    try:
        verify_for_file(path)
    except ValueError as exc:
        die(f"Learning not applied: {exc} (run evolution/learn.py apply + verify first)")


# ─────────────────────────────────────────────────────────────── project ──

LAYOUT = ["research", "viral", "audio", "visuals", "music", "render", "_qa"]


def cmd_init(args) -> dict:
    project = Path(args.project).resolve()
    for d in LAYOUT:
        (project / d).mkdir(parents=True, exist_ok=True)
    meta = project / "soul.json"
    if not meta.exists():
        save_json(meta, {"slug": args.slug or project.name, "channel": channel().get("handle"),
                         "format": "long", "created": _now()})
    return {"project": str(project), "created": LAYOUT}


def _now() -> str:
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


STEPS = [
    ("keywords", "research/keywords.json", "keyword research (niche-keyword-research)"),
    ("viral", "viral/selection.json", "viral blueprint (viral-blueprint)"),
    ("titles", "titles.json", "title candidates (title-ideation)"),
    ("title_chosen", None, "title chosen by the user"),
    ("script", "script.md", "narration script (narration-script)"),
    ("scenes", "scenes.json", "scene split (soul.py script scenes)"),
    ("learning", None, "learning applied + verified (evolution/learn.py)"),
    ("narration", None, "narration audio (soul.py narrate)"),
    ("visuals", None, "one visual per scene (faceless-video-build)"),
    ("render", None, "rendered MP4 (soul.py render)"),
    ("thumbnail", "thumbnail.png", "thumbnail (soul.py thumbnail)"),
    ("upload", "upload.json", "upload metadata with chapters"),
]


def project_status(project: Path) -> dict:
    project = Path(project).resolve()
    done = {}
    for key, rel, _ in STEPS:
        if rel:
            done[key] = (project / rel).exists()
    titles = project / "titles.json"
    done["title_chosen"] = titles.exists() and bool(load_json(titles).get("chosen"))
    active = project / ".evolution" / "active.json"
    if active.exists():
        run = load_json(project / ".evolution" / "runs" / load_json(active)["run_id"] / "run.json")
        done["learning"] = run.get("phase") == "applied"
    else:
        done["learning"] = False
    scenes = load_json(project / "scenes.json")["scenes"] if (project / "scenes.json").exists() else []
    done["narration"] = bool(scenes) and all((project / s["audio"]).exists() for s in scenes)
    done["visuals"] = bool(scenes) and all(find_visual(project, s) for s in scenes)
    done["render"] = any((project / "render").glob("*.mp4")) if (project / "render").exists() else False
    nxt = next(((k, label) for k, _, label in STEPS if not done.get(k)), None)
    return {"project": str(project), "done": done,
            "next": {"step": nxt[0], "do": nxt[1]} if nxt else {"step": "deliver", "do": "QA + review canvas + upload"}}


def cmd_status(args) -> dict:
    return project_status(Path(args.project))


# ─────────────────────────────────────────────────────────────── keywords ──

def _num(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "")
    if s.lower() in {"", "null", "none", "n/a", "-"}:
        return None
    m = re.match(r"^<\s*([0-9.]+)$", s)
    if m:  # "<750" → below the reported floor; keep as a small known-low number
        return float(m.group(1)) / 2
    m = re.match(r"^([+-]?[0-9.]+)\s*%?$", s)
    return float(m.group(1)) if m else None


def _split_row(line: str) -> list[str]:
    cells, buf, i = [], "", 0
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    while i < len(body):
        if body[i] == "\\" and i + 1 < len(body) and body[i + 1] == "|":
            buf += "|"; i += 2; continue
        if body[i] == "|":
            cells.append(buf.strip()); buf = ""; i += 1; continue
        buf += body[i]; i += 1
    cells.append(buf.strip())
    return cells


def parse_keyword_rows(text: str) -> list[dict]:
    """Rows from a saved vidIQ keyword_research response: markdown tables or JSON."""
    rows: list[dict] = []
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        def walk(node, section=None):
            if isinstance(node, dict):
                kw = node.get("keyword") or node.get("term")
                if isinstance(kw, str):
                    rows.append({"section": section, **node, "keyword": kw})
                for k, v in node.items():
                    walk(v, k if isinstance(v, list) else section)
            elif isinstance(node, list):
                for item in node:
                    walk(item, section)
        walk(json.loads(text))
        return rows
    header, section = None, None
    for line in text.splitlines():
        h = re.match(r"^#{2,4}\s+(\w[\w ]*?)\s*(\(\d+\))?\s*$", line.strip())
        if h:
            section, header = h.group(1).strip(), None
            continue
        if not line.strip().startswith("|"):
            header = None if line.strip() == "" else header
            continue
        cells = _split_row(line)
        if header is None:
            header = [c.split(" (")[0] for c in cells]
            continue
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
            continue
        if len(cells) != len(header):
            continue
        row = dict(zip(header, cells))
        if row.get("keyword"):
            row["section"] = section
            rows.append(row)
    return rows


def score_keyword(row: dict) -> dict:
    volume = _num(row.get("volume"))
    competition = _num(row.get("competition"))
    overall = _num(row.get("overall"))
    monthly = _num(row.get("estimatedMonthlySearch"))
    growth = _num(row.get("searchDemandGrowthPct"))
    if overall is None and volume is not None and competition is not None:
        overall = (volume + (100 - competition)) / 2
    score = overall if overall is not None else 0.0
    if growth is not None:  # rising demand nudges up, collapsing demand nudges down
        score += max(-10.0, min(10.0, growth / 10.0))
    words = len(row["keyword"].split())
    return {
        "keyword": row["keyword"].strip(),
        "section": row.get("section"),
        "volume": volume, "competition": competition, "overall": overall,
        "monthly_searches": monthly, "growth_pct": growth,
        "top_markets": row.get("topMarkets"),
        "words": words,
        "title_like": words >= 7 or bool(re.match(r"^\d+\s", row["keyword"])) and words >= 4,
        "opportunity": round(score, 1),
    }


def cmd_keywords_rank(args) -> dict:
    seen: dict[str, dict] = {}
    for f in args.inputs:
        for row in parse_keyword_rows(Path(f).read_text(encoding="utf-8")):
            k = score_keyword(row)
            key = re.sub(r"\s+", " ", k["keyword"].lower())
            if key not in seen or (k["opportunity"] > seen[key]["opportunity"]):
                k["source"] = Path(f).name
                seen[key] = k
    allk = sorted(seen.values(), key=lambda k: (-k["opportunity"], -(k["monthly_searches"] or 0)))
    must = [m.lower() for m in (args.must_match or channel().get("relevance_terms", []))]
    def relevant(k):
        return not must or any(m in k["keyword"].lower() for m in must)
    targets = [k for k in allk if not k["title_like"] and relevant(k)
               and (k["volume"] or 0) >= args.min_volume
               and (k["competition"] is None or k["competition"] <= args.max_competition)]
    patterns = [k for k in allk if k["title_like"]]
    low = [k for k in allk if (k["volume"] or 0) < args.min_volume and not k["title_like"]]
    out = {
        "generated": _now(),
        "method": "rank by vidIQ overall (volume vs competition) ± growth/10 (capped ±10); "
                  "drop volume < min, competition > max, title-shaped rows, off-niche rows",
        "filters": {"min_volume": args.min_volume, "max_competition": args.max_competition, "must_match": must},
        "primary_candidates": targets[: args.top],
        "title_patterns": patterns[:10],
        "long_tail_low_volume": low[:15],
        "all_count": len(allk),
    }
    if args.output:
        save_json(Path(args.output), out)
        md = Path(args.output).with_suffix(".md")
        lines = ["# Keyword shortlist", "", out["method"], "",
                 "| # | keyword | opportunity | volume | competition | monthly | growth |",
                 "|---|---|---|---|---|---|---|"]
        for i, k in enumerate(targets[: args.top], 1):
            lines.append(f"| {i} | {k['keyword']} | {k['opportunity']} | {_fmt(k['volume'])} | "
                         f"{_fmt(k['competition'])} | {_fmt(k['monthly_searches'])} | {_fmt(k['growth_pct'], '%')} |")
        if patterns:
            lines += ["", "## Title-shaped searches (patterns for titles, not targets)", ""]
            lines += [f"- {k['keyword']} (overall {_fmt(k['overall'])})" for k in patterns[:10]]
        md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"top": [(k["keyword"], k["opportunity"]) for k in targets[: args.top]],
            "title_patterns": [k["keyword"] for k in patterns[:5]], "output": args.output}


def _fmt(v, suffix=""):
    if v is None:
        return "—"
    return (f"{v:+.0f}{suffix}" if suffix == "%" else f"{v:,.0f}")


# ─────────────────────────────────────────────────────────────── titles ──

TITLE_MAX = 100   # YouTube hard limit
TITLE_SOFT = 70   # visible in most surfaces


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).split().__str__()


def keyword_in_title(keyword: str, title: str) -> bool:
    t = set(re.sub(r"[^a-z0-9 ]+", " ", title.lower()).split())
    words = [w for w in re.sub(r"[^a-z0-9 ]+", " ", keyword.lower()).split() if w not in {"a", "the", "to", "of", "by", "how"}]
    stem = lambda w: w[:-1] if w.endswith("s") and len(w) > 3 else w
    ts = {stem(w) for w in t}
    return all(stem(w) in ts for w in words)


def check_titles(data: dict, keywords: dict | None = None) -> dict:
    titles = data.get("titles", [])
    errors, warnings = [], []
    if len(titles) < 3:
        errors.append(f"need at least 3 title candidates, have {len(titles)}")
    primary = data.get("primary_keyword")
    if not primary:
        errors.append("set primary_keyword (from research/keywords.json)")
    known = {k["keyword"].lower() for k in (keywords or {}).get("primary_candidates", [])}
    report = []
    for i, t in enumerate(titles, 1):
        title = t.get("title", "").strip()
        kw = t.get("keyword") or primary or ""
        issues = []
        if not title:
            errors.append(f"#{i}: empty title"); continue
        if len(title) > TITLE_MAX:
            errors.append(f"#{i}: {len(title)} chars > YouTube's {TITLE_MAX}")
        elif len(title) > TITLE_SOFT:
            issues.append(f"{len(title)} chars — truncated after ~{TITLE_SOFT}")
        if kw and not keyword_in_title(kw, title):
            errors.append(f"#{i}: target keyword '{kw}' not in title")
        if known and kw and kw.lower() not in known:
            issues.append(f"keyword '{kw}' is not on the ranked shortlist")
        letters = [c for c in title if c.isalpha()]
        if letters and sum(c.isupper() for c in letters) / len(letters) > 0.6:
            issues.append("mostly CAPS — reads as spam; cap one or two words at most")
        if t.get("vidiq_score") is None:
            issues.append("no vidiq_score yet (vidiq_score_title type=long)")
        warnings += [f"#{i}: {x}" for x in issues]
        report.append({"n": i, "title": title, "chars": len(title), "keyword": kw,
                       "vidiq_score": t.get("vidiq_score"), "issues": issues})
    for a in range(len(titles)):
        for b in range(a + 1, len(titles)):
            r = difflib.SequenceMatcher(None, titles[a]["title"].lower(), titles[b]["title"].lower()).ratio()
            if r >= 0.75:
                errors.append(f"#{a+1} and #{b+1} are {r:.0%} alike — offer genuinely different angles")
    status = "ERROR" if errors else ("WARN" if warnings else "OK")
    return {"status": status, "errors": errors, "warnings": warnings, "titles": report}


def cmd_titles_check(args) -> dict:
    data = load_json(Path(args.titles))
    kw = load_json(Path(args.keywords)) if args.keywords else None
    res = check_titles(data, kw)
    if res["status"] == "ERROR":
        print(json.dumps(res, indent=2))
        raise SystemExit(1)
    return res


def cmd_titles_choose(args) -> dict:
    path = Path(args.titles)
    data = load_json(path)
    res = check_titles(data)
    if res["status"] == "ERROR":
        die("fix title errors before choosing: " + "; ".join(res["errors"]))
    n = args.pick
    if not 1 <= n <= len(data["titles"]):
        die(f"--pick must be 1..{len(data['titles'])}")
    chosen = dict(data["titles"][n - 1]); chosen["n"] = n; chosen["chosen_at"] = _now()
    data["chosen"] = chosen
    save_json(path, data)
    upload = path.parent / "upload.json"
    up = load_json(upload) if upload.exists() else {"title": "", "description": "", "tags": []}
    up["title"] = chosen["title"]
    save_json(upload, up)
    return {"chosen": chosen["title"], "upload": str(upload)}


# ─────────────────────────────────────────────────────────────── script ──

VISUAL_RE = re.compile(r"^\s*\[(?:visual|broll|image|clip|b-roll)\s*:\s*(.+?)\]\s*$", re.I)
NOTE_RE = re.compile(r"^\s*\[.*\]\s*$")
QUOTE_AUTHORS = re.compile(r"\b(Marcus Aurelius|Seneca|Epictetus|Zeno|Musonius|Cato|Cleanthes|Chrysippus)\b")


def parse_script(text: str) -> dict:
    title, chapter, visual = None, "Intro", None
    paras, buf, chapters = [], [], []
    def flush():
        if buf:
            paras.append({"chapter": chapter, "visual": visual, "text": " ".join(buf).strip()})
            buf.clear()
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("# ") and title is None:
            flush(); title = line[2:].strip(); continue
        if line.startswith("## "):
            flush(); chapter = line[3:].strip(); chapters.append(chapter); visual = None; continue
        m = VISUAL_RE.match(line)
        if m:
            flush(); visual = m.group(1).strip(); continue
        if NOTE_RE.match(line) or line.startswith("<!--") or line.startswith(">"):
            continue
        if not line.strip():
            flush(); continue
        buf.append(line.strip())
    flush()
    return {"title": title, "chapters": chapters, "paragraphs": [p for p in paras if p["text"]]}


def _words(s: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9’']+", s)


def lint_script(text: str, wpm: float = 140, target=(8.0, 12.0)) -> dict:
    s = parse_script(text)
    spoken = " ".join(p["text"] for p in s["paragraphs"])
    words = _words(spoken)
    minutes = len(words) / wpm if wpm else 0
    errors, warnings, verify = [], [], []
    if not words:
        errors.append("no spoken text")
    if minutes and not (target[0] <= minutes <= target[1]):
        warnings.append(f"~{minutes:.1f} min at {wpm:.0f} wpm; channel target is {target[0]:.0f}–{target[1]:.0f} min")
    hook = " ".join(words[: int(wpm / 2)]).lower()  # first ~30 s
    if words and not ("?" in spoken[: len(hook) + 40] or re.search(r"\byou\b", hook)):
        warnings.append("hook (first ~30 s) never addresses the viewer or raises a question")
    if len(s["chapters"]) < 3:
        warnings.append(f"{len(s['chapters'])} '## ' chapters — YouTube chapters need at least 3")
    tail = " ".join(p["text"] for p in s["paragraphs"][-2:]).lower()
    if not re.search(r"subscribe|comment|share|next video|watch this", tail):
        warnings.append("no closing call to action in the last two paragraphs")
    for sent in re.split(r"(?<=[.!?])\s+", spoken):
        if len(_words(sent)) > 38:
            warnings.append(f"long sentence ({len(_words(sent))} words) — split for narration: '{sent[:60]}…'")
    for p in s["paragraphs"]:
        if QUOTE_AUTHORS.search(p["text"]) and re.search(r"[\"“”]", p["text"]):
            verify.append(p["text"][:120])
    no_visual = sum(1 for p in s["paragraphs"] if not p["visual"])
    if no_visual:
        warnings.append(f"{no_visual} paragraph(s) have no [visual: …] note — they inherit the channel default")
    return {"status": "ERROR" if errors else ("WARN" if warnings else "OK"), "title": s["title"],
            "words": len(words), "est_minutes": round(minutes, 2), "chapters": s["chapters"],
            "paragraphs": len(s["paragraphs"]), "errors": errors, "warnings": warnings,
            "verify_quotes": verify}


def cmd_script_lint(args) -> dict:
    ch = channel()
    target = tuple(ch.get("target_minutes", [8, 12]))
    res = lint_script(Path(args.script).read_text(encoding="utf-8"), args.wpm or ch.get("wpm", 140), target)
    if res["status"] == "ERROR":
        print(json.dumps(res, indent=2)); raise SystemExit(1)
    return res


def build_scenes(text: str, min_words: int = 18, default_visual: str | None = None) -> dict:
    s = parse_script(text)
    merged: list[dict] = []
    for p in s["paragraphs"]:
        same = merged and merged[-1]["chapter"] == p["chapter"] and p["visual"] == merged[-1]["visual"]
        short = len(_words(p["text"])) < min_words or (merged and len(_words(merged[-1]["text"])) < min_words)
        if same and short:  # a short paragraph shares the neighbouring scene (same chapter + visual)
            merged[-1]["text"] += " " + p["text"]
        else:
            merged.append(dict(p))
    scenes = []
    for i, p in enumerate(merged, 1):
        sid = f"scene-{i:03d}"
        scenes.append({
            "id": sid, "chapter": p["chapter"], "text": p["text"],
            "visual_prompt": p["visual"] or default_visual or "slow cinematic atmosphere matching the narration",
            "visual": f"visuals/{sid}",            # extension resolved at render time
            "audio": f"audio/{sid}.mp3", "alignment": f"audio/{sid}.align.json",
        })
    return {"title": s["title"], "chapters": s["chapters"], "scenes": scenes}


def cmd_script_scenes(args) -> dict:
    ch = channel()
    out = Path(args.output)
    data = build_scenes(Path(args.script).read_text(encoding="utf-8"), args.min_words,
                        ch.get("default_visual"))
    if out.exists() and not args.force:
        old = load_json(out)
        # keep measured timings for unchanged scenes so a script tweak doesn't drop finished audio
        prev = {s["id"]: s for s in old.get("scenes", [])}
        for s in data["scenes"]:
            if s["id"] in prev and prev[s["id"]]["text"] == s["text"]:
                for k in ("duration", "start", "voice_id", "visual_prompt_locked"):
                    if k in prev[s["id"]]:
                        s[k] = prev[s["id"]][k]
    save_json(out, data)
    return {"scenes": len(data["scenes"]), "chapters": data["chapters"], "output": str(out)}


# ─────────────────────────────────────────────────────────────── narration ──

def env_key(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    d = Path.cwd()
    for base in [d, *d.parents, ROOT]:
        f = base / ".env"
        if f.exists():
            for line in f.read_text().splitlines():
                if line.strip().startswith(name + "="):
                    v = line.split("=", 1)[1].strip().strip("\"'")
                    if v:
                        return v
    return None


def probe_duration(path: Path) -> float:
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True)
    if out.returncode != 0 or not out.stdout.strip():
        die(f"ffprobe could not read {path}")
    return float(out.stdout.strip())


def words_from_alignment(al: dict) -> list[dict]:
    """Character alignment (ElevenLabs with-timestamps) → word timings."""
    chars = al.get("characters") or []
    starts = al.get("character_start_times_seconds") or []
    ends = al.get("character_end_times_seconds") or []
    words, cur, t0, t1 = [], "", None, None
    for c, a, b in zip(chars, starts, ends):
        if c.isspace():
            if cur:
                words.append({"word": cur, "start": t0, "end": t1})
            cur, t0, t1 = "", None, None
            continue
        if not cur:
            t0 = a
        cur += c; t1 = b
    if cur:
        words.append({"word": cur, "start": t0, "end": t1})
    return words


def tts_request(text: str, voice: str, model: str, key: str, prev_text: str | None, next_text: str | None,
                settings: dict) -> dict:
    body = {"text": text, "model_id": model, "voice_settings": settings}
    if prev_text:
        body["previous_text"] = prev_text[-500:]
    if next_text:
        body["next_text"] = next_text[:500]
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_128",
        data=json.dumps(body).encode(), method="POST",
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        die(f"ElevenLabs HTTP {e.code}: {e.read()[:400].decode(errors='replace')}")


def cmd_narrate(args) -> dict:
    scenes_path = Path(args.scenes).resolve()
    project = scenes_path.parent
    data = load_json(scenes_path)
    ch = channel()
    voice = args.voice or ch.get("voice", {}).get("voice_id")
    model = args.model or ch.get("voice", {}).get("model_id", "eleven_multilingual_v2")
    settings = ch.get("voice", {}).get("settings", {"stability": 0.55, "similarity_boost": 0.8, "style": 0.15,
                                                    "use_speaker_boost": True})
    todo = [s for s in data["scenes"] if args.force or not (project / s["audio"]).exists()
            or s.get("voice_id") != voice]
    chars = sum(len(s["text"]) for s in todo)
    plan = {"scenes_to_generate": len(todo), "characters": chars, "voice_id": voice, "model": model,
            "note": "ElevenLabs bills per character on your plan; the same text regenerated is billed again."}
    if args.dry_run or not todo:
        return {**plan, "dry_run": bool(args.dry_run), "skipped_existing": len(data["scenes"]) - len(todo)}
    if not voice:
        die("no voice: pass --voice or set channel/channel.json voice.voice_id")
    if not args.yes:
        die(f"this will spend ~{chars} ElevenLabs characters; re-run with --yes after the user approves")
    key = env_key("ELEVENLABS_API_KEY")
    if not key:
        die("ELEVENLABS_API_KEY missing (.env or environment)")
    learning_gate(scenes_path)
    texts = [s["text"] for s in data["scenes"]]
    for i, s in enumerate(data["scenes"]):
        if s not in todo:
            continue
        res = tts_request(s["text"], voice, model, key, texts[i - 1] if i else None,
                          texts[i + 1] if i + 1 < len(texts) else None, settings)
        audio = project / s["audio"]
        audio.parent.mkdir(parents=True, exist_ok=True)
        audio.write_bytes(base64.b64decode(res["audio_base64"]))
        save_json(project / s["alignment"], res.get("alignment") or res.get("normalized_alignment") or {})
        s["voice_id"] = voice
        print(f"  {s['id']}: {len(s['text'])} chars", file=sys.stderr)
    retime(project, data, ch)
    save_json(scenes_path, data)
    return {**plan, "generated": len(todo), "total_seconds": data.get("total_seconds")}


def retime(project: Path, data: dict, ch: dict | None = None) -> None:
    ch = ch or channel()
    gap = float(ch.get("scene_gap_seconds", 0.45))
    chapter_gap = float(ch.get("chapter_gap_seconds", 1.0))
    t, prev_chapter = 0.0, None
    for i, s in enumerate(data["scenes"]):
        audio = project / s["audio"]
        if not audio.exists():
            continue
        speech = probe_duration(audio)
        last = i == len(data["scenes"]) - 1
        nxt = None if last else data["scenes"][i + 1]["chapter"]
        tail = 1.5 if last else (chapter_gap if nxt != s["chapter"] else gap)
        s["speech_seconds"] = round(speech, 3)
        s["duration"] = round(speech + tail, 3)
        s["start"] = round(t, 3)
        t += s["duration"]
        prev_chapter = s["chapter"]
    data["total_seconds"] = round(t, 3)


def cmd_retime(args) -> dict:
    p = Path(args.scenes).resolve()
    data = load_json(p)
    retime(p.parent, data)
    save_json(p, data)
    return {"total_seconds": data.get("total_seconds")}


# ─────────────────────────────────────────────────────────────── visuals ──

def find_visual(project: Path, scene: dict) -> Path | None:
    base = project / scene["visual"]
    if base.suffix and base.exists():
        return base
    for ext in [*IMAGE_EXT, *VIDEO_EXT]:
        p = base.with_suffix(ext)
        if p.exists():
            return p
    return None


def cmd_visuals_plan(args) -> dict:
    p = Path(args.scenes).resolve()
    data = load_json(p)
    ch = channel()
    style = ch.get("visual_style", "")
    lines = ["# Visual plan", "", f"Style suffix for every prompt: {style}", "",
             "Save each result as `visuals/<scene id>.png|jpg|mp4` (16:9, ≥1920×1080). "
             "Generated or licensed media only — never competitor footage.", ""]
    missing = 0
    for s in data["scenes"]:
        have = find_visual(p.parent, s)
        missing += not have
        lines += [f"## {s['id']} — {s['chapter']}" + ("" if not have else f"  ✓ {have.name}"),
                  f"- prompt: {s['visual_prompt']}. {style}".rstrip(),
                  f"- narration: {s['text'][:160]}{'…' if len(s['text']) > 160 else ''}",
                  f"- on screen for: {s.get('duration', '?')} s", ""]
    out = p.parent / "visuals" / "prompts.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"scenes": len(data["scenes"]), "missing": missing, "plan": str(out)}


# ─────────────────────────────────────────────────────────────── captions ──

def caption_chunks(words: list[dict], max_words: int = 6, max_chars: int = 34) -> list[dict]:
    chunks, cur = [], []
    def push():
        if cur:
            chunks.append({"text": " ".join(w["word"] for w in cur), "start": cur[0]["start"], "end": cur[-1]["end"]})
            cur.clear()
    for w in words:
        if w["start"] is None:
            continue
        candidate = " ".join(x["word"] for x in cur + [w])
        if cur and (len(cur) >= max_words or len(candidate) > max_chars):
            push()
        cur.append(w)
        if re.search(r"[.!?;:,—]$", w["word"]) and len(cur) >= 2:
            push()
    push()
    # hold each chunk until the next one starts (no flicker between words)
    for a, b in zip(chunks, chunks[1:]):
        a["end"] = max(a["end"], min(b["start"], a["end"] + 0.6))
    return chunks


def _font(path: str | None, size: int):
    from PIL import ImageFont
    candidates = [path, channel().get("font"),
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/Library/Fonts/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                  "C:/Windows/Fonts/arialbd.ttf"]
    for c in candidates:
        if c and Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default(size)


def caption_png(text: str, width: int, height: int, out: Path, font_path: str | None) -> tuple[int, int, int, int]:
    from PIL import Image, ImageDraw
    size = max(18, int(height * 0.052))
    font = _font(font_path, size)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    l, t, r, b = probe.textbbox((0, 0), text, font=font, stroke_width=3)
    pad_x, pad_y = int(size * 0.6), int(size * 0.35)
    w, h = (r - l) + 2 * pad_x, (b - t) + 2 * pad_y
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=int(size * 0.3), fill=(0, 0, 0, 140))
    d.text((pad_x - l, pad_y - t), text, font=font, fill=(255, 255, 255, 255),
           stroke_width=3, stroke_fill=(0, 0, 0, 255))
    img.save(out)
    x = (width - w) // 2
    y = int(height * 0.86) - h // 2
    return x, y, w, h


# ─────────────────────────────────────────────────────────────── render ──

def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        die("ffmpeg failed: " + " ".join(cmd[:6]) + " …\n" + p.stderr[-1500:])


def next_version(render_dir: Path, slug: str) -> Path:
    n = 1
    while (render_dir / f"{slug}-v{n}.mp4").exists():
        n += 1
    return render_dir / f"{slug}-v{n}.mp4"


def render_scene(project: Path, s: dict, idx: int, W: int, H: int, fps: int, tmp: Path, captions: bool,
                 font: str | None, draft: bool) -> Path:
    dur = float(s["duration"])
    frames = max(1, int(round(dur * fps)))
    audio = project / s["audio"]
    visual = find_visual(project, s)
    if visual is None and not draft:
        die(f"{s['id']}: no visual at {s['visual']}.* (use --draft for placeholders)")
    inputs: list[str] = []
    if visual is None:
        inputs += ["-f", "lavfi", "-i", f"color=c=0x1b2430:s={W}x{H}:r={fps}:d={dur:.3f}"]
        vchain = "[0:v]format=yuv420p,setsar=1"
    elif visual.suffix.lower() in IMAGE_EXT:
        inputs += ["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.3f}", "-i", str(visual)]
        zoom = 0.10
        inc = zoom / frames
        if idx % 2 == 0:
            z = f"min(1+{inc:.7f}*on,{1 + zoom:.3f})"
        else:
            z = f"max({1 + zoom:.3f}-{inc:.7f}*on,1)"
        vchain = (f"[0:v]scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
                  f"zoompan=z='{z}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={fps},"
                  f"trim=duration={dur:.3f},format=yuv420p,setsar=1")
    else:
        inputs += ["-stream_loop", "-1", "-i", str(visual)]
        vchain = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},"
                  f"trim=duration={dur:.3f},setpts=PTS-STARTPTS,format=yuv420p,setsar=1")
    fade = min(0.5, dur / 4)
    vchain += f",fade=t=in:st=0:d={fade:.2f},fade=t=out:st={dur - fade:.3f}:d={fade:.2f}"
    inputs += ["-i", str(audio)]
    audio_idx = 1
    overlays = []
    if captions and (project / s["alignment"]).exists():
        words = words_from_alignment(load_json(project / s["alignment"]))
        for j, c in enumerate(caption_chunks(words)):
            png = tmp / f"{s['id']}-cap{j:03d}.png"
            x, y, _, _ = caption_png(c["text"], W, H, png, font)
            inputs += ["-i", str(png)]
            overlays.append((len(overlays) + 2, x, y, c["start"], min(c["end"], dur)))
    graph = [vchain + "[v0]"]
    last = "v0"
    for k, (inp, x, y, a, b) in enumerate(overlays):
        graph.append(f"[{last}][{inp}:v]overlay={x}:{y}:enable='between(t,{a:.3f},{b:.3f})'[v{k+1}]")
        last = f"v{k+1}"
    graph.append(f"[{audio_idx}:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=duration={dur:.3f}[a]")
    out = tmp / f"{s['id']}.mp4"
    preset = "ultrafast" if draft else "veryfast"
    run([FFMPEG, "-y", "-v", "error", *inputs, "-filter_complex", ";".join(graph),
         "-map", f"[{last}]", "-map", "[a]", "-t", f"{dur:.3f}", "-r", str(fps),
         "-c:v", "libx264", "-preset", preset, "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "pcm_s16le", str(out.with_suffix(".mov"))])
    return out.with_suffix(".mov")


def cmd_render(args) -> dict:
    p = Path(args.scenes).resolve()
    project = p.parent
    data = load_json(p)
    ch = channel()
    W, H = (int(x) for x in (args.size or ch.get("size", "1920x1080")).split("x"))
    fps = args.fps or int(ch.get("fps", 30))
    missing_audio = [s["id"] for s in data["scenes"] if not (project / s["audio"]).exists()]
    if missing_audio:
        die(f"narration missing for {len(missing_audio)} scene(s): {missing_audio[:5]} — run soul.py narrate")
    if not args.draft:
        learning_gate(p)
    retime(project, data, ch)
    save_json(p, data)
    slug = load_json(project / "soul.json")["slug"] if (project / "soul.json").exists() else project.name
    out = Path(args.output) if args.output else next_version(project / "render", slug + ("-draft" if args.draft else ""))
    if out.exists():
        die(f"{out} exists — new versions are new files")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="soul-render-") as td:
        tmp = Path(td)
        parts = [render_scene(project, s, i, W, H, fps, tmp, not args.no_captions, args.font, args.draft)
                 for i, s in enumerate(data["scenes"])]
        listing = tmp / "concat.txt"
        listing.write_text("".join(f"file '{x}'\n" for x in parts))
        body = tmp / "body.mov"
        run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(body)])
        total = data["total_seconds"]
        music = Path(args.music) if args.music else None
        if music is None and (project / "music").exists():
            beds = sorted((project / "music").glob("*.mp3"))
            music = beds[-1] if beds else None
        bed_db = float(args.music_db if args.music_db is not None else ch.get("music_db", -24))
        lufs = float(ch.get("target_lufs", -14))
        if music and music.exists():
            graph = (f"[0:a]asplit=2[vo][key];"
                     f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={bed_db}dB,"
                     f"afade=t=out:st={max(0, total - 4):.2f}:d=4,atrim=duration={total:.3f}[bed];"
                     f"[bed][key]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[duck];"
                     f"[vo][duck]amix=inputs=2:normalize=0,loudnorm=I={lufs}:TP=-1.5:LRA=11[a]")
            run([FFMPEG, "-y", "-v", "error", "-i", str(body), "-stream_loop", "-1", "-i", str(music),
                 "-filter_complex", graph, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                 "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)])
        else:
            run([FFMPEG, "-y", "-v", "error", "-i", str(body), "-af", f"loudnorm=I={lufs}:TP=-1.5:LRA=11",
                 "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])
    dur = probe_duration(out)
    return {"render": str(out), "seconds": round(dur, 2), "planned_seconds": total,
            "music": str(music) if music and music.exists() else None, "size": f"{W}x{H}", "fps": fps,
            "next": "run video-qa on this file, then publish on video-review-canvas"}


# ─────────────────────────────────────────────────────────────── packaging ──

def fmt_ts(sec: float) -> str:
    sec = int(sec)
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def chapters_from(data: dict) -> list[dict]:
    out = []
    for s in data["scenes"]:
        if "start" not in s:
            die("scenes are not timed yet — narrate first")
        if not out or out[-1]["title"] != s["chapter"]:
            out.append({"title": s["chapter"], "start": s["start"]})
    if out:
        out[0]["start"] = 0.0
    return out


def cmd_chapters(args) -> dict:
    p = Path(args.scenes).resolve()
    data = load_json(p)
    chs = chapters_from(data)
    total = data.get("total_seconds", 0)
    errors = []
    if len(chs) < 3:
        errors.append("YouTube needs at least 3 chapters")
    for a, b in zip(chs, chs[1:] + [{"start": total}]):
        if b["start"] - a["start"] < 10:
            errors.append(f"chapter '{a['title']}' is shorter than 10 s")
    text = "\n".join(f"{fmt_ts(c['start'])} {c['title']}" for c in chs)
    if args.upload:
        up_path = Path(args.upload)
        up = load_json(up_path) if up_path.exists() else {"title": "", "description": "", "tags": []}
        desc = up.get("description", "")
        if "{{CHAPTERS}}" in desc:
            desc = desc.replace("{{CHAPTERS}}", text)
        elif "0:00 " not in desc:
            desc = (desc.rstrip() + "\n\nChapters\n" + text).strip()
        up["description"] = desc
        save_json(up_path, up)
    return {"chapters": text, "errors": errors}


def cmd_thumbnail(args) -> dict:
    from PIL import Image, ImageDraw, ImageFilter
    W, H = 1280, 720
    img = Image.open(args.image).convert("RGB")
    scale = max(W / img.width, H / img.height)
    img = img.resize((math.ceil(img.width * scale), math.ceil(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((left, top, left + W, top + H))
    shade = Image.new("L", (W, H))
    sd = ImageDraw.Draw(shade)
    for x in range(W):  # dark on the text side, clear on the subject side
        a = int(200 * max(0.0, 1 - x / (W * 0.62)))
        sd.line([(x, 0), (x, H)], fill=a)
    img = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, shade.filter(ImageFilter.GaussianBlur(8)))
    words = args.text.upper().split()
    if len(words) > 6:
        print("warning: thumbnails read best with ≤ 5 words", file=sys.stderr)
    ch = channel()
    accent = tuple(int(ch.get("accent", "#E8B04B").lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    d = ImageDraw.Draw(img)
    max_w = int(W * 0.58)  # keep the right side clear for the subject

    def wrap(font):
        lines, cur = [], []
        for w in words:
            trial = " ".join(cur + [w])
            if cur and d.textlength(trial, font=font) > max_w:
                lines.append(" ".join(cur)); cur = []
            cur.append(w)
        lines.append(" ".join(cur))
        return lines

    for size in range(150, 47, -6):
        font = _font(args.font, size)
        lines = wrap(font)
        if len(lines) <= 3 and all(d.textlength(l, font=font) <= max_w for l in lines):
            break
    y = H // 2 - (len(lines) * int(size * 1.08)) // 2
    for i, line in enumerate(lines):
        fill = accent if (args.accent_line or len(lines)) - 1 == i else (255, 255, 255)
        d.text((64, y), line, font=font, fill=fill, stroke_width=6, stroke_fill=(0, 0, 0))
        y += int(size * 1.08)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=92)
    kb = out.stat().st_size / 1024
    if kb > 2000:
        img.save(out.with_suffix(".jpg"), quality=85); out = out.with_suffix(".jpg")
    return {"thumbnail": str(out), "size": f"{W}x{H}", "kb": round(out.stat().st_size / 1024)}


# ─────────────────────────────────────────────────────────────── main ──

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="soul.py", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("project"); p.add_argument("--slug"); p.set_defaults(fn=cmd_init)
    p = sub.add_parser("status"); p.add_argument("project"); p.set_defaults(fn=cmd_status)

    kw = sub.add_parser("keywords").add_subparsers(dest="sub", required=True)
    p = kw.add_parser("rank"); p.add_argument("inputs", nargs="+"); p.add_argument("-o", "--output")
    p.add_argument("--top", type=int, default=15); p.add_argument("--min-volume", type=float, default=40)
    p.add_argument("--max-competition", type=float, default=70)
    p.add_argument("--must-match", action="append", help="keep only keywords containing one of these terms")
    p.set_defaults(fn=cmd_keywords_rank)

    ti = sub.add_parser("titles").add_subparsers(dest="sub", required=True)
    p = ti.add_parser("check"); p.add_argument("titles"); p.add_argument("--keywords"); p.set_defaults(fn=cmd_titles_check)
    p = ti.add_parser("choose"); p.add_argument("titles"); p.add_argument("--pick", type=int, required=True)
    p.set_defaults(fn=cmd_titles_choose)

    sc = sub.add_parser("script").add_subparsers(dest="sub", required=True)
    p = sc.add_parser("lint"); p.add_argument("script"); p.add_argument("--wpm", type=float); p.set_defaults(fn=cmd_script_lint)
    p = sc.add_parser("scenes"); p.add_argument("script"); p.add_argument("-o", "--output", required=True)
    p.add_argument("--min-words", type=int, default=18); p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_script_scenes)

    p = sub.add_parser("narrate"); p.add_argument("scenes"); p.add_argument("--voice"); p.add_argument("--model")
    p.add_argument("--dry-run", action="store_true"); p.add_argument("--yes", action="store_true")
    p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_narrate)
    p = sub.add_parser("retime"); p.add_argument("scenes"); p.set_defaults(fn=cmd_retime)

    vi = sub.add_parser("visuals").add_subparsers(dest="sub", required=True)
    p = vi.add_parser("plan"); p.add_argument("scenes"); p.set_defaults(fn=cmd_visuals_plan)

    p = sub.add_parser("render"); p.add_argument("scenes"); p.add_argument("--music"); p.add_argument("--music-db", type=float)
    p.add_argument("--size"); p.add_argument("--fps", type=int); p.add_argument("--font")
    p.add_argument("--no-captions", action="store_true"); p.add_argument("--draft", action="store_true")
    p.add_argument("-o", "--output"); p.set_defaults(fn=cmd_render)

    p = sub.add_parser("chapters"); p.add_argument("scenes"); p.add_argument("--upload"); p.set_defaults(fn=cmd_chapters)
    p = sub.add_parser("thumbnail"); p.add_argument("--image", required=True); p.add_argument("--text", required=True)
    p.add_argument("--font"); p.add_argument("--accent-line", type=int); p.add_argument("-o", "--output", required=True)
    p.set_defaults(fn=cmd_thumbnail)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd in {"render", "narrate", "retime"} and not shutil.which(FFPROBE):
        print("ERROR: ffprobe not found (set FFPROBE_PATH)", file=sys.stderr)
        return 1
    try:
        result = args.fn(args)
    except SoulError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if result is not None:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
