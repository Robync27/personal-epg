import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from scripts.recover_verified_aliases import apply_aliases


class AliasRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "epg.xml"
        self.cfg = Path(self.tmp.name) / "aliases.json"
        self.cfg.write_text(json.dumps({"aliases": {"missing": "source"}}))
        self.path.write_text(
            '<tv><channel id="source"><display-name>Same TV</display-name></channel>'
            '<channel id="missing"><display-name>Same TV HD</display-name></channel>'
            '<programme channel="source" start="20261113120000 -0500" stop="20261113130000 -0500">'
            '<title>Genuine listing</title></programme></tv>'
        )

    def programmes(self):
        return [(p.get("channel"), p.findtext("title")) for p in ET.parse(self.path).getroot().findall("programme")]

    def test_source_recovered_with_original_id_preserved(self):
        out = apply_aliases(self.path, self.cfg)
        self.assertEqual(out["missing"]["status"], "recovered")
        self.assertEqual(self.programmes(), [("source", "Genuine listing"), ("missing", "Genuine listing")])

    def test_idempotent_no_duplicate_programmes(self):
        apply_aliases(self.path, self.cfg)
        out = apply_aliases(self.path, self.cfg)
        self.assertEqual(out["missing"]["status"], "already_has_schedule")
        self.assertEqual(len(self.programmes()), 2)

    def test_does_not_overwrite_existing_schedule(self):
        root = ET.parse(self.path).getroot()
        ET.SubElement(root, "programme", channel="missing", start="20261113130000 -0500",
                      stop="20261113140000 -0500").append(ET.Element("title"))
        root[-1].find("title").text = "Existing verified entry"
        ET.ElementTree(root).write(self.path, encoding="utf-8")
        out = apply_aliases(self.path, self.cfg)
        self.assertEqual(out["missing"]["status"], "already_has_schedule")
        self.assertEqual(len(self.programmes()), 2)

    def test_missing_source_skips_without_mutation(self):
        original = self.path.read_bytes()
        self.cfg.write_text(json.dumps({"aliases": {"missing": "not-in-guide"}}))
        self.assertEqual(apply_aliases(self.path, self.cfg)["missing"]["status"], "missing_channel_id")
        self.assertEqual(self.path.read_bytes(), original)

    def test_empty_source_skips_without_mutation(self):
        root = ET.parse(self.path).getroot()
        root.remove(root.find("programme"))
        ET.ElementTree(root).write(self.path)
        original = self.path.read_bytes()
        self.assertEqual(apply_aliases(self.path, self.cfg)["missing"]["status"], "source_has_no_schedule")
        self.assertEqual(self.path.read_bytes(), original)

    def test_self_mapping_refused(self):
        self.cfg.write_text(json.dumps({"aliases": {"source": "source"}}))
        with self.assertRaisesRegex(ValueError, "Invalid alias"):
            apply_aliases(self.path, self.cfg)

if __name__ == "__main__":
    unittest.main()
