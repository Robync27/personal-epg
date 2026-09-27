#!/usr/bin/env python3
import json, re, sys
from pathlib import Path
import xml.etree.ElementTree as ET

cfg = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
upstream = Path(sys.argv[2])
outdir = Path(sys.argv[3])
outdir.mkdir(parents=True, exist_ok=True)

for source in cfg['sources']:
    src = upstream / source['upstream']
    root = ET.parse(src).getroot()
    patterns = [re.compile(p, re.I) for p in source['patterns']]
    prefix = source.get('site_id_prefix')
    selected = []
    seen = set()
    for ch in root.findall('channel'):
        name = ''.join(ch.itertext()).strip()
        site_id = ch.get('site_id', '')
        if prefix and not site_id.startswith(prefix):
            continue
        if not any(p.search(name) for p in patterns):
            continue
        key = (site_id, name)
        if key in seen:
            continue
        seen.add(key)
        selected.append(ch)
    outroot = ET.Element('channels')
    for ch in selected:
        outroot.append(ch)
    out = outdir / f"{source['name']}.channels.xml"
    ET.ElementTree(outroot).write(out, encoding='utf-8', xml_declaration=True)
    print(f"{source['name']}: selected {len(selected)} channels -> {out}")
    if not selected:
        raise SystemExit(f"No channels selected for {source['name']}")
