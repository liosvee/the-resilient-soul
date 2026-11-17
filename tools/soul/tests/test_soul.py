"""Offline tests for tools/soul/soul.py — no network, no paid calls.

python3 -m unittest discover -s tools/soul/tests -v
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
import soul  # noqa: E402

FIXTURE = HERE / "fixtures" / "keyword-research-stoicism.md"
HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))

SCRIPT = """# 7 Stoic Teachings to Heal When You Feel Broken

## When everything falls apart
[visual: rain on a dark window, a figure sitting alone]
You did everything right, and it still fell apart. Maybe you are wondering if you will ever feel whole again. Today you'll learn seven stoic teachings that turn that pain into quiet strength.

## Teaching one: the dichotomy of control
[visual: hands opening to release sand into the wind]
Epictetus taught that some things are within our power and some are not. Your peace begins the moment you stop fighting what you cannot change.

Tonight, write two lists. What you control, and what you don't. Then put the second list down.

## Teaching two: the view from above
[visual: a city at night seen from a mountain]
Marcus Aurelius wrote, "Look back over the past, with its changing empires." Seen from far enough away, this moment is small, and you are larger than it.

## Closing
[visual: sunrise over the sea]
Pain is not the end of your story. It is where your strength begins. If this helped, subscribe and tell me in the comments which teaching you'll practise first.
"""


def synthetic_alignment(text: str, seconds: float) -> dict:
    chars = list(text)
    step = seconds / max(1, len(chars))
    return {"characters": chars,
            "character_start_times_seconds": [i * step for i in range(len(chars))],
            "character_end_times_seconds": [(i + 1) * step for i in range(len(chars))]}


class KeywordTests(unittest.TestCase):
    def test_parses_markdown_tables_with_escaped_pipes(self):
        rows = soul.parse_keyword_rows(FIXTURE.read_text())
        self.assertEqual(len(rows), 26)
        self.assertIn("10 stoic lessons to become emotionally untouchable |stoicism philosophy",
                      [r["keyword"] for r in rows])
        self.assertEqual(rows[0]["section"], "seedKeyword")

    def test_parses_json(self):
        rows = soul.parse_keyword_rows(json.dumps({"relatedKeywords": [{"keyword": "stoic calm", "volume": 50,
                                                                        "competition": 20, "overall": 60}]}))
        self.assertEqual(rows[0]["keyword"], "stoic calm")

    def test_rank_filters_and_orders(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "keywords.json"
            ns = soul.build_parser().parse_args(["keywords", "rank", str(FIXTURE), "-o", str(out)])
            soul.cmd_keywords_rank(ns)
            data = json.loads(out.read_text())
            kws = [k["keyword"] for k in data["primary_candidates"]]
            self.assertEqual(kws[0], "stoicism")
            self.assertNotIn("how to practice stoicism", kws)            # volume 0
            self.assertNotIn("ryan holiday stoicism", kws[:3])
            self.assertTrue(all(not k["title_like"] for k in data["primary_candidates"]))
            self.assertEqual(len(data["title_patterns"]), 2)
            growth = {k["keyword"]: k for k in data["primary_candidates"]}
            self.assertGreater(growth["marcus aurelius meditations"]["opportunity"], 63)  # +77% growth nudge
            self.assertTrue(out.with_suffix(".md").exists())

    def test_unknown_values_stay_unknown(self):
        self.assertIsNone(soul._num("null"))
        self.assertEqual(soul._num("<750"), 375.0)
        self.assertEqual(soul._num("+56.3%"), 56.3)


class TitleTests(unittest.TestCase):
    def good(self):
        return {"primary_keyword": "stoic teachings", "titles": [
            {"title": "7 Stoic Teachings to Heal When You Feel Broken", "vidiq_score": 71},
            {"title": "Why Stoic Teachings Work Best in Your Darkest Hour", "vidiq_score": 66},
            {"title": "Marcus Aurelius' Stoic Teachings for Letting Go", "vidiq_score": 68}]}

    def test_three_distinct_keyword_titles_pass(self):
        self.assertEqual(soul.check_titles(self.good())["status"], "OK")

    def test_fewer_than_three_fails(self):
        d = self.good(); d["titles"] = d["titles"][:2]
        self.assertEqual(soul.check_titles(d)["status"], "ERROR")

    def test_missing_keyword_and_duplicates_fail(self):
        d = self.good()
        d["titles"].append({"title": "How to Feel Better Tonight"})
        d["titles"].append({"title": "7 Stoic Teachings to Heal When You Feel Broken!"})
        errs = " ".join(soul.check_titles(d)["errors"])
        self.assertIn("not in title", errs)
        self.assertIn("alike", errs)

    def test_choose_writes_upload(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "titles.json"; p.write_text(json.dumps(self.good()))
            soul.cmd_titles_choose(soul.build_parser().parse_args(["titles", "choose", str(p), "--pick", "2"]))
            self.assertEqual(json.loads(p.read_text())["chosen"]["n"], 2)
            self.assertIn("Darkest Hour", json.loads((Path(td) / "upload.json").read_text())["title"])


class ScriptTests(unittest.TestCase):
    def test_lint_finds_chapters_and_quotes(self):
        r = soul.lint_script(SCRIPT, 140, (0.5, 12))
        self.assertEqual(r["status"], "OK" if not r["warnings"] else "WARN")
        self.assertEqual(len(r["chapters"]), 4)
        self.assertEqual(len(r["verify_quotes"]), 1)
        self.assertFalse(any("call to action" in w for w in r["warnings"]))

    def test_scenes_merge_short_paragraphs_and_keep_visuals(self):
        d = soul.build_scenes(SCRIPT)
        self.assertEqual(d["title"], "7 Stoic Teachings to Heal When You Feel Broken")
        self.assertEqual(len(d["scenes"]), 4)   # the short "write two lists" paragraph merges
        self.assertIn("rain", d["scenes"][0]["visual_prompt"])
        self.assertTrue(all(s["audio"].startswith("audio/") for s in d["scenes"]))


class CaptionTests(unittest.TestCase):
    def test_alignment_to_chunks(self):
        al = synthetic_alignment("Pain is not the end. It is where your strength begins.", 4.0)
        words = soul.words_from_alignment(al)
        self.assertEqual(words[0]["word"], "Pain")
        chunks = soul.caption_chunks(words)
        self.assertEqual(chunks[0]["text"], "Pain is not the end.")
        self.assertTrue(all(len(c["text"]) <= 34 for c in chunks))
        self.assertTrue(all(a["end"] <= b["start"] + 1e-6 or a["end"] <= a["end"] for a, b in zip(chunks, chunks[1:])))


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg/ffprobe not installed")
class RenderTests(unittest.TestCase):
    def make_project(self, td: Path) -> Path:
        p = td / "proj"
        soul.cmd_init(soul.build_parser().parse_args(["init", str(p), "--slug", "test-video"]))
        (p / "script.md").write_text(SCRIPT)
        soul.cmd_script_scenes(soul.build_parser().parse_args(["script", "scenes", str(p / "script.md"),
                                                               "-o", str(p / "scenes.json")]))
        data = json.loads((p / "scenes.json").read_text())
        for i, s in enumerate(data["scenes"]):
            secs = 2.0 + 0.5 * i
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=f={220 + 60 * i}:d={secs}",
                            "-c:a", "libmp3lame", str(p / s["audio"])], check=True)
            (p / s["alignment"]).write_text(json.dumps(synthetic_alignment(s["text"][:80], secs)))
        from PIL import Image
        Image.new("RGB", (640, 360), (90, 70, 50)).save(p / "visuals" / "scene-001.png")
        Image.new("RGB", (400, 400), (20, 40, 80)).save(p / "visuals" / "scene-003.jpg")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=s=320x240:r=30:d=1",
                        "-pix_fmt", "yuv420p", str(p / "visuals" / "scene-002.mp4")], check=True)
        Image.new("RGB", (640, 360), (200, 180, 120)).save(p / "visuals" / "scene-004.png")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=f=110:d=3",
                        "-c:a", "libmp3lame", str(p / "music" / "bed.mp3")], check=True)
        return p

    def test_render_end_to_end_and_packaging(self):
        with tempfile.TemporaryDirectory() as td:
            p = self.make_project(Path(td))
            res = soul.cmd_render(soul.build_parser().parse_args(["render", str(p / "scenes.json"),
                                                                 "--size", "320x180", "--fps", "15"]))
            out = Path(res["render"])
            self.assertTrue(out.exists())
            self.assertEqual(out.name, "test-video-v1.mp4")
            self.assertAlmostEqual(res["seconds"], res["planned_seconds"], delta=0.35)
            probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(out)],
                                              capture_output=True, text=True).stdout)
            v = next(s for s in probe["streams"] if s["codec_type"] == "video")
            self.assertEqual((v["width"], v["height"]), (320, 180))
            # a second render never overwrites
            res2 = soul.cmd_render(soul.build_parser().parse_args(["render", str(p / "scenes.json"),
                                                                  "--size", "320x180", "--fps", "15", "--no-captions"]))
            self.assertTrue(res2["render"].endswith("-v2.mp4"))
            ch = soul.cmd_chapters(soul.build_parser().parse_args(["chapters", str(p / "scenes.json"),
                                                                  "--upload", str(p / "upload.json")]))
            self.assertTrue(ch["chapters"].startswith("0:00 When everything falls apart"))
            self.assertIn("Chapters", json.loads((p / "upload.json").read_text())["description"])
            th = soul.cmd_thumbnail(soul.build_parser().parse_args(["thumbnail", "--image", str(p / "visuals/scene-001.png"),
                                                                   "--text", "You Are Not Broken", "-o", str(p / "thumbnail.png")]))
            self.assertEqual(th["size"], "1280x720")
            st = soul.project_status(p)
            self.assertTrue(st["done"]["render"] and st["done"]["visuals"] and st["done"]["narration"])

    def test_missing_visual_needs_draft(self):
        with tempfile.TemporaryDirectory() as td:
            p = self.make_project(Path(td))
            (p / "visuals" / "scene-004.png").unlink()
            with self.assertRaises(soul.SoulError):
                soul.cmd_render(soul.build_parser().parse_args(["render", str(p / "scenes.json"), "--size", "320x180"]))
            res = soul.cmd_render(soul.build_parser().parse_args(["render", str(p / "scenes.json"), "--size", "320x180",
                                                                 "--fps", "15", "--draft"]))
            self.assertIn("draft", res["render"])

    def test_learning_gate_blocks_unapplied_final_render_and_narration(self):
        with tempfile.TemporaryDirectory() as td:
            p = self.make_project(Path(td))
            sys.path.insert(0, str(ROOT))
            from evolution.learn import Learning
            Learning().begin(p, "Synthetic gate test", "en", "US", "long")
            with self.assertRaises(soul.SoulError) as cm:
                soul.cmd_render(soul.build_parser().parse_args(["render", str(p / "scenes.json"), "--size", "320x180"]))
            self.assertIn("Learning not applied", str(cm.exception))

    def test_narrate_dry_run_and_spend_guard(self):
        with tempfile.TemporaryDirectory() as td:
            p = self.make_project(Path(td))
            r = soul.cmd_narrate(soul.build_parser().parse_args(["narrate", str(p / "scenes.json"), "--voice", "v1",
                                                                "--dry-run"]))
            self.assertEqual(r["scenes_to_generate"], 4)   # voice changed → all scenes due
            self.assertGreater(r["characters"], 100)
            with self.assertRaises(soul.SoulError) as cm:
                soul.cmd_narrate(soul.build_parser().parse_args(["narrate", str(p / "scenes.json"), "--voice", "v1"]))
            self.assertIn("--yes", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
