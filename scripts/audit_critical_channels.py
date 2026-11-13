#!/usr/bin/env python3
"""Audit critical Sky Cinema schedules in a generated XMLTV file.

Fail a release if known source IDs are absent or have no current/future programmes.
This does not claim playlist-to-XMLTV matching has been validated.
"""
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

CRITICAL = {
    "Sky Cinema Premiere": ("SkyCinemaPremiere.uk@HD", "sky-cinema-premiere-hd", "sky-cinema-premiere"),
    "Sky Cinema Drama": ("SkyCinemaDrama.uk@HD", "sky-cinema-drama-hd", "sky-cinema-drama"),
    "Sky Cinema Action": ("SkyCinemaAction.uk@HD", "sky-cinema-action-hd", "sky-cinema-action"),
    "Sky Cinema Comedy": ("SkyCinemaComedy.uk@HD", "sky-cinema-comedy-hd", "sky-cinema-comedy"),
    "Sky Cinema Family": ("SkyCinemaFamily.uk@HD", "sky-cinema-family-hd", "sky-cinema-family"),
    "Sky Cinema Thriller": ("SkyCinemaThriller.uk@HD", "sky-cinema-thriller-hd", "sky-cinema-thriller"),
}

def audit(path, now=None):
    now = now or datetime.now(timezone.utc)
    ids = set()
    future = Counter()
    total = Counter()
    for event, element in ET.iterparse(path, events=("end",)):
        if element.tag == "channel":
            cid = element.get("id", "")
            if cid:
                ids.add(cid)
            element.clear()
        elif element.tag == "programme":
            cid = element.get("channel", "")
            total[cid] += 1
            try:
                start = datetime.strptime(element.get("start", ""), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
                stop = datetime.strptime(element.get("stop", ""), "%Y%m%d%H%M%S %z").astimezone(timezone.utc)
                if start < now + timedelta(days=2) and stop > now and element.findtext("title", "").strip():
                    future[cid] += 1
            except ValueError:
                pass
            element.clear()
    result = {}
    failed = []
    for name, variants in CRITICAL.items():
        known = [cid for cid in variants if cid in ids]
        active = [cid for cid in known if future[cid] > 0]
        result[name] = {"present_ids": known, "active_ids": active,
                        "future_programmes": {cid: future[cid] for cid in known},
                        "all_programmes": {cid: total[cid] for cid in known}}
        if not active:
            failed.append(name)
    return {"status": "FAIL" if failed else "PASS",
            "missing_critical_channels": failed, "channels": result}

if __name__ == "__main__":
    report = audit(Path(sys.argv[1]))
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["missing_critical_channels"]:
        sys.exit(1)
