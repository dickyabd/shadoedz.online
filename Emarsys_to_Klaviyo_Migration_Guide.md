# Emarsys to Klaviyo Migration Guide

## Overview

The Bulk Import Profiles API performs an **upsert**: it updates a matching profile if one exists (matched on identifier) or creates a new one. At 3.5M profiles and a 10,000-profile-per-job ceiling, this is roughly **350 to 370 jobs**. The accompanying script (`klaviyo_bulk_import.py`) handles chunking, submission, throttling, resume, and error retrieval.

The migration has five phases: export, prepare/map, import, apply consent, verify.

## Critical Constraints (Read First)

The single most important point: **importing a profile is not the same as subscribing it.** The Bulk Import Profiles API does not set or change consent status. If you import contacts and then send to them without a lawful basis, you risk deliverability damage and compliance exposure. Only apply marketing consent (via the Subscribe Profiles endpoint) to contacts who were validly opted in within Emarsys, and migrate that consent state deliberately.

Other hard limits enforced by the API per job:

- Maximum 10,000 profiles per job.  
- Maximum 5 MB total payload per job.  
- Maximum 100 KB per individual profile (oversized profiles are dropped).  
- Jobs expire after 7 days, so retrieve status and errors within that window.  
- The endpoint cannot set fields to `null`. Only non-null values are written.

Authentication and scopes:

- Use a private API key. Header: `Authorization: Klaviyo-API-Key pk_xxx`.  
- The key needs both `profiles:write` and `lists:write` scopes (missing scope returns 403).  
- Pin an API revision via the `revision` header (the script uses `2026-04-15`).

## Phase 1: Export From Emarsys

Export contacts from Emarsys to CSV. You can export from the Emarsys UI (Contacts \> export) or via the Emarsys Contact API. For a list this size, an async file export is the practical route.

Make sure the export includes, at minimum, a reliable identifier (email and/or mobile) plus any standard fields (name, location) and the custom fields you want to retain. Critically, **also export the consent/opt-in fields** (email opt-in status, SMS consent, opt-in date, source) so you can reconstruct consent state in Phase 4\. Note the column header names; you will map them in the script.

## Phase 2: Prepare and Map the Data

Open `klaviyo_bulk_import.py` and edit the mapping section near the top:

- `STANDARD_FIELD_MAP` maps Emarsys CSV column headers to Klaviyo standard attributes (`email`, `phone_number`, `first_name`, `last_name`, `location.city`, etc.). Adjust the left-hand keys to match your exact export headers.  
- `CUSTOM_PROPERTY_COLUMNS` / `AUTO_CUSTOM` control which remaining columns become custom profile properties. With `AUTO_CUSTOM = True`, every unmapped column is carried over as a property.  
- `DEFAULT_COUNTRY_CODE` auto-prefixes bare phone numbers toward E.164. Phone numbers must be valid E.164 (for example `+14155551234`) with a real country code, or they are dropped during processing.

Data hygiene before import: deduplicate on email, drop rows with no identifier, and standardize phone formatting. The script already skips rows with no identifier and rows that exceed 100 KB, and reports the skipped count.

Run a dry run first to confirm chunking and payload sizes without calling the API:

```
export KLAVIYO_API_KEY="pk_xxx"
python klaviyo_bulk_import.py import --csv emarsys_export.csv --dry-run
```

## Phase 3: Import

Decide whether to add profiles to a list during import. Passing `--list-id` upserts the profiles and adds them to that list in one call, which is convenient for segmentation. Omit it to import without list membership.

```
python klaviyo_bulk_import.py import --csv emarsys_export.csv --list-id ABC123
```

Behavior worth knowing:

- The script writes each submitted job to `klaviyo_import_state.jsonl`. It is **resumable**: if it stops or you re-run it, it skips jobs already recorded and continues. Do not delete this file mid-migration.  
- It pauses between submissions and backs off automatically on 429 (rate limit) and 5xx responses, honoring `Retry-After` when present.  
- Validation is partly synchronous: if a job contains an invalid email or phone, the whole job can be rejected with a 400 and **no profiles from that job are imported**. Clean data upstream to avoid losing a full batch of 9,500.  
- Processing order is not guaranteed, and duplicates within or across jobs may be dropped during the upsert.

At a sustained, throttled pace, expect the full 3.5M submission to run over a few hours; actual asynchronous processing on Klaviyo's side completes separately and is tracked by polling.

## Phase 4: Apply Consent (Separate Step)

After profiles exist, apply marketing consent only for contacts with a valid opt-in carried over from Emarsys. Use the **Subscribe Profiles** endpoint (`POST /api/profile-subscription-bulk-create-jobs/`), batching subscribers and setting the correct email/SMS subscription state. Do not blanket-subscribe the whole import. This step is intentionally decoupled so consent is a deliberate, auditable action rather than a side effect of import.

## Phase 5: Monitor and Verify

Check job status across everything you submitted:

```
python klaviyo_bulk_import.py poll
```

This reports each job's status (`queued`, `processing`, `complete`) plus total/completed/failed counts and a roll-up summary. You can also query unprocessed jobs directly: `GET /api/profile-bulk-import-jobs/?filter=any(status,["queued","processing"])`.

Download per-profile import errors (remember the 7-day expiry):

```
python klaviyo_bulk_import.py errors
```

This writes `klaviyo_import_errors.jsonl`, paging through every job's `import-errors` endpoint. Common processing errors: missing identifier, invalid email/phone, duplicate-causing upsert dropped, and individual payload over 100 KB. A 200 response on submission does not guarantee every profile landed, so always review errors.

Finally, spot-check counts in the Klaviyo UI against your source export and confirm a sample of profiles have the expected properties and (where applicable) list membership and consent.

## Error Reference

| Status | Cause |
| :---- | :---- |
| 400 | Missing required field, invalid email/phone, or invalid list ID. No job is created. |
| 401 | Missing or bad auth. |
| 403 | API key missing `profiles:write` and/or `lists:write` scope. |
| 413 | Payload over 5 MB. |
| 429 | Rate limit exceeded (script backs off automatically). |

## Files

- `klaviyo_bulk_import.py` — the import/poll/errors script.  
- `klaviyo_import_state.jsonl` — created at runtime; records submitted jobs (enables resume).  
- `klaviyo_import_errors.jsonl` — created by the `errors` command.

## Source

Klaviyo Bulk Import Profiles API guide: [https://developers.klaviyo.com/en/docs/use\_klaviyos\_bulk\_profile\_import\_api](https://developers.klaviyo.com/en/docs/use_klaviyos_bulk_profile_import_api)  
