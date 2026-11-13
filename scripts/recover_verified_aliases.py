#!/usr/bin/env python3
"""Fill missing XMLTV IDs solely from explicitly reviewed same-service schedules.

Never guesses based on names, never changes existing programmes, never
deletes original channel metadata, and never changes source IDs.
"""
import copy
import json
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET


def apply_aliases(xml_path: Path, config_path: Path):
    mapping = json.loads(config_path.read_text(encoding="utf-8"))["aliases"]
    tree = ET.parse(xml_path)
    root = tree.getroot()
    if root.tag != "tv":
        raise ValueError("Expected XMLTV root")
    ids = {c.get("id") for c in root.findall("channel")}
    grouped = defaultdict(list)
    for p in root.findall("programme"):
        grouped[p.get("channel")].append(p)
    report = {}
    pending = []
    for target, source in mapping.items():
        if not target or target == source or not source:
            raise ValueError(f"Invalid alias mapping {target!r} -> {source!r}")
        if target not in ids or source not in ids:
            report[target] = {"source": source, "status": "missing_channel_id", "copied": 0}
            continue
        if grouped[target]:
            report[target] = {"source": source, "status": "already_has_schedule", "copied": 0}
            continue
        if not grouped[source]:
            report[target] = {"source": source, "status": "source_has_no_schedule", "copied": 0}
            continue
        pending.extend((target, p) for p in grouped[source])
        report[target] = {"source": source, "status": "recovered", "copied": len(grouped[source])}
    for target, original in pending:
        replica = copy.deepcopy(original)
        replica.set("channel", target)
        root.append(replica)
    if pending:
        # An interrupted process must never leave a truncated published XML file.
        with tempfile.NamedTemporaryFile(dir=xml_path.parent, suffix=".xml", delete=False) as tmp:
            temp = Path(tmp.name)
        try:
            tree.write(temp, encoding="utf-8", xml_declaration=True)
            ET.parse(temp)  # Verify our output before atomic replacement.
            temp.replace(xml_path)
        finally:
            temp.unlink(missing_ok=True)
    return report


if __name__ == "__main__":
    result = apply_aliases(Path(sys.argv[1]), Path(sys.argv[2]))
    counts = Counter(x["status"] for x in result.values())
    print("Verified equivalent-service ID recovery:", dict(counts))
    for target, item in result.items():
        print(f"{target}: {item['status']} (source={item['source']}, programmes={item['copied']})")
