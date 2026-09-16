# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A minimal Python utilities repo. The main artifact is `klaviyo_bulk_import.py`, a standalone CLI tool for migrating profiles from Emarsys to Klaviyo via the Klaviyo Bulk Import Profiles API.

## Running the Script

Requires `KLAVIYO_API_KEY` environment variable set to a private API key (`pk_...`).

```powershell
$env:KLAVIYO_API_KEY = "pk_xxx"

# Submit import jobs from CSV
python klaviyo_bulk_import.py import --csv emarsys_export.csv

# Dry run (no API calls)
python klaviyo_bulk_import.py import --csv emarsys_export.csv --dry-run

# Poll status of submitted jobs
python klaviyo_bulk_import.py poll

# Download error reports
python klaviyo_bulk_import.py errors
```

No dependencies beyond the Python standard library. No build, lint, or test setup.

## Architecture of klaviyo_bulk_import.py

**State file**: `klaviyo_import_state.jsonl` — one JSONL record per submitted job. The `import` command is resumable: it skips jobs already recorded in this file.

**Chunking logic**: The script splits the CSV into chunks that respect three Klaviyo API hard limits — 10,000 profiles/job (targets 9,500), 5 MB payload (targets 4.7 MB), and 100 KB per profile. Each chunk becomes one API job.

**Field mapping**: Emarsys column names are mapped to Klaviyo standard profile attributes in the `FIELD_MAP` dict (around line 50). Unmapped columns are automatically added as Klaviyo custom properties (`AUTO_CUSTOM = True`).

**Phone normalization**: Strips non-digit characters and prepends the default country code (`DEFAULT_COUNTRY_CODE = "+1"`) if no country code is present.

**Pinned API revision**: The Klaviyo API revision is hard-coded as `2026-04-15`. Do not change it without testing, as Klaviyo breaking changes are versioned by date.

**Consent/subscriptions are not set** by this script. After import, subscription status must be applied separately via Klaviyo's Subscribe Profiles endpoint for contacts with lawful marketing basis.

**Retry logic**: 6 retries with exponential backoff on HTTP 429 and 5xx responses. A 0.5-second pause is inserted between job submissions to avoid rate-limit bursts.
