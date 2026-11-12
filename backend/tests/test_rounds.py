"""Round splitting and kill feed."""

import unittest

from oldschool.parser import goldsrc as gd
from tests.demo_factory import MATCH, ROUND_ID, build_round_demo, round_var, roundtime, text


class RoundTests(unittest.TestCase):
    def test_rounds_and_feed(self):
        r = gd.rounds(build_round_demo(MATCH))
        got = [(x["number"], x["start"], x["end"], x["winner"], x["reason"]) for x in r["rounds"]]
        self.assertEqual(
            got,
            [
                (1, 0.1, 30.0, "CT", "CTs_Win"),
                (2, 41.0, 60.0, "TERRORIST", "Target_Bombed"),
                (3, 86.0, 100.0, "TERRORIST", "Terrorists_Win"),
            ],
        )
        self.assertEqual(r["restarts"], [80.0])
        self.assertEqual(r["rounds"][1]["start_basis"], "RoundTime 180")
        k = r["rounds"][0]["kills"][0]
        self.assertEqual(
            (k["killer"], k["victim"], k["weapon"], k["headshot"]), ("aAa|KabaL", "GG.Eclair", "ak47", True)
        )
        self.assertEqual([len(x["kills"]) for x in r["rounds"]], [1, 1, 1])
        self.assertEqual(r["rounds"][1]["score_after"], {"CT": 1, "TERRORIST": 1})

    def test_fallback_start_without_roundtime(self):
        frames = [(t, m) for t, m in MATCH if not m.startswith(bytes([ROUND_ID["RoundTime"]]))]
        r = gd.rounds(build_round_demo(frames))
        self.assertEqual(r["rounds"][1]["start"], 35.0)
        self.assertTrue(r["rounds"][1]["start_basis"].startswith("end+"))

    def test_round_end_from_radio_sound_only(self):
        def audio(s):  # SendAudio-like payload
            return round_var("TextMsg", b"\x00\x00" + s + b"\x00")

        frames = [
            (2.0, roundtime(180)),
            (30.0, audio(b"%!MRAD_terwin")),
            (41.0, roundtime(180)),
            (60.0, audio(b"%!MRAD_ctwin") + text(b"#CTs_Win")),
        ]
        r = gd.rounds(build_round_demo(frames))
        got = [(x["end"], x["winner"], x["reason"]) for x in r["rounds"]]
        self.assertEqual(got, [(30.0, "TERRORIST", "Terrorists_Win"), (60.0, "CT", "CTs_Win")])


def test_demo_without_round_end():
    from tests.demo_factory import build_demo

    r = gd.rounds(build_demo(1, hltv=False))
    assert r["rounds"] == []
    assert len(r["other_kills"]) == 3
