import gzip
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from scripts.build_epg_v2 import build, parse_stamp, read_playlist_ids

NOW = datetime(2026, 11, 13, 17, tzinfo=timezone.utc)

def make_guide(channel, title="Real film", start="20261113180000 +0000", stop="20261113200000 +0000"):
    return (f'<tv><channel id="{channel}"><display-name>Sky Cinema Drama</display-name></channel>'
            f'<programme channel="{channel}" start="{start}" stop="{stop}">'
            f'<title>{title}</title></programme></tv>')

class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.a = self.dir / "first.xml"
        self.b = self.dir / "second.xml"
        self.alias = self.dir / "aliases.json"
        self.alias.write_text(json.dumps({"aliases": {}}))
        self.out = self.dir / "epg.xml"
        self.gz = self.dir / "epg.xml.gz"
        self.report = self.dir / "coverage.json"

    def run_build(self, sources=None, playlist=None):
        return build(sources or [self.a, self.b], self.alias, self.out, self.gz, self.report,
                     now=NOW, playlist_path=playlist)

    def test_retrieves_and_compresses(self):
        self.a.write_text(make_guide("SkyCinemaDrama.uk@HD"))
        result = self.run_build()
        self.assertEqual(result["programme_count"], 1)
        self.assertEqual(result["channels_with_future_programmes"], 1)
        with gzip.open(self.gz, "rb") as f:
            self.assertEqual(f.read(), self.out.read_bytes())

    def test_priority_preserves_first_source(self):
        self.a.write_text(make_guide("channel", title="First source"))
        self.b.write_text(make_guide("channel", title="Conflicting source"))
        self.run_build()
        self.assertEqual(ET.parse(self.out).getroot().find("programme/title").text, "First source")

    def test_explicit_alias_creates_matching_programme(self):
        self.a.write_text(make_guide("SkyCinemaDrama.uk@HD"))
        self.b.write_text('<tv><channel id="provider-drama"><display-name>Sky Cinema Drama HD</display-name></channel></tv>')
        self.alias.write_text(json.dumps({"aliases": {"provider-drama": "SkyCinemaDrama.uk@HD"}}))
        self.run_build()
        root = ET.parse(self.out).getroot()
        self.assertEqual(len([p for p in root.findall("programme") if p.get("channel") == "provider-drama"]), 1)

    def test_no_name_guessing(self):
        self.a.write_text(make_guide("SkyCinemaDrama.uk@HD"))
        self.b.write_text('<tv><channel id="unknown"><display-name>Sky Cinema Drama</display-name></channel></tv>')
        result = self.run_build()
        self.assertIn("unknown", result["channels_without_future_programmes"])

    def test_stale_output_refused(self):
        self.a.write_text(make_guide("channel", start="20200101180000 +0000", stop="20200101200000 +0000"))
        with self.assertRaisesRegex(ValueError, "stale"):
            self.run_build()

    def test_playlist_ids_report_unmatched(self):
        self.a.write_text(make_guide("SkyCinemaDrama.uk@HD"))
        playlist = self.dir / "sample.m3u"
        playlist.write_text('#EXTM3U\n#EXTINF:-1 tvg-id="provider-123",Sky Cinema Drama\n')
        result = self.run_build(playlist=playlist)
        self.assertEqual(result["unmatched_playlist_ids"], ["provider-123"])

    def test_timezone_and_offsets(self):
        self.assertEqual(parse_stamp("20261113120000 -0500"), datetime(2026, 11, 13, 17, tzinfo=timezone.utc))
        with self.assertRaises(ValueError):
            parse_stamp("20261113120000")

if __name__ == "__main__":
    unittest.main()
