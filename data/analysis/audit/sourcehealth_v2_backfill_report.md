# SourceHealth Reliability V2 Historical Backfill

- taxonomy SHA: `4161514aed0a0a0cb471ed6d8f79175537c17b33`
- replay generated_at: `2026-09-18T07:42:40+00:00`
- date range: 2026-06-29 → 2026-09-18
- total dates: 20
- already V2: 0
- replayed V2: 2
- partial V2: 9
- not recoverable: 9
- failed: 0
- live recrawl: NO
- raw / clean rewritten: NO
- Daily Health rewritten: NO

## Per-date coverage

| Date | Raw | Manifest | Clean | Prior trend | Status | UNKNOWN | Unattributed legacy UNKNOWN | Reason |
| --- | --- | --- | --- | --- | --- | ---: | ---: | --- |
| 2026-06-29 | True | True | False | None | NOT_RECOVERABLE | 0 | 0 | MISSING_CLEAN |
| 2026-06-30 | True | True | False | None | NOT_RECOVERABLE | 0 | 0 | MISSING_CLEAN |
| 2026-07-01 | True | True | False | None | NOT_RECOVERABLE | 0 | 0 | MISSING_CLEAN |
| 2026-07-02 | True | True | False | None | NOT_RECOVERABLE | 0 | 0 | MISSING_CLEAN |
| 2026-07-03 | True | True | False | None | NOT_RECOVERABLE | 0 | 0 | MISSING_CLEAN |
| 2026-07-04 | False | False | True | None | NOT_RECOVERABLE | 0 | 0 | MISSING_RAW; MISSING_MANIFEST |
| 2026-07-06 | True | True | False | None | NOT_RECOVERABLE | 0 | 0 | MISSING_CLEAN |
| 2026-07-07 | True | True | True | trend_v1 | PARTIAL_V2 | 1196 | 1196 | LEGACY_DETAIL_FAILURE_IDENTITIES_UNAVAILABLE |
| 2026-07-08 | True | True | True | trend_v1 | REPLAYED_V2 | 0 | 0 |  |
| 2026-07-14 | True | True | False | None | NOT_RECOVERABLE | 0 | 0 | MISSING_CLEAN |
| 2026-07-15 | True | True | False | None | NOT_RECOVERABLE | 0 | 0 | MISSING_CLEAN |
| 2026-09-01 | True | True | True | trend_v1 | REPLAYED_V2 | 0 | 0 |  |
| 2026-09-02 | True | True | True | trend_v1 | PARTIAL_V2 | 1 | 1 | LEGACY_DETAIL_FAILURE_IDENTITIES_UNAVAILABLE |
| 2026-09-03 | True | True | True | trend_v1 | PARTIAL_V2 | 1 | 1 | LEGACY_DETAIL_FAILURE_IDENTITIES_UNAVAILABLE |
| 2026-09-04 | True | True | True | trend_v1 | PARTIAL_V2 | 10 | 1 | LEGACY_DETAIL_FAILURE_IDENTITIES_UNAVAILABLE |
| 2026-09-07 | True | True | True | trend_v1 | PARTIAL_V2 | 833 | 833 | LEGACY_DETAIL_FAILURE_IDENTITIES_UNAVAILABLE |
| 2026-09-15 | True | True | True | trend_v1 | PARTIAL_V2 | 1 | 1 | LEGACY_DETAIL_FAILURE_IDENTITIES_UNAVAILABLE |
| 2026-09-16 | True | True | True | trend_v1 | PARTIAL_V2 | 1 | 1 | LEGACY_DETAIL_FAILURE_IDENTITIES_UNAVAILABLE |
| 2026-09-17 | True | True | True | trend_v1 | PARTIAL_V2 | 2 | 1 | LEGACY_DETAIL_FAILURE_IDENTITIES_UNAVAILABLE |
| 2026-09-18 | True | True | True | trend_v1 | PARTIAL_V2 | 1 | 1 | LEGACY_DETAIL_FAILURE_IDENTITIES_UNAVAILABLE |

## Artifact counts

- classification: 11
- events: 11
- trend: 11
- audit_bundle: 11
- daily_market_report: 11
- weekly: 11

## UNKNOWN totals

- inventory: 2046
- unknown_new_jobs: 1
- unknown_reappeared_jobs: 1
- unknown_removed_jobs: 2
- unknown_updated_jobs: 0

## Frozen regression

- tencent_2026_09_17: PASS
- meituan_severe: PASS
- didi_2026_09_04: PASS
- weekly: PASS

## V1 → V2 before / after

- Tencent 2026-09-17 V1: `{"confirmed_active": 127, "confirmed_new": 3, "content_flow_reliable": false, "inventory_reliable": false, "observed": 127, "presence_flow_reliable": false, "unknown": 0, "unknown_new": 0}`
- Tencent 2026-09-17 V2: `{"confirmed_active": 127, "confirmed_new": 3, "content_flow_reliable": true, "inventory_reliable": true, "observed": 128, "presence_flow_reliable": true, "unknown": 1, "unknown_new": 1}`
- Meituan 2026-07-07 V2: confirmed=121, unknown=1194, observed=1315, skill_categories=16
- Meituan 2026-09-07 V2: confirmed=147, unknown=829, observed=976, skill_categories=16
- Didi 2026-09-04 V2: `{"confirmed_active": 43, "content_flow_reliable": true, "inventory_reason_codes": ["LIST_RECORDS_INCOMPLETE", "SOURCE_PRESENCE_UNRELIABLE"], "inventory_reliable": false, "observed": 52, "presence_flow_reason_codes": ["LIST_RECORDS_INCOMPLETE", "SOURCE_PRESENCE_UNRELIABLE"], "presence_flow_reliable": false, "unknown": 9}`

## Idempotency

- verified: True
- semantic derived artifacts are hash-stable across the second run

## Provenance

Each replayable date records frozen input hashes, before/after derived hashes, source date, taxonomy SHA, trend_v2, and replay generated_at in the JSON manifest.
