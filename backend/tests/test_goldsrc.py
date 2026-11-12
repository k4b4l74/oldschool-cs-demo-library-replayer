"""Parser tests on synthetic demos."""

import struct
import unittest

from oldschool.parser import goldsrc as gd
from tests.demo_factory import build_demo


class ParserTests(unittest.TestCase):
    def test_hltv_demo(self):
        r = gd.analyse(build_demo())
        self.assertEqual(r["header"]["map"], "de_dust2")
        self.assertEqual(r["server"]["hostname"], "Test LAN #1")
        self.assertTrue(r["server"]["layout_confirmed"])
        self.assertEqual(r["recorder"]["kind"], "hltv")
        self.assertEqual(r["server_names"], ["Test LAN HLTV"])
        self.assertEqual(r["kill_count"], 3)
        self.assertEqual(r["kills"][0]["killer_name"], "aAa|KabaL")
        self.assertTrue(r["kills"][0]["headshot"])
        self.assertEqual(r["final_score"], {"CT": 1, "TERRORIST": 13})
        tags = {t["tag"]: t["sides"] for t in r["teams"]}
        self.assertEqual(tags, {"aAa": ["CT", "TERRORIST"], "GG": ["TERRORIST", "CT"]})
        self.assertIn("gg", r["chat"][0]["text"])
        self.assertEqual(r["duration_seconds"], 949.5)

    def test_player_pov_and_steamids(self):
        r = gd.analyse(build_demo(recorder_slot=1, hltv=False, steam=True))
        self.assertEqual(r["recorder"]["kind"], "player")
        self.assertEqual(r["recorder"]["name"], "aAa|KabaL")
        self.assertEqual(r["recorder"]["sides"], ["CT", "TERRORIST"])
        kabal = r["players"][0]
        self.assertEqual(kabal["steamid"], "STEAM_0:1:1")
        self.assertEqual((kabal["kills"], kabal["headshots"]), (1, 1))

    def test_missing_directory_is_walked(self):
        data = bytearray(build_demo())
        struct.pack_into("<i", data, 540, 0)
        r = gd.analyse(bytes(data))
        self.assertEqual(r["kill_count"], 3)
        self.assertTrue(any("directory" in p for p in r["problems"]))

    def test_resync_after_corrupt_frame(self):
        data = bytearray(build_demo())
        # Break the length field of the first kill frame (time 10.0).
        marker = struct.pack("<Bf", 1, 10.0)
        at = data.find(marker)
        struct.pack_into("<i", data, at + 9 + gd.NETMSG_PREFIX, 0x7FFFFFF0)
        r = gd.analyse(bytes(data))
        self.assertTrue(any(p.startswith("resynchronised") for p in r["problems"]))
        self.assertEqual(r["kill_count"], 1)  # kills after the damage survive
        self.assertEqual(r["kills"][0]["weapon"], "deagle")

    def test_cs13_team_names(self):
        demo = build_demo().replace(b"TERRORIST\x00", b"Terrorist\x00")
        r = gd.analyse(demo)
        self.assertEqual(r["final_score"], {"CT": 1, "TERRORIST": 13})

    def test_truncated_demo(self):
        data = build_demo()
        r = gd.analyse(data[: len(data) // 2])
        self.assertIn("players", r)

    def test_not_a_demo(self):
        with self.assertRaises(gd.DemoError):
            gd.analyse(b"PK\x03\x04" + b"\x00" * 600)

    def test_names(self):
        self.assertEqual(gd.clan_tag(["3D.Moore <Jaden>", "3D.miller", "3D.Kim [Rambo]", "3D.Morgan<bullseye>"]), "3D")
        self.assertEqual(gd.clan_tag(["[1st~Yen] <Menace>", "[1st~AniszczyK] <zx>", "[1st~Benger] <shaGuar>"]), "1st")
        self.assertEqual(gd.clan_tag(["KabaL.GG", "eclair.GG", "moon"]), "GG")
        self.assertIsNone(gd.clan_tag(["alpha", "beta", "gamma"]))
        self.assertEqual(gd.display_alias("3D.Morgan<bullseye>", "3D"), "bullseye")
        self.assertEqual(gd.display_alias("aAa|KabaL", "aAa"), "KabaL")
        self.assertEqual(gd.display_alias("*aAa* Emkill <3 Sophie", "aAa"), "Emkill <3 Sophie")
