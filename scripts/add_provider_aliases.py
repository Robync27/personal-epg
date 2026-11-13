#!/usr/bin/env python3
"""Publish additional XMLTV IDs proven by a locally exported provider channel inventory.

Only explicit, reviewed equivalent channel mappings are accepted. Original programme
IDs and schedules are preserved. This does not modify IPTV playlists or provider data.
"""
import copy
import gzip
import json
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET


def apply(xml_path, map_path):
    mapping = json.loads(Path(map_path).read_text(encoding="utf-8"))["aliases"]
    tree = ET.parse(xml_path)
    root = tree.getroot()
    if root.tag != "tv":
        raise ValueError("Invalid XMLTV root")
    channels = {c.get("id"): c for c in root.findall("channel")}
    programmes = defaultdict(list)
    for p in root.findall("programme"):
        programmes[p.get("channel")].append(p)
    result = {}
    new_channels = []
    new_programmes = []
    for target, spec in mapping.items():
        sources = spec["source_ids"]
        label = spec["label"]
        if not target or not sources or not label or target in sources:
            raise ValueError("Invalid explicit provider mapping: " + repr(target))
        if programmes[target]:
            result[target] = {"status": "already_has_programmes", "copied": 0}
            continue
        source = next((cid for cid in sources if cid in channels and programmes[cid]), None)
        if not source:
            result[target] = {"status": "source_missing_or_empty", "copied": 0}
            continue
        if target not in channels:
            new = copy.deepcopy(channels[source])
            new.set("id", target)
            for display in new.findall("display-name"):
                new.remove(display)
            display = ET.Element("display-name")
            display.text = label
            new.insert(0, display)
            new_channels.append(new)
            channels[target] = new
        for original in programmes[source]:
            p = copy.deepcopy(original)
            p.set("channel", target)
            new_programmes.append(p)
        result[target] = {"status": "mapped", "source": source, "copied": len(programmes[source])}
    # XMLTV requires channel declarations to precede programme entries.
    first_programme = next((i for i, elem in enumerate(root) if elem.tag == "programme"), len(root))
    for offset, ch in enumerate(new_channels):
        root.insert(first_programme + offset, ch)
    for p in new_programmes:
        root.append(p)
    if new_channels or new_programmes:
        with tempfile.NamedTemporaryFile(dir=Path(xml_path).parent, suffix=".xml", delete=False) as out:
            temp = Path(out.name)
        try:
            tree.write(temp, encoding="utf-8", xml_declaration=True)
            ET.parse(temp)
            temp.replace(xml_path)
        finally:
            temp.unlink(missing_ok=True)
    return result


if __name__ == "__main__":
    path = Path(sys.argv[1])
    mapping = Path(sys.argv[2])
    result = apply(path, mapping)
    print(json.dumps(result, indent=2))
    unmapped = [k for k, v in result.items() if v["status"] == "source_missing_or_empty"]
    if unmapped:
        raise SystemExit("Required provider IDs lack real schedules: " + ", ".join(unmapped))
