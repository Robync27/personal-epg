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
            baseline.write_text('<tv><channel id="old"><display-name>Original</display-name></channel>'
                                '<programme channel="old" start="20261113180000 +0000" '
                                'stop="20261113200000 +0000"><title>A</title></programme></tv>')
            candidate.write_text('<tv><channel id="old"><display-name>Changed</display-name></channel>'
                                 '<channel id="provider"><display-name>Provider name</display-name></channel>'
                                 '<programme channel="old" start="20261113180000 +0000" '
                                 'stop="20261113200000 +0000"><title>B</title></programme>'
                                 '<programme channel="provider" start="20261113180000 +0000" '
                                 'stop="20261113200000 +0000"><title>B</title></programme></tv>')
            self.assertEqual(preserve(candidate, baseline), 1)
            root = ET.parse(candidate).getroot()
            self.assertEqual(root.find("channel[@id='old']/display-name").text, "Original")
            self.assertEqual(root.find("channel[@id='provider']/display-name").text, "Provider name")
            self.assertEqual(root.find("programme[@channel='old']/title").text, "B")
            self.assertEqual(preserve(candidate, baseline), 0)

if __name__ == "__main__":
    unittest.main()
