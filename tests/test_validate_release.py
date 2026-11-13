import gzip
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from scripts.validate_release import validate

NOW = datetime(2026, 11, 13, 15, tzinfo=timezone.utc)
START = "20261113150000 +0000"
STOP = "20261113160000 +0000"

def guide(channels=("a",), with_programme=True, title="Verified programme"):
    ch = "".join(f'<channel id="{c}"><display-name>{c}</display-name></channel>' for c in channels)
    ps = "".join(f'<programme channel="{c}" start="{START}" stop="{STOP}"><title>{title}</title></programme>' for c in channels) if with_programme else ""
    return f'<?xml version="1.0"?><tv>{ch}{ps}</tv>'

class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.old = self.folder / "old.xml"
        self.new = self.folder / "new.xml"
        self.old.write_text(guide(("a", "b")), encoding="utf-8")
        self.new.write_text(guide(("a", "b")), encoding="utf-8")

    def check(self, xml, error):
        self.new.write_text(xml, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, error):
            validate(self.new, self.old, now=NOW)

    def test_unchanged_release_passes(self):
        self.assertEqual(validate(self.new, self.old, now=NOW)["status"], "PASS")

    def test_removed_channel_id_fails(self):
        self.check(guide(("a",)), "channel ID regression")

    def test_orphan_programmes_fail(self):
        xml = guide(("a", "b")).replace('programme channel="b"', 'programme channel="missing"')
        self.check(xml, "undeclared IDs")

    def test_invalid_xml_fails(self):
        self.new.write_text("<tv><channel>", encoding="utf-8")
        with self.assertRaises(Exception):
            validate(self.new, self.old, now=NOW)

    def test_no_future_programmes_fails(self):
        self.check(guide(("a", "b")).replace("20261113", "20250101"), "no current or upcoming")

    def test_overlapping_programmes_fail(self):
        xml = guide(("a", "b")).replace("</tv>", f'<programme channel="a" start="{START}" stop="{STOP}"><title>Other</title></programme></tv>')
        self.check(xml, "overlapping")

    def test_titleless_programmes_fail(self):
        self.check(guide(("a", "b"), title=""), "lack titles")

    def test_compressed_output_verified(self):
        zipped = self.folder / "epg.xml.gz"
        with gzip.open(zipped, "wb") as fh:
            fh.write(self.new.read_bytes())
        self.assertEqual(validate(self.new, self.old, zipped, now=NOW)["status"], "PASS")
        with gzip.open(zipped, "wb") as fh:
            fh.write(b"wrong content")
        with self.assertRaisesRegex(ValueError, "differs"):
            validate(self.new, self.old, zipped, now=NOW)

if __name__ == "__main__":
    unittest.main()
