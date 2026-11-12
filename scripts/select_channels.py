#!/usr/bin/env python3
"""Build limited, valid channel lists for the upstream EPG grabber."""
import json
import re
import sys
import unicodedata
from pathlib import Path
import xml.etree.ElementTree as ET

cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
upstream = Path(sys.argv[2])
outdir = Path(sys.argv[3])
outdir.mkdir(parents=True, exist_ok=True)

def fallback_id(name, site_id, region):
    # Use readable, stable IDs for upstream rows that have no XMLTV ID.
    # Preserve site_id to distinguish East/West and similarly named feeds.
    base = unicodedata.normalize("NFKD", name)
    base = "".join(c for c in base if not unicodedata.combining(c))
    base = re.sub(r"[^a-zA-Z0-9]+", "", base)[:48] or "Channel"
    suffix = re.sub(r"[^a-zA-Z0-9]+", "", site_id)[-22:] or "source"
    return f"{base}.{region}.{suffix}"

for source in cfg["sources"]:
    src = upstream / source["upstream"]
    root = ET.parse(src).getroot()
    patterns = [re.compile(r"^W$", re.I) if p == "W" else re.compile(p, re.I)
                for p in source["patterns"]]
    prefix = source.get("site_id_prefix")
    selected = []
    seen = set()
    generated = 0
    for ch in root.findall("channel"):
        name = "".join(ch.itertext()).strip()
        site_id = ch.get("site_id", "")
        if not name or not ch.get("site") or not site_id:
            continue
        if prefix and not site_id.startswith(prefix):
            continue
        if not any(p.search(name) for p in patterns):
            continue
        if not ch.get("xmltv_id", "").strip():
            ch.set("xmltv_id", fallback_id(name, site_id, source["name"]))
            generated += 1
        key = (ch.get("site"), site_id)
        if key in seen:
            continue
        seen.add(key)
        selected.append(ch)

    outroot = ET.Element("channels")
    for ch in selected:
        outroot.append(ch)
    for entry in source.get("extra_channels", []):
        if not all(entry.get(k) for k in ("name", "site", "site_id", "xmltv_id")):
            raise SystemExit(f"Invalid extra channel in {source['name']}: {entry}")
        attributes = {key: value for key, value in entry.items() if key != "name"}
        ET.SubElement(outroot, "channel", attributes).text = entry["name"]

    ids = [ch.get("xmltv_id") for ch in outroot]
    if len(set(ids)) != len(ids):
        raise SystemExit(f"Duplicate XMLTV IDs selected for {source['name']}")
    out = outdir / f"{source['name']}.channels.xml"
    ET.ElementTree(outroot).write(out, encoding="utf-8", xml_declaration=True)
    print(f"{source['name']}: selected {len(outroot)} channels, repaired {generated} blank XMLTV IDs -> {out}")
    if not len(outroot):
        raise SystemExit(f"No channels selected for {source['name']}")
