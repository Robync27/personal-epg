#!/usr/bin/env python3
"""Fail-closed XMLTV release gate. Never rewrites input or baseline."""
import gzip
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

def inspect(path, now=None):
    now = now or datetime.now(timezone.utc)
    channels = set()
    names = {}
    programmes = Counter()
    future = Counter()
    spans = defaultdict(list)
    missing_title = 0
    for event, elem in ET.iterparse(path, events=("end",)):
        if elem.tag == "channel":
            cid = elem.get("id", "")
            if not cid or cid in channels:
                raise ValueError("missing or duplicate channel id: " + cid)
            channels.add(cid)
            names[cid] = tuple((n.text or "").strip() for n in elem.findall("display-name"))
            elem.clear()
        elif elem.tag == "programme":
            cid = elem.get("channel", "")
            try:
                start = datetime.strptime(elem.get("start", ""), "%Y%m%d%H%M%S %z")
                stop = datetime.strptime(elem.get("stop", ""), "%Y%m%d%H%M%S %z")
            except ValueError as ex:
                raise ValueError("invalid timestamp for " + cid) from ex
            if stop <= start:
                raise ValueError("nonpositive programme duration: " + cid)
            if not any((t.text or "").strip() for t in elem.findall("title")):
                missing_title += 1
            programmes[cid] += 1
            if stop >= now and start <= now + timedelta(days=3):
                future[cid] += 1
            spans[cid].append((start, stop))
            elem.clear()
    if not channels or not programmes:
        raise ValueError("empty guide")
    orphans = set(programmes) - channels
    if orphans:
        raise ValueError("programmes reference undeclared IDs: " + repr(sorted(orphans)[:8]))
    for cid, intervals in spans.items():
        intervals.sort()
        if any(a[1] > b[0] for a, b in zip(intervals, intervals[1:])):
            raise ValueError("overlapping programmes: " + cid)
    total = sum(programmes.values())
    if missing_title > total // 20:
        raise ValueError("more than 5% of programmes lack titles")
    if sum(future.values()) == 0:
        raise ValueError("no current or upcoming programme entries")
    return {"channels": channels, "names": names, "programmes": programmes,
            "future": future, "programme_count": total,
            "future_count": sum(future.values()), "missing_title": missing_title}

def validate(candidate, baseline, gz=None, now=None):
    new = inspect(candidate, now)
    old = inspect(baseline, now)
    removed = old["channels"] - new["channels"]
    if removed:
        raise ValueError("channel ID regression; removed: " + repr(sorted(removed)[:20]))
    if new["programme_count"] < old["programme_count"] * 0.80:
        raise ValueError("programme coverage dropped below 80% of previous release")
    # Compare only when prior release still has substantial upcoming listings.
    if old["future_count"] >= 100 and new["future_count"] < old["future_count"] * 0.75:
        raise ValueError("upcoming listings dropped below 75% of previous release")
    changed = [cid for cid in old["channels"]
               if old["names"][cid] and new["names"][cid]
               and not (set(old["names"][cid]) & set(new["names"][cid]))]
    if changed:
        raise ValueError("channel display-name regression: " + repr(sorted(changed)[:20]))
    if gz:
        with gzip.open(gz, "rb") as fh:
            compressed_hash = hashlib.sha256()
            while chunk := fh.read(1024 * 1024):
                compressed_hash.update(chunk)
        if compressed_hash.digest() != hashlib.sha256(Path(candidate).read_bytes()).digest():
            raise ValueError("gzip file differs from candidate XML")
    return {"channels": len(new["channels"]), "programmes": new["programme_count"],
            "upcoming": new["future_count"], "baseline_programmes": old["programme_count"],
            "baseline_upcoming": old["future_count"], "removed_ids": 0, "status": "PASS"}

if __name__ == "__main__":
    try:
        result = validate(Path(sys.argv[1]), Path(sys.argv[2]),
                          Path(sys.argv[3]) if len(sys.argv) > 3 else None)
        print(json.dumps(result, sort_keys=True))
    except (ValueError, ET.ParseError, OSError, IndexError) as err:
        print("LEVEL 3 RELEASE BLOCKED:", err, file=sys.stderr)
        sys.exit(1)
