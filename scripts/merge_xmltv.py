#!/usr/bin/env python3
"""Merge XMLTV sources in priority order and normalize output to Eastern Time."""
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

EASTERN = ZoneInfo('America/Toronto')
TIME_RE = re.compile(r'^(\d{14})(?:\s+([+-]\d{4}))?$')


def parse_time(value):
    match = TIME_RE.fullmatch(value.strip())
    if not match or not match.group(2):
        raise ValueError(f'XMLTV time has no valid UTC offset: {value!r}')
    time = datetime.strptime(match.group(1), '%Y%m%d%H%M%S')
    offset = match.group(2)
    hours, minutes = int(offset[1:3]), int(offset[3:5])
    if hours > 23 or minutes > 59:
        raise ValueError(f'Invalid XMLTV timezone offset: {offset}')
    delta = timedelta(hours=hours, minutes=minutes)
    if offset[0] == '-':
        delta = -delta
    return time.replace(tzinfo=timezone(delta)).astimezone(timezone.utc)


def eastern_stamp(utc):
    return utc.astimezone(EASTERN).strftime('%Y%m%d%H%M%S %z')


def merge(output, inputs):
    root = ET.Element('tv', {'generator-info-name': 'personal-epg'})
    channels = set()
    seen_programmes = set()
    occupied = defaultdict(list)
    counts = Counter()

    for path in inputs:
        if not path.is_file():
            counts['absent_sources'] += 1
            continue
        source = ET.parse(path).getroot()
        if source.tag != 'tv':
            raise ValueError(f'{path}: expected XMLTV <tv> root')
        for ch in source.findall('channel'):
            cid = ch.get('id', '')
            if cid and cid not in channels:
                channels.add(cid)
                root.append(ch)
        programmes = []
        for program in source.findall('programme'):
            cid = program.get('channel', '')
            if not cid:
                counts['no_channel'] += 1
                continue
            try:
                start = parse_time(program.get('start', ''))
                end = parse_time(program.get('stop', ''))
            except ValueError:
                counts['invalid_time'] += 1
                continue
            if end <= start:
                counts['invalid_interval'] += 1
                continue
            programmes.append((start, end, cid, program))

        programmes.sort(key=lambda item: (item[0], item[1], item[2]))
        added = 0
        for start, end, cid, program in programmes:
            if cid not in channels:
                counts['orphan_programmes'] += 1
                continue
            key = (cid, start, end)
            if key in seen_programmes:
                counts['duplicate_programmes'] += 1
                continue
            if any(start < earlier_end and earlier_start < end
                   for earlier_start, earlier_end in occupied[cid]):
                counts['conflicting_programmes'] += 1
                continue
            seen_programmes.add(key)
            occupied[cid].append((start, end))
            program.set('start', eastern_stamp(start))
            program.set('stop', eastern_stamp(end))
            root.append(program)
            added += 1
        print(f'{path}: accepted {added} programmes of {len(programmes)} valid-time entries')
    ET.indent(root, space='  ')
    ET.ElementTree(root).write(output, encoding='utf-8', xml_declaration=True)
    print(f'merged {len(channels)} channels and {len(seen_programmes)} programmes into {output}')
    print('validation:', ', '.join(f'{key}={value}' for key, value in sorted(counts.items())))
    if not channels or not seen_programmes:
        raise SystemExit('Refusing to publish empty EPG')


if __name__ == '__main__':
    merge(Path(sys.argv[1]), [Path(arg) for arg in sys.argv[2:]])
