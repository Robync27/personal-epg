# personal-epg

Personal XMLTV guide builder for TiviMate.

It builds a curated 7-day EPG for:

- US premium movie and entertainment channels
- Canadian entertainment channels
- UK Sky Cinema and major entertainment channels

## How it works

A GitHub Actions job runs daily at 2:00 a.m. America/Toronto (automatically accounting for daylight saving time). It checks out the public-domain `iptv-org/epg` grabber, selects the channels configured in `config/channels.json`, downloads current listings from the configured upstream site definitions, merges results into one XMLTV file, validates the result, compresses it, and commits the current guide to `public/`.

No IPTV username, password, Xtream credentials, VPS credentials, or private tokens belong in this repository.

## TiviMate URL

Existing TiviMate URL (kept up to date by the workflow):

`https://raw.githubusercontent.com/Robync27/personal-epg/main/Canada_EPG.xml.gz`

Alternative URL: `https://raw.githubusercontent.com/Robync27/personal-epg/main/public/epg.xml.gz`

The workflow checks for updated listings every day at 2:00 a.m. Ontario time and also runs when its code or configuration changes. The channel IDs in your playlist must match the XMLTV channel IDs; use TiviMate's manual EPG assignment for channels that do not match automatically. A matching channel name in the configuration does not guarantee that an upstream source provides its schedule.

## Files

- `config/channels.json` — channel groups and matching rules
- `scripts/select_channels.py` — builds small custom channel lists from upstream definitions
- `scripts/select_fallbacks.py` — identifies missing XMLTV IDs and selects one alternative upstream source per ID; configurable via `fallback` in `config/channels.json`
- `scripts/merge_xmltv.py` — merges regional XMLTV outputs and removes duplicates
- `.github/workflows/update-epg.yml` — automatic daily 2:00 a.m. Ontario-time update
- `public/epg.xml` — generated guide
- `public/epg.xml.gz` — compressed generated guide
- `Canada_EPG.xml.gz` — compatibility copy for the existing TiviMate URL

## Data and rights

This repository contains software/configuration, not a grant of rights to third-party schedule data. Upstream websites and data providers may have their own terms, copyright, database-right, rate-limit, and redistribution rules. Keep this for personal use unless you have the rights required to redistribute or sell the resulting listings.

The upstream `iptv-org/epg` software is released under The Unlicense. Its source-site adapters can change when providers change their websites or APIs.

## Fallback source coverage

The fallback pass runs only for selected XMLTV IDs with no primary programme entries. It looks through upstream channel definitions and chooses an alternate source using exact IDs; it does not guess matches based on channel names. A source being listed is not proof that its scraper works or has current listings. The fallback pass is capped at 150 selected channels per update to control runtime. This is **not** a scrape of every channel or every provider. Check the Actions logs for counts and errors; provider terms and rate limits still apply.

## Temporary safeguard (November 2026)

The automated fallback scraping pass is temporarily disabled after a reported decline in TiviMate guide coverage. The US, Canada, and UK primary scrapers remain active. The publishing workflow now checks minimum channel/programme coverage and compares its new guide to the previously published guide before replacing it. These checks may reject an update rather than publish a severely reduced guide. Fallback configuration and selector script are retained for further testing but are not executed by the current workflow.

## Automatic operation

The scheduled workflow runs every day at **2:00 a.m. America/Toronto** and can also be triggered manually from **Actions → Update personal EPG → Run workflow**. It scrapes the configured upstream sites, creates a merged seven-day XMLTV guide, validates its minimum schedule coverage, and only then commits `public/epg.xml`, `public/epg.xml.gz` and `Canada_EPG.xml.gz` to the `main` branch. The legacy TiviMate URL remains unchanged. If scraping or validation fails, the workflow does not publish a new guide; the last successfully committed guide remains available. Scheduled GitHub Actions may start later than the cron time, and TiviMate refresh timing is configured separately within TiviMate.

The fallback selector is currently **disabled** in the production workflow while missing-guide issues are investigated; descriptions above of alternate sources are for the optional code only.
