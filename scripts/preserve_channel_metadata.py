#!/usr/bin/env python3
"""Preserve published XMLTV channel identity and display metadata.

New builds may add channels, but may not silently remove or rename previously
published channel IDs. Missing legacy declarations are restored without copying
old programme entries, which could otherwise publish stale schedules.
"""
import copy
import sys
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET


def preserve(candidate, baseline):
    old = ET.parse(baseline).getroot()
    tree = ET.parse(candidate)
    root = tree.getroot()
    if old.tag != "tv" or root.tag != "tv":
        raise ValueError("Invalid XMLTV input")

    original_channels = [
        channel for channel in old.findall("channel")
        if channel.get("id")
    ]
    original = {channel.get("id"): channel for channel in original_channels}
    current = {
        channel.get("id"): channel
        for channel in root.findall("channel")
        if channel.get("id")
    }

    changes = 0

    # Preserve the exact previously published metadata for IDs that remain.
    for cid, current_channel in current.items():
        previous_channel = original.get(cid)
        if previous_channel is not None and (
            ET.tostring(current_channel, encoding="unicode")
            != ET.tostring(previous_channel, encoding="unicode")
        ):
            index = list(root).index(current_channel)
            root.remove(current_channel)
            root.insert(index, copy.deepcopy(previous_channel))
            changes += 1

    # Restore missing legacy channel declarations, but never old programmes.
    missing = [
        copy.deepcopy(channel)
        for channel in original_channels
        if channel.get("id") not in current
    ]
    if missing:
        first_programme = next(
            (index for index, element in enumerate(root)
             if element.tag == "programme"),
            len(root),
        )
        for offset, channel in enumerate(missing):
            root.insert(first_programme + offset, channel)
        changes += len(missing)

    if changes:
        with tempfile.NamedTemporaryFile(
            dir=Path(candidate).parent, suffix=".xml", delete=False
        ) as handle:
            temp = Path(handle.name)
        try:
            tree.write(temp, encoding="utf-8", xml_declaration=True)
            ET.parse(temp)
            temp.replace(candidate)
        finally:
            temp.unlink(missing_ok=True)

    return changes


if __name__ == "__main__":
    print(
        "Existing XMLTV channel metadata preserved/restored:",
        preserve(Path(sys.argv[1]), Path(sys.argv[2])),
    )
