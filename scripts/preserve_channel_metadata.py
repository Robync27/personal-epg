#!/usr/bin/env python3
"""Keep existing channel identity/display metadata byte-for-byte semantically stable.
A new XMLTV build may add channels but may not silently rename existing IDs.
"""
import copy
import sys
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

def preserve(candidate, baseline):
    old = ET.parse(baseline).getroot()
    tree = ET.parse(candidate)
    root = tree.getroot()
    if old.tag != "tv" or root.tag != "tv":
        raise ValueError("Invalid XMLTV input")
    original = {c.get("id"): c for c in old.findall("channel") if c.get("id")}
    changes = 0
    for idx, c in enumerate(list(root)):
        if c.tag != "channel":
            continue
        cid = c.get("id")
        if cid in original:
            if ET.tostring(c, encoding="unicode") != ET.tostring(original[cid], encoding="unicode"):
                root.remove(c)
                root.insert(idx, copy.deepcopy(original[cid]))
                changes += 1
    if changes:
        with tempfile.NamedTemporaryFile(dir=Path(candidate).parent, suffix=".xml", delete=False) as handle:
            temp = Path(handle.name)
        try:
            tree.write(temp, encoding="utf-8", xml_declaration=True)
            ET.parse(temp)
            temp.replace(candidate)
        finally:
            temp.unlink(missing_ok=True)
    return changes

if __name__ == "__main__":
    print("Existing XMLTV channel metadata preserved:", preserve(Path(sys.argv[1]), Path(sys.argv[2])))
