#!/usr/bin/env python3
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

out = Path(sys.argv[1])
inputs = [Path(x) for x in sys.argv[2:]]
root = ET.Element('tv', {'generator-info-name': 'personal-epg'})
channels = set()
programmes = set()
for path in inputs:
    if not path.exists():
        continue
    src = ET.parse(path).getroot()
    for ch in src.findall('channel'):
        cid = ch.get('id', '')
        if cid and cid not in channels:
            channels.add(cid)
            root.append(ch)
    for p in src.findall('programme'):
        key = (p.get('channel',''), p.get('start',''), p.get('stop',''))
        if key not in programmes:
            programmes.add(key)
            root.append(p)
ET.indent(root, space='  ')
ET.ElementTree(root).write(out, encoding='utf-8', xml_declaration=True)
print(f"merged {len(channels)} channels and {len(programmes)} programmes into {out}")
