#!/usr/bin/env python3
"""
Emarsys -> Klaviyo bulk profile migration.

Reads an Emarsys contact export (CSV), maps columns to Klaviyo profile
attributes, splits the data into jobs that respect Klaviyo's Bulk Import
Profiles API limits, submits each job, and tracks status + import errors.

Designed for large migrations (e.g. 3.5M profiles). It is RESUMABLE: every
submitted job is written to a state file, so re-running the script will not
re-submit jobs that already succeeded.

Klaviyo Bulk Import Profiles API limits (per job):
  - max 10,000 profiles
  - max 5 MB total payload
  - max 100 KB per individual profile
Reference: https://developers.klaviyo.com/en/docs/use_klaviyos_bulk_profile_import_api

IMPORTANT: This endpoint does NOT set consent. Subscription/consent status
must be applied separately via the Subscribe Profiles endpoint AFTER import,
and only for contacts who have a lawful basis for marketing. Importing a
profile is NOT the same as subscribing it. See the accompanying guide.

Usage:
  export KLAVIYO_API_KEY="pk_xxx"          # private key, scopes: profiles:write, lists:write
  python klaviyo_bulk_import.py import   --csv emarsys_export.csv [--list-id ABC123] [--dry-run]
  python klaviyo_bulk_import.py poll                                # check status of submitted jobs
  python klaviyo_bulk_import.py errors                              # download import errors for finished jobs
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

API_BASE = "https://a.klaviyo.com/api"
API_REVISION = "2026-04-15"            # pin a revision; bump deliberately
API_KEY = os.environ.get("KLAVIYO_API_KEY", "")

# API hard limits
MAX_PROFILES_PER_JOB = 10_000
MAX_PAYLOAD_BYTES = 5 * 1024 * 1024    # 5 MB
MAX_PROFILE_BYTES = 100 * 1024         # 100 KB

# Stay safely under the limits to leave headroom for JSON overhead.
TARGET_PROFILES_PER_JOB = 9_500
TARGET_PAYLOAD_BYTES = int(4.7 * 1024 * 1024)

# Throttling. The POST endpoint is burst-limited; pause between submits and
# back off on 429. Tune SUBMIT_PAUSE upward if you see sustained 429s.
SUBMIT_PAUSE = 0.5                      # seconds between job submissions
MAX_RETRIES = 6

STATE_FILE = "klaviyo_import_state.jsonl"   # one JSON record per submitted job

# --------------------------------------------------------------------------- #
# Field mapping  --  Emarsys TEST_export_22487_1 column schema
# --------------------------------------------------------------------------- #
# Keys are Emarsys CSV column headers; values are Klaviyo standard attributes.
# All unmapped columns are imported as custom properties (AUTO_CUSTOM = True).
STANDARD_FIELD_MAP = {
    # Identifiers
    "Email":                "email",
    "Mobile":               "phone_number",
    "user_id":              "external_id",
    # Name
    "First Name":           "first_name",
    "Last Name":            "last_name",
    "Title":                "title",
    # Organization
    "Company":              "organization",
    # Home address
    "Address":              "location.address1",
    "ZIP Code":             "location.zip",
    "City":                 "location.city",
    "State":                "location.region",
    "Country or region":    "location.country",
}

# Emarsys columns to carry over as custom profile properties.
# Leave empty to map every unmapped column automatically (set AUTO_CUSTOM=True).
CUSTOM_PROPERTY_COLUMNS = []
AUTO_CUSTOM = True

# Phone numbers must be E.164 (e.g. +14155551234) or they are dropped.
DEFAULT_COUNTRY_CODE = "+1"   # set to None to skip auto-prefixing


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def require_key():
    if not API_KEY:
        sys.exit("ERROR: set KLAVIYO_API_KEY environment variable (private key).")


def headers():
    return {
        "Authorization": f"Klaviyo-API-Key {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "revision": API_REVISION,
    }


def api_request(method, url, body=None):
    """Single HTTP call with 429/5xx exponential backoff. Returns (status, json)."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    for attempt in range(MAX_RETRIES):
        req = urllib.request.Request(url, data=data, headers=headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            if e.code == 429:
                retry_after = float(e.headers.get("Retry-After", 0)) or (2 ** attempt)
                print(f"  429 rate limited; sleeping {retry_after:.0f}s "
                      f"(attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(retry_after)
                continue
            if 500 <= e.code < 600:
                backoff = 2 ** attempt
                print(f"  {e.code} server error; retry in {backoff}s")
                time.sleep(backoff)
                continue
            # 4xx other than 429 are not retryable
            try:
                return e.code, json.loads(raw)
            except json.JSONDecodeError:
                return e.code, {"raw": raw}
        except urllib.error.URLError as e:
            backoff = 2 ** attempt
            print(f"  network error {e}; retry in {backoff}s")
            time.sleep(backoff)
    return 0, {"error": "max retries exceeded"}


_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

def is_valid_email(value):
    return bool(value and _EMAIL_RE.match(value.strip()))


def normalize_phone(value):
    if not value:
        return None
    v = value.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not v:
        return None
    if v.startswith("+"):
        return v
    if DEFAULT_COUNTRY_CODE:
        return DEFAULT_COUNTRY_CODE + v
    return v


def set_nested(attrs, dotted_key, value):
    """Support 'location.city' style keys -> attrs['location']['city']."""
    if "." in dotted_key:
        parent, child = dotted_key.split(".", 1)
        attrs.setdefault(parent, {})[child] = value
    else:
        attrs[dotted_key] = value


def row_to_profile(row):
    """Map one CSV row to a Klaviyo profile object. Returns None if no identifier."""
    attrs = {}
    properties = {}
    mapped_sources = set()

    for col, klaviyo_field in STANDARD_FIELD_MAP.items():
        if col in row and row[col] not in (None, ""):
            mapped_sources.add(col)
            val = row[col].strip()
            if klaviyo_field == "phone_number":
                val = normalize_phone(val)
                if not val:
                    continue
            if klaviyo_field == "email" and not is_valid_email(val):
                continue
            set_nested(attrs, klaviyo_field, val)

    # custom properties
    custom_cols = CUSTOM_PROPERTY_COLUMNS
    if AUTO_CUSTOM and not custom_cols:
        custom_cols = [c for c in row.keys() if c not in mapped_sources]
    for col in custom_cols:
        if col in row and row[col] not in (None, ""):
            properties[col] = row[col].strip()

    if properties:
        attrs["properties"] = properties

    # require at least one identifier
    if not attrs.get("email") and not attrs.get("phone_number") and not attrs.get("external_id"):
        return None

    return {"type": "profile", "attributes": attrs}


def build_payload(profiles, list_id=None):
    payload = {
        "data": {
            "type": "profile-bulk-import-job",
            "attributes": {"profiles": {"data": profiles}},
        }
    }
    if list_id:
        payload["data"]["relationships"] = {
            "lists": {"data": [{"type": "list", "id": list_id}]}
        }
    return payload


def chunk_profiles(csv_path):
    """Yield lists of profiles that respect count + size limits."""
    batch = []
    batch_bytes = 2048  # base envelope overhead estimate
    skipped = 0
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            profile = row_to_profile(row)
            if profile is None:
                skipped += 1
                continue
            p_bytes = len(json.dumps(profile).encode("utf-8")) + 1
            if p_bytes > MAX_PROFILE_BYTES:
                skipped += 1
                continue  # would be dropped by Klaviyo anyway
            over_count = len(batch) + 1 > TARGET_PROFILES_PER_JOB
            over_size = batch_bytes + p_bytes > TARGET_PAYLOAD_BYTES
            if batch and (over_count or over_size):
                yield batch
                batch, batch_bytes = [], 2048
            batch.append(profile)
            batch_bytes += p_bytes
    if batch:
        yield batch
    if skipped:
        print(f"NOTE: skipped {skipped} rows (no identifier / oversize).")


def load_state():
    jobs = []
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    jobs.append(json.loads(line))
    return jobs


def append_state(record):
    with open(STATE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #

def cmd_import(args):
    if not args.dry_run:
        require_key()
    already = len(load_state())
    submitted = 0
    print(f"Resuming: {already} jobs already recorded in {STATE_FILE}.")
    for idx, batch in enumerate(chunk_profiles(args.csv)):
        if idx < already:
            continue  # already submitted in a previous run
        payload = build_payload(batch, args.list_id)
        size_mb = len(json.dumps(payload).encode("utf-8")) / 1024 / 1024
        if args.dry_run:
            print(f"[dry-run] job #{idx}: {len(batch)} profiles, {size_mb:.2f} MB")
            submitted += 1
            continue
        status, resp = api_request("POST", f"{API_BASE}/profile-bulk-import-jobs/", payload)
        if status in (200, 201, 202):
            job_id = resp.get("data", {}).get("id")
            append_state({
                "index": idx,
                "job_id": job_id,
                "count": len(batch),
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            })
            submitted += 1
            print(f"job #{idx} OK  id={job_id}  ({len(batch)} profiles, {size_mb:.2f} MB)")
        else:
            print(f"job #{idx} FAILED status={status} resp={json.dumps(resp)[:500]}")
            print("Stopping so you can fix the issue; re-run to resume.")
            return
        time.sleep(SUBMIT_PAUSE)
    print(f"\nDone. Submitted {submitted} new job(s) this run.")


def cmd_poll(args):
    require_key()
    jobs = load_state()
    if not jobs:
        print("No jobs in state file.")
        return
    counts = {}
    for j in jobs:
        jid = j["job_id"]
        status, resp = api_request(
            "GET",
            f"{API_BASE}/profile-bulk-import-jobs/{jid}/"
            f"?fields[profile-bulk-import-job]=status,completed_count,failed_count,total_count",
        )
        attrs = resp.get("data", {}).get("attributes", {})
        st = attrs.get("status", f"http {status}")
        counts[st] = counts.get(st, 0) + 1
        print(f"{jid}: {st}  "
              f"total={attrs.get('total_count')} "
              f"done={attrs.get('completed_count')} "
              f"failed={attrs.get('failed_count')}")
        time.sleep(0.2)
    print("\nSummary:", json.dumps(counts))


def cmd_errors(args):
    require_key()
    jobs = load_state()
    out_path = "klaviyo_import_errors.jsonl"
    total = 0
    with open(out_path, "w", encoding="utf-8") as out:
        for j in jobs:
            jid = j["job_id"]
            url = f"{API_BASE}/profile-bulk-import-jobs/{jid}/import-errors/"
            while url:
                status, resp = api_request("GET", url)
                if status != 200:
                    print(f"{jid}: error fetch failed status={status}")
                    break
                for err in resp.get("data", []):
                    out.write(json.dumps({"job_id": jid, "error": err}) + "\n")
                    total += 1
                url = resp.get("links", {}).get("next")
                time.sleep(0.2)
    print(f"Wrote {total} import errors to {out_path}.")


def main():
    parser = argparse.ArgumentParser(description="Emarsys -> Klaviyo bulk import")
    sub = parser.add_subparsers(dest="command", required=True)

    p_imp = sub.add_parser("import", help="submit bulk import jobs")
    p_imp.add_argument("--csv", required=True, help="Emarsys export CSV path")
    p_imp.add_argument("--list-id", default=None, help="optional Klaviyo list ID")
    p_imp.add_argument("--dry-run", action="store_true", help="chunk only, no API calls")
    p_imp.set_defaults(func=cmd_import)

    p_poll = sub.add_parser("poll", help="check status of submitted jobs")
    p_poll.set_defaults(func=cmd_poll)

    p_err = sub.add_parser("errors", help="download import errors")
    p_err.set_defaults(func=cmd_errors)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
