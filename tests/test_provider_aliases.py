import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from scripts.add_provider_aliases import apply

class ProviderAliasTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        self.path = d / "guide.xml"
        self.config = d / "provider.json"
        self.path.write_text(
            '<tv><channel id="SkyCinemaDrama.uk@HD"><display-name>Sky Cinema Drama HD</display-name></channel>'
            '<programme channel="SkyCinemaDrama.uk@HD" start="20261113180000 +0000" stop="20261113200000 +0000">'
            '<title>Real movie</title></programme></tv>', encoding="utf-8")
        self.config.write_text(json.dumps({"aliases": {
            "SkyCinemaDrama.uk": {"label": "Sky Cinema Drama",
                                  "source_ids": ["SkyCinemaDrama.uk@HD"]}}}))

    def test_creates_provider_id_and_preserves_source(self):
        self.assertEqual(apply(self.path, self.config)["SkyCinemaDrama.uk"]["status"], "mapped")
        root = ET.parse(self.path).getroot()
        self.assertEqual(len(root.findall("channel")), 2)
        ids = [p.get("channel") for p in root.findall("programme")]
        self.assertEqual(set(ids), {"SkyCinemaDrama.uk@HD", "SkyCinemaDrama.uk"})
        self.assertTrue(all(p.findtext("title") == "Real movie" for p in root.findall("programme")))

    def test_repeated_run_does_not_duplicate(self):
        apply(self.path, self.config)
        self.assertEqual(apply(self.path, self.config)["SkyCinemaDrama.uk"]["status"], "already_has_programmes")
        self.assertEqual(len(ET.parse(self.path).getroot().findall("programme")), 2)

    def test_no_guessed_fallback(self):
        self.config.write_text(json.dumps({"aliases": {
            "BadGuess.uk": {"label": "Sky Cinema Drama", "source_ids": ["absent"]}}}))
        self.assertEqual(apply(self.path, self.config)["BadGuess.uk"]["status"], "source_missing_or_empty")
        self.assertEqual(len(ET.parse(self.path).getroot().findall("channel")), 1)

if __name__ == "__main__":
    unittest.main()
