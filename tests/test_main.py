"""Tests for the command-line program: saved progress and whole sessions.

Every test points XDG_DATA_HOME at a temporary directory, so the real
progress file in the user's home is never read or written.
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main  # noqa: E402


def deck(name):
    with (ROOT / "json" / (name + ".json")).open(encoding="utf-8") as f:
        return json.load(f)["cards"]


ANSWERS = {c["front"]: c["back"] for c in deck("kana")}


class TempDataDir(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_home = Path(tmp.name)
        env = mock.patch.dict(os.environ, {"XDG_DATA_HOME": tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.path = self.data_home / "ankikado" / "progress.json"

    def saved_cards(self):
        with self.path.open(encoding="utf-8") as f:
            return json.load(f)["cards"]


class Session:
    """Runs main.main() with scripted keyboard input and captured output.

    The clock is faked too: each answer takes `pace` seconds, starting at
    `start`. `fronts` lists the card shown at each prompt, in order.
    """

    def __init__(self, argv, replies, start=1700000000.0, pace=3.0):
        self.argv = argv
        self.replies = list(replies)
        self.clock = start
        self.pace = pace
        self.fronts = []
        self.out = io.StringIO()
        self.exit_code = None

    def _input(self, prompt=""):
        front = self.out.getvalue().rstrip("\n").split("\n")[-1].split()[0]
        if not self.replies:
            raise AssertionError("program asked for more input than scripted")
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        self.fronts.append(front)
        self.clock += self.pace
        return reply(front) if callable(reply) else reply

    def run(self):
        with mock.patch("builtins.input", self._input), \
                mock.patch("time.time", lambda: self.clock), \
                mock.patch.object(main, "clear_cli", lambda: None), \
                contextlib.redirect_stdout(self.out):
            try:
                main.main(self.argv)
            except SystemExit as e:
                self.exit_code = e.code or 0
        return self

    @property
    def output(self):
        return self.out.getvalue()


def right(front):
    return ANSWERS[front]


def wrong(front):
    return "zzz"


class ProgressFileTests(TempDataDir):
    def test_progress_lives_under_xdg_data_home(self):
        self.assertEqual(main.progress_path(), self.path)

    def test_progress_defaults_to_local_share_in_home(self):
        with mock.patch.dict(os.environ, {"HOME": "/home/someone"}):
            os.environ.pop("XDG_DATA_HOME")
            self.assertEqual(
                main.progress_path(),
                Path("/home/someone/.local/share/ankikado/progress.json"),
            )

    def test_missing_file_means_no_progress(self):
        self.assertEqual(main.load_progress(self.path), ({}, None))

    def test_saved_progress_loads_back_identically(self):
        progress = {"あ\ta": {"stability": 42.5, "last_seen": 1700000000.0,
                              "seen": 3, "missed": 1}}
        self.assertTrue(main.save_progress(self.path, progress))
        self.assertEqual(main.load_progress(self.path), (progress, None))

    def test_corrupt_file_is_set_aside_not_destroyed(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{ not json", encoding="utf-8")
        progress, backup = main.load_progress(self.path)
        self.assertEqual(progress, {})
        self.assertEqual(Path(backup).read_text(encoding="utf-8"), "{ not json")
        self.assertFalse(self.path.exists())

    def test_wrong_shape_file_is_treated_as_corrupt(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("[1, 2, 3]", encoding="utf-8")
        progress, backup = main.load_progress(self.path)
        self.assertEqual(progress, {})
        self.assertIsNotNone(backup)

    def test_malformed_entries_are_dropped_and_good_ones_kept(self):
        good = {"stability": 10.0, "last_seen": 5.0, "seen": 1, "missed": 0}
        cards = {
            "good\tg": good,
            "not a dict\tx": 7,
            "zero stability\tx": dict(good, stability=0),
            "negative stability\tx": dict(good, stability=-3.0),
            "text stability\tx": dict(good, stability="soon"),
            "no last_seen\tx": {"stability": 10.0},
            "nan stability\tx": dict(good, stability=float("nan")),
        }
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({"version": 1, "cards": cards}), encoding="utf-8")
        progress, backup = main.load_progress(self.path)
        self.assertEqual(progress, {"good\tg": good})
        self.assertIsNone(backup)

    def test_entry_without_counters_gets_zero_counters(self):
        cards = {"あ\ta": {"stability": 10.0, "last_seen": 5.0}}
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({"version": 1, "cards": cards}), encoding="utf-8")
        progress, _ = main.load_progress(self.path)
        self.assertEqual(progress["あ\ta"]["seen"], 0)
        self.assertEqual(progress["あ\ta"]["missed"], 0)

    def test_save_failure_is_reported_not_raised(self):
        blocker = self.data_home / "blocker"
        blocker.write_text("a file where a directory is needed")
        self.assertFalse(main.save_progress(blocker / "progress.json", {}))

    def test_save_leaves_no_temporary_files_behind(self):
        main.save_progress(self.path, {})
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["progress.json"])


class SessionTests(TempDataDir):
    def test_answers_are_saved_when_typing_exit(self):
        s = Session(["-h"], [right] * 5 + ["exit"]).run()
        self.assertEqual(s.exit_code, 0)
        self.assertEqual(len(self.saved_cards()), 5)
        self.assertIn("Score: 5/5", s.output)

    def test_answers_are_saved_on_ctrl_c(self):
        s = Session(["-h"], [right, right, KeyboardInterrupt()]).run()
        self.assertEqual(s.exit_code, 0)
        self.assertEqual(len(self.saved_cards()), 2)
        self.assertIn("Score: 2/2", s.output)

    def test_answers_are_saved_on_end_of_input(self):
        s = Session(["-h"], [right, right, right, EOFError()]).run()
        self.assertEqual(s.exit_code, 0)
        self.assertEqual(len(self.saved_cards()), 3)

    def test_progress_is_saved_after_every_answer(self):
        seen_on_disk = []

        def right_and_peek(front):
            seen_on_disk.append(len(self.saved_cards()) if self.path.exists() else 0)
            return ANSWERS[front]

        Session(["-h"], [right_and_peek] * 3 + ["exit"]).run()
        self.assertEqual(seen_on_disk, [0, 1, 2])

    def test_next_session_remembers_what_was_already_seen(self):
        first = Session(["-h"], [right] * 30 + ["exit"]).run()
        second = Session(["-h"], [right] * 30 + ["exit"], start=first.clock + 3600).run()
        answered = first.fronts[:30] + second.fronts[:30]
        self.assertEqual(len(set(answered)), 60)

    def test_hiragana_progress_carries_over_to_the_combined_deck(self):
        Session(["-h"], [right] * 71 + ["exit"]).run()
        combined = Session([], [right] * 20 + ["exit"]).run()
        hiragana = {c["front"] for c in deck("hiragana")}
        self.assertFalse(hiragana & set(combined.fronts))

    def test_wrong_answer_shows_the_right_one_and_is_listed_at_exit(self):
        s = Session(["-h"], [wrong, "exit"]).run()
        front = s.fronts[0]
        self.assertIn("Incorrect\n" + front + ": " + ANSWERS[front], s.output)
        summary = s.output[s.output.rindex("Score: 0/1"):]
        self.assertIn("Incorrect list:", summary)
        self.assertIn(front + ": " + ANSWERS[front], summary)

    def test_missed_card_is_the_first_to_come_back(self):
        s = Session(["-h"], [wrong] + [right] * 75 + ["exit"]).run()
        missed = s.fronts[0]
        first_repeat = next(f for i, f in enumerate(s.fronts) if f in s.fronts[:i])
        self.assertEqual(first_repeat, missed)

    def test_answer_is_accepted_with_stray_spaces_and_capitals(self):
        s = Session(["-h"], [lambda f: "  " + ANSWERS[f].upper() + " ", "exit"]).run()
        self.assertIn("Score: 1/1", s.output)

    def test_exit_command_is_not_counted_as_an_answer(self):
        s = Session(["-h"], [right, " EXIT "]).run()
        self.assertEqual(s.exit_code, 0)
        self.assertIn("Score: 1/1", s.output)
        self.assertEqual(len(self.saved_cards()), 1)

    def test_session_survives_an_unwritable_progress_location(self):
        (self.data_home / "ankikado").write_text("a file where a directory is needed")
        s = Session(["-h"], [right, right, "exit"]).run()
        self.assertEqual(s.exit_code, 0)
        self.assertIn("Score: 2/2", s.output)
        self.assertIn("could not be saved", s.output)

    def test_session_survives_a_corrupt_progress_file(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("garbage", encoding="utf-8")
        s = Session(["-h"], [right, "exit"]).run()
        self.assertEqual(s.exit_code, 0)
        self.assertEqual(len(self.saved_cards()), 1)


class ResetTests(TempDataDir):
    def test_reset_forgets_only_the_selected_deck(self):
        Session(["-h"], [right] * 4 + ["exit"]).run()
        Session(["-k"], [right] * 6 + ["exit"]).run()
        self.assertEqual(len(self.saved_cards()), 10)

        s = Session(["-h", "--reset"], []).run()

        self.assertEqual(s.exit_code, 0)
        katakana = {c["front"] for c in deck("katakana")}
        left = {key.split("\t")[0] for key in self.saved_cards()}
        self.assertEqual(len(left), 6)
        self.assertTrue(left <= katakana)

    def test_reset_with_no_saved_progress_is_harmless(self):
        s = Session(["--reset"], []).run()
        self.assertEqual(s.exit_code, 0)


class InstalledCommandTests(unittest.TestCase):
    def test_scheduler_is_found_when_only_main_is_importable(self):
        # An installed `ankikado` command may know only where main.py is
        # (installs made before scheduler.py existed), not its folder.
        load_main_by_path = (
            "import importlib.util, sys\n"
            "spec = importlib.util.spec_from_file_location('main', sys.argv[1])\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(module)\n"
            "module.main(['--help'])\n"
        )
        with tempfile.TemporaryDirectory() as elsewhere:
            result = subprocess.run(
                [sys.executable, "-I", "-c", load_main_by_path, str(ROOT / "main.py")],
                cwd=elsewhere, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--hiragana", result.stdout)


if __name__ == "__main__":
    unittest.main()
