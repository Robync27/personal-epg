#!/usr/bin/env python3
"""Report XMLTV schedule coverage; does not verify TiviMate playlist mapping."""
import collections
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
out = Path(sys.argv[2])
channels = {}
for ch in root.findall("channel"):
    cid = ch.get("id")
    if cid:
        channels[cid] = [x.text.strip() for x in ch.findall("display-name") if x.text and x.text.strip()]

counts, remaining = collections.Counter(), collections.Counter()
now = datetime.now(timezone.utc)
for p in root.findall("programme"):
    cid = p.get("channel")
    if not cid:
        continue
    counts[cid] += 1
    raw = (p.get("stop") or p.get("start") or "").strip()
    try:
        dt = datetime.strptime(raw[:14], "%Y%m%d%H%M%S")
        suffix = raw[14:].strip()
        if len(suffix) >= 5 and suffix[0] in "+-" and suffix[1:5].isdigit():
            sign = 1 if suffix[0] == "+" else -1
            minutes = sign * (int(suffix[1:3])*60 + int(suffix[3:5]))
            dt = dt.replace(tzinfo=timezone(timedelta(minutes=minutes)))
        else:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt > now:
            remaining[cid] += 1
    except ValueError:
        continue

rows = [{"xmltv_id": cid, "names": names, "programmes": counts[cid],
         "remaining_programmes": remaining[cid]} for cid, names in sorted(channels.items())]
zero = [r for r in rows if not r["programmes"]]
expired = [r for r in rows if not r["remaining_programmes"]]
report = {
    "generated_utc": now.isoformat(timespec="seconds"),
    "channel_count": len(rows),
    "programme_count": sum(counts.values()),
    "channels_with_programmes": len(rows)-len(zero),
    "channels_with_remaining_programmes": len(rows)-len(expired),
    "channels_missing_all_programmes": zero,
    "channels_missing_current_or_future_programmes": expired,
    "channels": rows,
    "note": "XMLTV data only; TiviMate tvg-id/EPG mapping is not checked."
}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
lines = [
    "### XMLTV coverage report",
    "- Defined channels: **%s**" % len(rows),
    "- Programme entries: **%s**" % sum(counts.values()),
    "- Channels with any entries: **%s**" % (len(rows)-len(zero)),
    "- Channels with current/future entries: **%s**" % (len(rows)-len(expired)),
    "- Channels with no entries: **%s**" % len(zero),
    "",
    "This does not check TiviMate playlist channel IDs.",
    "",
    "#### Channels with no entries",
]
lines.extend("- %s (%s)" % (", ".join(r["names"]), r["xmltv_id"]) for r in zero[:100])
summary = "\n".join(lines)+"\n"
print(summary)
summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
if summary_path:
    with open(summary_path, "a", encoding="utf-8") as stream:
        stream.write(summary)
