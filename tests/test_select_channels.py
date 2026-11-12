#!/usr/bin/env python3
"""Fixture-based selection test: no network or provider access needed."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

with TemporaryDirectory() as temp:
    root = Path(temp)
    upstream = root / "upstream"
    cases = [
        ("us", "sites/mock/us.channels.xml", [
            ("Showtime Extreme East", "us#showtime-extreme-east", "ShowtimeExtreme.us@East"),
            ("Showtime Extreme West", "us#showtime-extreme-west", "ShowtimeExtreme.us@West"),
            ("Showtime Extreme West duplicate", "us#showtime-extreme-west", "ShowtimeExtreme.us@West"),
            ("Random Channel", "us#random", ""),
            ("Showtime Invalid No ID", "us#showtime-invalid", ""),
        ], ["Showtime"]),
        ("uk", "sites/mock/uk.channels.xml", [
            ("W", "GB#1", "W.uk"),
            ("World Documentary", "GB#2", "WorldDoc.uk"),
            ("Sky Cinema Premiere", "GB#3", "SkyCinemaPremiere.uk"),
        ], ["W", "Sky Cinema"]),
    ]
    sources = []
    for region, rel, stations, patterns in cases:
        target = upstream / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        xml = ET.Element("channels")
        for name, site_id, xmltv_id in stations:
            ch = ET.SubElement(xml, "channel",
                {"site": "mock.test", "site_id": site_id, "lang": "en", "xmltv_id": xmltv_id})
            ch.text = name
        ET.ElementTree(xml).write(target, encoding="utf-8", xml_declaration=True)
        source = {"name": region, "upstream": rel, "patterns": patterns}
        if region == "uk":
            source["site_id_prefix"] = "GB#"
        sources.append(source)
    cfg = root / "config.json"
    cfg.write_text(json.dumps({"sources": sources}), encoding="utf-8")
    out = root / "selected"
    subprocess.run([sys.executable, "scripts/select_channels.py", str(cfg),
                    str(upstream), str(out)], check=True)
    us = ET.parse(out / "us.channels.xml").getroot()
    uk = ET.parse(out / "uk.channels.xml").getroot()
    assert len(us) == 2, f"Expected two unique Showtime feeds, got {len(us)}"
    assert len(uk) == 2, f"Expected only W and Sky Cinema, got {len(uk)}"
    assert all(ch.get("xmltv_id") for ch in list(us) + list(uk))
    assert len({ch.get("xmltv_id") for ch in us}) == len(us)
    assert {ch.get("xmltv_id") for ch in us} == {"ShowtimeExtreme.us@East", "ShowtimeExtreme.us@West"}
    assert uk[1].get("xmltv_id") == "SkyCinemaPremiere.uk"
    print("Selection smoke test passed: feeds distinct, canonical IDs preserved, missing IDs skipped, duplicates removed.")
