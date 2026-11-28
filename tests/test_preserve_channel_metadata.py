import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from scripts.preserve_channel_metadata import preserve


class PreservationTests(unittest.TestCase):
    def test_preserves_existing_metadata_and_keeps_new_alias(self):
        with tempfile.TemporaryDirectory() as d:
            baseline = Path(d) / "baseline.xml"
            candidate = Path(d) / "candidate.xml"
            baseline.write_text(
                '<tv><channel id="old"><display-name>Original</display-name></channel>'
                '<programme channel="old" start="20261113180000 +0000" '
                'stop="20261113200000 +0000"><title>A</title></programme></tv>'
            )
            candidate.write_text(
                '<tv><channel id="old"><display-name>Changed</display-name></channel>'
                '<channel id="provider"><display-name>Provider name</display-name></channel>'
                '<programme channel="old" start="20261113180000 +0000" '
                'stop="20261113200000 +0000"><title>B</title></programme>'
                '<programme channel="provider" start="20261113180000 +0000" '
                'stop="20261113200000 +0000"><title>B</title></programme></tv>'
            )
            self.assertEqual(preserve(candidate, baseline), 1)
            root = ET.parse(candidate).getroot()
            self.assertEqual(root.find("channel[@id='old']/display-name").text, "Original")
            self.assertEqual(root.find("channel[@id='provider']/display-name").text, "Provider name")
            self.assertEqual(root.find("programme[@channel='old']/title").text, "B")
            self.assertEqual(preserve(candidate, baseline), 0)

    def test_restores_missing_legacy_ids_without_copying_stale_programmes(self):
        with tempfile.TemporaryDirectory() as d:
            baseline = Path(d) / "baseline.xml"
            candidate = Path(d) / "candidate.xml"
            baseline.write_text(
                '<tv>'
                '<channel id="legacy"><display-name>Legacy Channel</display-name></channel>'
                '<channel id="legacy-two"><display-name>Legacy Two</display-name></channel>'
                '<programme channel="legacy" start="20261113180000 +0000" '
                'stop="20261113200000 +0000"><title>Old schedule</title></programme>'
                '</tv>'
            )
            candidate.write_text(
                '<tv>'
                '<channel id="new"><display-name>New Channel</display-name></channel>'
                '<programme channel="new" start="20261113180000 +0000" '
                'stop="20261113200000 +0000"><title>Current schedule</title></programme>'
                '</tv>'
            )

            self.assertEqual(preserve(candidate, baseline), 2)
            root = ET.parse(candidate).getroot()
            self.assertIsNotNone(root.find("channel[@id='legacy']"))
            self.assertIsNotNone(root.find("channel[@id='legacy-two']"))
            self.assertIsNotNone(root.find("channel[@id='new']"))
            self.assertIsNone(root.find("programme[@channel='legacy']"))
            self.assertIsNone(root.find("programme[@channel='legacy-two']"))
            self.assertEqual(root.find("programme[@channel='new']/title").text, "Current schedule")

            # Idempotent: a second pass must not change the guide.
            self.assertEqual(preserve(candidate, baseline), 0)


if __name__ == "__main__":
    unittest.main()
