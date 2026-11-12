#!/usr/bin/env python3
"""Select alternate upstream scrapers for XMLTV IDs missing primary listings."""
import argparse
import collections
import json
from pathlib import Path
import xml.etree.ElementTree as ET

def main():
    p = argparse.ArgumentParser()
    p.add_argument("config", type=Path)
    p.add_argument("upstream", type=Path)
    p.add_argument("selected_dir", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("primary", type=Path, nargs="+")
    a = p.parse_args()
    cfg = json.loads(a.config.read_text(encoding="utf-8"))
    rules = cfg.get("fallback", {})
    cap = int(rules.get("max_channels", 150))
    if not 0 <= cap <= 1000:
        raise SystemExit("fallback.max_channels must be between 0 and 1000")
    preferred = rules.get("preferred_sites", ["tvpassport.com", "tvguide.com"])

    selected = set()
    primary_sites = collections.defaultdict(set)
    for source in cfg["sources"]:
        path = a.selected_dir / (source["name"] + ".channels.xml")
        if not path.exists():
            continue
        for _, ch in ET.iterparse(path, events=("end",)):
            if ch.tag == "channel":
                cid = ch.get("xmltv_id")
                if cid:
                    selected.add(cid)
                    if ch.get("site"):
                        primary_sites[cid].add(ch.get("site"))
                ch.clear()

    covered = set()
    for path in a.primary:
        if not path.exists():
            print("Missing primary output:", path)
            continue
        try:
            for _, element in ET.iterparse(path, events=("end",)):
                if element.tag == "programme" and element.get("channel"):
                    covered.add(element.get("channel"))
                element.clear()
        except ET.ParseError as error:
            print("Invalid primary output:", path, error)

    missing = selected - covered
    candidates = collections.defaultdict(list)
    if cap and missing:
        for path in sorted((a.upstream / "sites").glob("*/*.channels.xml")):
            try:
                for _, ch in ET.iterparse(path, events=("end",)):
                    if ch.tag == "channel":
                        cid = ch.get("xmltv_id")
                        site = ch.get("site")
                        if (cid in missing and site and ch.get("site_id")
                                and site not in primary_sites[cid]):
                            candidates[cid].append(
                                (site, ch.get("site_id"), ch.get("lang", ""),
                                 "".join(ch.itertext()).strip()))
                        ch.clear()
            except ET.ParseError as error:
                print("Skipping malformed definition:", path, error)

    root = ET.Element("channels")
    per_site = collections.Counter()
    for cid in sorted(missing):
        if len(root) >= cap:
            break
        options = candidates.get(cid, [])
        if not options:
            continue
        options.sort(key=lambda entry: (
            preferred.index(entry[0]) if entry[0] in preferred else len(preferred),
            entry[0], entry[1]))
        site, site_id, lang, name = options[0]
        attrs = {"site": site, "site_id": site_id, "xmltv_id": cid}
        if lang:
            attrs["lang"] = lang
        ET.SubElement(root, "channel", attrs).text = name or cid
        per_site[site] += 1

    a.output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(a.output, encoding="utf-8", xml_declaration=True)
    print("Missing IDs:", len(missing), "fallback candidates selected:", len(root))
    for site, number in per_site.most_common():
        print(" ", site, number)

if __name__ == "__main__":
    main()
