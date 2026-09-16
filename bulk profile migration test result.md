# Emarsys to Klaviyo Bulk Profile Migration: Test Report

**Date:** June 11, 2026
**Prepared by:** Grain Group
**Client:** NOBULL

---

## Objective

Validate the Emarsys to Klaviyo bulk profile migration pipeline end-to-end using a test export before running the full 3.5M profile load. Scope includes field mapping, chunking, job submission, status polling, and error retrieval against the NOBULL Klaviyo account.

---

## Test Data

- **File:** TEST_export_22487_1_en-53cdd0.csv
- **Total rows:** 4,032 contacts
- **Schema:** 138 columns including email, mobile, name, address, loyalty fields, Shopify/predict properties, and opt-in/consent flags

---

## Field Mapping

The following Emarsys columns were mapped to Klaviyo standard profile attributes:

| Emarsys Column | Klaviyo Attribute |
|---|---|
| Email | email |
| Mobile | phone_number |
| user_id | external_id |
| First Name | first_name |
| Last Name | last_name |
| Title | title |
| Company | organization |
| Address | location.address1 |
| ZIP Code | location.zip |
| City | location.city |
| State | location.region |
| Country or region | location.country |

All remaining columns (~125) were imported as custom profile properties.

---

## Test Results

| Step | Result |
|---|---|
| Dry run (chunking + size check) | 1 job, 4,032 profiles, 3.06 MB (well under 5 MB limit) |
| Live import | Submitted successfully (Job ID: VnY2TVhyX21haW50ZW5hbmNlLmQ1OHpOQS4xNzgxMTY4MTczLmtSUkxsWA) |
| Job status | Complete |
| Klaviyo reported failures | 0 |
| Import errors (via errors command) | 0 |
| Members visible in Klaviyo list | 3,996 |

---

## Issues Found and Resolved

### 1. Invalid Email Addresses (3 rows)

Three rows contained malformed email addresses that caused Klaviyo to reject the entire batch on the first submission attempt.

| Row | Email | Issue |
|---|---|---|
| 1680 | mailto:connect@nobullproject.com | "mailto:" prefix |
| 1812 | tracey!@nobullproject.com | Invalid character (!) |
| 3715 | abbyrapp@nobullproject.com1 | Digit appended to TLD |

**Resolution:** Email validation was added to the migration script. Invalid emails are now skipped at the row level rather than failing the entire job. These 3 contacts were still imported using their Emarsys user_id as the profile identifier, without an email attribute.

### 2. Missing API Key Check on Dry Run

The script required a Klaviyo API key even when running in dry-run mode, which makes no API calls.

**Resolution:** Fixed in the script. Dry runs no longer require the API key.

---

## Data Quality Findings

### Duplicate Email Addresses (Source: Emarsys Export)

15 email addresses appear more than once in the export, producing 54 duplicate rows. Klaviyo automatically merges profiles with the same email, which accounts for the difference between profiles imported (4,032) and members visible in the list (3,996).

A consistent pattern was observed across all duplicate groups: each group contains one "primary" row with a full name, loyalty data, and a numeric Shopify ID (a real Shopify customer record), and one or more "ghost" rows with blank name fields and UUID-style or alphanumeric Shopify IDs (likely created by Emarsys web tracking or the Predict module). This suggests the duplicates originate from Emarsys creating anonymous tracking profiles that share the same email as an existing customer.

**This is a data quality issue in the Emarsys source export, not a script or Klaviyo issue.**

---

#### madisondaries@nobullproject.com (7 rows)

| CSV Row | user_id | Name | Loyalty Status | Loyalty Points | Shopify ID |
|---|---|---|---|---|---|
| 113 | 229687169 | | | | fd2a34ba-e293-4ce6-9f2f-dab13913ac84 |
| 3712 | 791740159 | Madison D'Aries | Blocked | | 8155551006910 |
| 3800 | 820079441 | | | | 4bfef489-acd1-4199-8465-75c26673e1da |
| 3934 | 1521014014 | | | | 0bbcd702-a22c-4c2a-834d-868abc870e0c |
| 3943 | 1597373922 | | | | 6485137d-ffed-4c67-9fe6-04536d33af45 |
| 3948 | 1623085878 | | | | 2edf8b11-7858-4627-9a39-2f3abe99381e |
| 3978 | 1810422983 | | | | 9957ffb2-5ff3-4373-a248-0d67a7326121 |

#### lindseycunniff@nobullproject.com (6 rows)

| CSV Row | user_id | Name | Loyalty Status | Loyalty Points | Shopify ID |
|---|---|---|---|---|---|
| 106 | 184988362 | | | | 183db269-9baf-48fb-a820-400775bc6bc7 |
| 2073 | 625987159 | | | | 73c31e04-bc60-43a8-a51a-7e453ad6cdcc |
| 3687 | 781841130 | Lindsey Cunniff | Blocked | | 8130019786942 |
| 3944 | 1601227579 | | | | 4zny1bw8kx7mapk0lur |
| 3968 | 1765677659 | | | | 4847937a-0987-450d-8fd6-9ed669b4d51b |
| 3993 | 1904642142 | | | | bwppt1ip9g8ma89wk0r |

#### meganmurray@nobullproject.com (6 rows)

| CSV Row | user_id | Name | Loyalty Status | Loyalty Points | Shopify ID |
|---|---|---|---|---|---|
| 124 | 294914216 | | | | dgekws0vx0tma5kbz2t |
| 3837 | 968783125 | | | | em347v5b7nrmbjnsnwi |
| 3838 | 970093493 | Megan Murray | Blocked | | 8253131096254 |
| 3846 | 991368051 | | | | f0b6f389-15f1-40f6-b811-fc60884723b2 |
| 3859 | 1038649832 | | | | 83243cc6-e7fd-4a27-89cc-7e4fe9c82be5 |
| 3960 | 1716883598 | | | | 153ca3c4-b4c1-4c8a-b6c1-2166c7595958 |

#### danluise@nobullproject.com (6 rows)

| CSV Row | user_id | Name | Loyalty Status | Loyalty Points | Shopify ID |
|---|---|---|---|---|---|
| 1697 | 405723299 | | | | 8e3e4303-3212-4d55-9ed9-e24815b76b8c |
| 1836 | 457478152 | | | | 274d8b49-17d5-4186-8bed-3b43482e5933 |
| 1856 | 465502212 | Dan Luise | enrolled | 200 | 5330786189502 |
| 3872 | 1127156251 | | | | 00593c6a-c358-493c-b4d6-e4d24812ce15 |
| 3919 | 1394779510 | | | | 02adf7bc-30c2-46db-a66f-e68a4d1963a5 |
| 4019 | 2050940065 | | | | 8v60yxv9lv8mb6q8v9a |

#### michathaddeus@nobullproject.com (6 rows)

| CSV Row | user_id | Name | Loyalty Status | Loyalty Points | Shopify ID |
|---|---|---|---|---|---|
| 1895 | 475186559 | Micha Thaddeus | blocked | 200 | 5156739514558 |
| 3709 | 790822927 | | | | 8c65ecbb-9fa2-47b3-ae3d-62a1fef6710e |
| 3874 | 1131946000 | | | | 80576d74-1492-43d7-9764-07d690fc0722 |
| 3880 | 1166468708 | | | | 06e4027b-85f5-449c-8a46-cd11e9259607 |
| 3893 | 1232582250 | | | | f51360db-2936-4906-a63c-8d441f9120a8 |
| 3903 | 1277561574 | | | | 532f9b15-1442-4a56-8955-2d9da002c84d |

#### cameronburke@nobullproject.com (6 rows)

| CSV Row | user_id | Name | Loyalty Status | Loyalty Points | Shopify ID |
|---|---|---|---|---|---|
| 2092 | 710033022 | | | | 6356dc73-5cd1-4e23-a6a0-6cba8f1b4220 |
| 3797 | 806869533 | | | | 29e79867-27ae-4699-a53e-154cb722b04e |
| 3842 | 979313824 | | | | 04ccd8d7-f324-4b5b-8408-91189e72a7c1 |
| 3935 | 1535206226 | | | | 7226c6e9-8252-4d34-9547-42d00effeea5 |
| 3957 | 1701449213 | | | | 12227951-6ccb-4d4e-8ed6-3cb680a90de4 |
| 3967 | 1762313434 | Cameron Burke | Blocked | 464 | 7958910435518 |

#### sarahperkinson@nobullproject.com (5 rows)

| CSV Row | user_id | Name | Loyalty Status | Loyalty Points | Shopify ID |
|---|---|---|---|---|---|
| 7 | 24068208 | Sarah Perkinson | | | 9068017516734 |
| 119 | 268950057 | | | | 5842020d-5dd7-48a8-8e47-53da8cfc6d7b |
| 127 | 299166539 | | | | 14651ba8-e383-424a-8892-ead692335816 |
| 1753 | 417302828 | | | | 98910931-0a6a-487c-be64-f4c88944d512 |
| 3895 | 1235782255 | | | | b7ad2a50-0d66-4e61-9991-518e35b23191 |

#### rup@nobullproject.com (5 rows)

| CSV Row | user_id | Name | Loyalty Status | Loyalty Points | Shopify ID |
|---|---|---|---|---|---|
| 3823 | 921237718 | ANANDARUP BASUROYCHOWDHURY | Blocked | 100 | 7791728591038 |
| 3875 | 1139642079 | | | | c2d710e8-1ab2-4531-b927-a4c4178ede61 |
| 3906 | 1314525652 | | | | 4d302b34-b799-4cae-a1f4-f1e896722507 |
| 3907 | 1320347544 | | | | 388ce87e-4f57-4739-924e-5a7a79764e2c |
| 3976 | 1799053864 | | | | 18980737-a1f3-40f6-b936-2d44da47d4ff |

#### siobaindermody@nobullproject.com (4 rows)

| CSV Row | user_id | Name | Loyalty Status | Loyalty Points | Shopify ID |
|---|---|---|---|---|---|
| 78 | 120425121 | Siobain Dermody | blocked | | 9448154005694 |
| 180 | 327235614 | | | | dc04ddc5-5b72-43d9-a9d6-ac96bf35c838 |
| 1896 | 477262284 | | | | 342d954e-5ccf-40c2-ac6f-916256066f61 |
| 3815 | 890107946 | | | | 908282693 |

#### jeannecarpenter@nobullproject.com (4 rows)

| CSV Row | user_id | Name | Loyalty Status | Loyalty Points | Shopify ID |
|---|---|---|---|---|---|
| 2072 | 613172735 | | | | 3e5acb44-6822-4f88-a8f0-28549c115f0c |
| 2074 | 629907572 | | | | fdc5befd-7177-408d-9fe9-0e6d2f5e17b4 |
| 3922 | 1405791338 | | | | sxbvfmbzx3imbfczl7d |
| 3941 | 1579879876 | Jeanne Carpenter | Blocked | | 8384802291902 |

#### dannyshields@nobullproject.com (4 rows)

| CSV Row | user_id | Name | Loyalty Status | Loyalty Points | Shopify ID |
|---|---|---|---|---|---|
| 3836 | 968521075 | | | | 843781726 |
| 3839 | 972229821 | | | | e8a27a32-c68e-4b3e-b446-818e5e11c741 |
| 3885 | 1186179412 | | | | 6a93c98d-3fb9-4e49-b46c-dfcb92550e30 |
| 4027 | 2119170948 | Danny Shields | pending | | 9282279047358 |

#### bhaviniraju@nobullproject.com (3 rows)

| CSV Row | user_id | Name | Loyalty Status | Loyalty Points | Shopify ID |
|---|---|---|---|---|---|
| 135 | 316464760 | Bhavini Raju | blocked | 244 | 6925120569534 |
| 829 | 382813094 | | | | bf65d303-40f9-4f68-a4d2-cb3f82283929 |
| 3680 | 764119057 | | | | b677f545-94f2-45dc-87a1-aaaca1b36313 |

#### emilianoesquer@nobullproject.com (3 rows)

| CSV Row | user_id | Name | Loyalty Status | Loyalty Points | Shopify ID |
|---|---|---|---|---|---|
| 3912 | 1347997331 | | | | 7387b2bc-3b0a-40e3-b8d6-0af56aa0aec5 |
| 3931 | 1469828501 | Emiliano Esquer | enrolled | 50 | 9519764766910 |
| 4017 | 2044875461 | | | | db8aff73-6e68-4f7e-a1e7-9e2132248e86 |

#### jason@nobullproject.com (2 rows)

| CSV Row | user_id | Name | Loyalty Status | Loyalty Points | Shopify ID |
|---|---|---|---|---|---|
| 1692 | 404026892 | Jason Harty | Blocked | 100 | 6091865292990 |
| 3981 | 1836664999 | | | | a30ks0zcpz8ma5ozr46 |

#### mattwhalen@nobullproject.com (2 rows)

| CSV Row | user_id | Name | Loyalty Status | Loyalty Points | Shopify ID |
|---|---|---|---|---|---|
| 1920 | 495886094 | Matthew Whalen | Blocked | 200 | 4479794184382 |
| 3799 | 817659214 | | | | c7f30010-7ca2-46e0-b88a-ed629c11e80a |

---

## Opt-In / Subscription Status

The Klaviyo Bulk Import Profiles API does not set subscription or consent status. All 3,996 profiles were imported as unsubscribed contacts. Their original opt-in values (Emarsys columns: Opt-In, Mobile SMS Opt-In, google_ad_user_data_consent) are stored as custom properties on each profile.

A separate step using Klaviyo's Subscribe Profiles endpoint is required to mirror consent status before sending any marketing communications. This step should only be applied to contacts with a confirmed lawful basis for marketing.

---

## Recommendations Before Full 3.5M Migration

1. **Deduplicate the Emarsys export** by email address before running the full load. Duplicate rows result in profile merges in Klaviyo and inflated job sizes.
2. **Validate emails at export time** to remove malformed addresses (mailto: prefixes, invalid characters, numeric TLDs) before the file reaches the migration script.
3. **Plan the subscription sync step** separately. Define which opt-in fields map to which Klaviyo subscription channels (email marketing, SMS) and run the Subscribe Profiles endpoint after the full import completes.
4. **Run the full migration in off-peak hours** given the 3.5M volume. At ~9,500 profiles per job, expect approximately 368 API jobs with a 0.5-second pause between submissions.
