#!/usr/bin/env python3
"""Build a validated, source-priority XMLTV guide with explicit reviewed ID aliases.
Never guess channel equivalences from display-name similarity.
"""
import argparse
import copy
import gzip
import hashlib
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

EASTERN = ZoneInfo("America/Toronto")
TIMESTAMP = re.compile(r"^(\d{14})\s+([+-]\d{4})$")


def parse_stamp(raw):
    match = TIMESTAMP.fullmatch(raw or "")
    if not match:
        raise ValueError("Invalid timestamp " + repr(raw))
    dt = datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
    off = match.group(2)
    hours, minutes = int(off[1:3]), int(off[3:5])
    if hours > 23 or minutes > 59:
        raise ValueError("Invalid UTC offset " + off)
    delta = timedelta(hours=hours, minutes=minutes)
    if off[0] == "-":
        delta = -delta
    return dt.replace(tzinfo=timezone(delta)).astimezone(timezone.utc)


def stamp(value):
    return value.astimezone(EASTERN).strftime("%Y%m%d%H%M%S %z")


def read_playlist_ids(path):
    """Optional credential-free playlist sample: read only tvg-id attributes."""
    if not path:
        return []
    content = Path(path).read_text(encoding="utf-8")
    return sorted(set(re.findall(r'tvg-id="([^"]+)"', content)))


def build(sources, alias_path, output, gzip_output, report_path, now=None, playlist_path=None):
    now = now or datetime.now(timezone.utc)
    channels = {}
    schedules = defaultdict(list)
    counters = Counter()
    source_reports = {}
    for source_path in sources:
        source_path = Path(source_path)
        if not source_path.exists() or source_path.stat().st_size == 0:
            source_reports[source_path.name] = {"status": "missing", "accepted": 0}
            continue
        root = ET.parse(source_path).getroot()
        if root.tag != "tv":
            raise ValueError(f"{source_path}: invalid XMLTV root")
        for channel in root.findall("channel"):
            cid = channel.get("id", "")
            if cid and cid not in channels:
                channels[cid] = copy.deepcopy(channel)
        accepted = 0
        entries = []
        for programme in root.findall("programme"):
            cid = programme.get("channel", "")
            if not cid:
                counters["no_channel"] += 1
                continue
            if not (programme.findtext("title") or "").strip():
                counters["no_title"] += 1
                continue
            try:
                start = parse_stamp(programme.get("start"))
                stop = parse_stamp(programme.get("stop"))
            except ValueError:
                counters["invalid_timestamp"] += 1
                continue
            if stop <= start:
                counters["invalid_duration"] += 1
                continue
            entries.append((start, stop, cid, programme))
        entries.sort(key=lambda row: (row[0], row[1], row[2]))
        for start, stop, cid, programme in entries:
            if cid not in channels:
                counters["orphan"] += 1
                continue
            if any(start < end2 and start2 < stop for start2, end2, _ in schedules[cid]):
                counters["overlap"] += 1
                continue
            item = copy.deepcopy(programme)
            item.set("start", stamp(start))
            item.set("stop", stamp(stop))
            schedules[cid].append((start, stop, item))
            accepted += 1
        source_reports[source_path.name] = {"status": "read", "accepted": accepted}

    aliases = json.loads(Path(alias_path).read_text(encoding="utf-8")).get("aliases", {})
    alias_report = {}
    for target, source in aliases.items():
        if not target or not source or target == source:
            raise ValueError("Invalid verified alias mapping")
        if target not in channels or source not in channels:
            alias_report[target] = "missing_id"
        elif schedules[target]:
            alias_report[target] = "already_populated"
        elif not schedules[source]:
            alias_report[target] = "source_empty"
        else:
            schedules[target] = [(s, e, copy.deepcopy(p)) for s, e, p in schedules[source]]
            for _, _, item in schedules[target]:
                item.set("channel", target)
            alias_report[target] = "recovered"

    root = ET.Element("tv", {"generator-info-name": "personal-epg-v2"})
    for cid in sorted(channels):
        root.append(channels[cid])
    future = Counter()
    total = Counter()
    for cid in sorted(schedules):
        for start, stop, programme in sorted(schedules[cid]):
            total[cid] += 1
            if start < now + timedelta(days=2) and stop > now:
                future[cid] += 1
            root.append(programme)
    if not channels or not sum(total.values()) or not sum(future.values()):
        raise ValueError("Empty, stale, or unusable guide: refusing publication")
    ET.indent(root, space="  ")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".xml", delete=False) as fh:
        tmp = Path(fh.name)
    try:
        ET.ElementTree(root).write(tmp, encoding="utf-8", xml_declaration=True)
        ET.parse(tmp)
        with gzip.open(str(tmp) + ".gz", "wb", compresslevel=9) as fh:
            fh.write(tmp.read_bytes())
        with gzip.open(str(tmp) + ".gz", "rb") as fh:
            if hashlib.sha256(fh.read()).digest() != hashlib.sha256(tmp.read_bytes()).digest():
                raise ValueError("Compressed XML mismatch")
        tmp.replace(output)
        Path(str(tmp) + ".gz").replace(gzip_output)
    finally:
        tmp.unlink(missing_ok=True)
        Path(str(tmp) + ".gz").unlink(missing_ok=True)
    selected = read_playlist_ids(playlist_path)
    report = {
        "generated_utc": now.isoformat(),
        "channel_count": len(channels),
        "programme_count": sum(total.values()),
        "channels_with_future_programmes": len(future),
        "channels_without_future_programmes": sorted(set(channels) - set(future)),
        "sky_cinema": {
            cid: {"programmes": total[cid], "upcoming": future[cid]}
            for cid, ch in channels.items()
            if "sky cinema" in " ".join((x.text or "") for x in ch.findall("display-name")).lower()
            or "skycinema" in cid.lower() or "sky-cinema" in cid.lower()
        },
        "source_results": source_reports,
        "alias_results": alias_report,
        "rejected_records": dict(counters),
        "playlist_ids_supplied": len(selected),
        "unmatched_playlist_ids": [cid for cid in selected if cid not in channels],
    }
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aliases", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gzip", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--playlist")
    parser.add_argument("sources", nargs="+")
    args = parser.parse_args()
    result = build(args.sources, args.aliases, args.output, args.gzip, args.report, playlist_path=args.playlist)
    print(json.dumps({key: result[key] for key in ("channel_count", "programme_count", "channels_with_future_programmes", "sky_cinema")}, indent=2))


if __name__ == "__main__":
    main()
