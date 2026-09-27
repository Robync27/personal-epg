# personal-epg

Personal XMLTV guide builder for TiviMate.

It builds a curated 7-day EPG for:

- US premium movie and entertainment channels
- Canadian entertainment channels
- UK Sky Cinema and major entertainment channels

## How it works

A GitHub Actions job runs every 6 hours. It checks out the public-domain `iptv-org/epg` grabber, selects the channels configured in `config/channels.json`, downloads current listings from the configured upstream site definitions, merges them into one XMLTV file, validates the result, compresses it, and commits the current guide to `public/`.

No IPTV username, password, Xtream credentials, VPS credentials, or private tokens belong in this repository.

## TiviMate URL

After the first successful workflow run, use the raw GitHub URL for `public/epg.xml.gz` as the XMLTV EPG source in TiviMate. The channel IDs in your playlist still need to match the XMLTV channel IDs; use TiviMate's manual EPG assignment for channels that do not match automatically.

## Files

- `config/channels.json` — channel groups and matching rules
- `scripts/select_channels.py` — builds small custom channel lists from upstream definitions
- `scripts/merge_xmltv.py` — merges regional XMLTV outputs and removes duplicates
- `.github/workflows/update-epg.yml` — automatic six-hour update
- `public/epg.xml` — generated guide
- `public/epg.xml.gz` — compressed generated guide

## Data and rights

This repository contains software/configuration, not a grant of rights to third-party schedule data. Upstream websites and data providers may have their own terms, copyright, database-right, rate-limit, and redistribution rules. Keep this for personal use unless you have the rights required to redistribute or sell the resulting listings.

The upstream `iptv-org/epg` software is released under The Unlicense. Its source-site adapters can change when providers change their websites or APIs.
