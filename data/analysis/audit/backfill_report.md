# Historical Derived Artifact Backfill Audit

## Summary

- date range: 2026-06-29 → 2026-09-17
- total historical dates: 19
- already complete: 3
- fully backfilled: 0
- partially backfilled: 7
- not recoverable: 9
- failed: 0
- live recrawl: NO
- preservation policy: existing artifacts were never overwritten
- SourceHealth column meaning: standalone Daily Health SourceHealth evidence; older Trend snapshots still embed the SourceHealth-derived reliability gate

## Derived Artifact Dependency Map

### Production AI job analysis

- entrypoint: `src.analysis.ai_eval_jobs.run_analysis`
- inputs: dated clean jobs, config.yaml company scope
- outputs: *_ai_eval_analysis.json, *_ai_eval_report.md, *_ai_eval_hits.jsonl

### Classification / Personal Fit

- entrypoint: `src.analysis.pipeline.replay -> src.analysis.classification.classify_record`
- inputs: dated clean jobs, SourceHealth, classifier versions, prior reliable classification
- outputs: analysis/classification/YYYY-MM-DD.jsonl

### SourceHealth

- entrypoint: `src.analysis.source_health.SourceHealth`
- inputs: crawl manifest, dated clean jobs
- outputs: in-memory reliability used by lifecycle, trend, audit, and Daily Health

### Lifecycle / Events

- entrypoint: `src.analysis.lifecycle.Lifecycle.observe`
- inputs: strictly chronological clean observations, SourceHealth, prior lifecycle state
- outputs: analysis/events/YYYY-MM-DD.jsonl

### Trend

- entrypoint: `src.analysis.trends.trend_snapshot / compare_trends`
- inputs: classification, canonical events, SourceHealth, present clean identities, prior history
- outputs: analysis/trends/snapshots/YYYY-MM-DD.json, optional comparisons
- reliability gate: `src.analysis.trends.trend_comparability`

### Trend report

- entrypoint: `tools.generate_market_report.render_snapshot`
- inputs: canonical trend snapshot
- outputs: analysis/reports/market_report_YYYY-MM-DD.md

### Audit

- entrypoint: `src.analysis.audit_bundle.export_bundle`
- inputs: clean jobs, classification, SourceHealth, events, trend, prior observation
- outputs: analysis/audit/YYYY-MM-DD_bundle.json

### Daily Health

- entrypoint: `src.analysis.daily_health.generate_daily_health`
- inputs: actual daily run status, crawl manifest, clean jobs, known-limitations registry
- outputs: analysis/health/YYYY-MM-DD.json

### Daily run status

- entrypoint: `tools.run_daily.run_daily`
- inputs: actual crawl/clean/analysis execution results
- outputs: analysis/runs/YYYY-MM-DD.json
- backfill policy: never synthesize from artifacts after the fact

### History registration

- entrypoint: `src.operations.daily_ops.DailyOperations.publish`
- inputs: actual daily run status, Daily Health
- outputs: ops/ops.sqlite3 runs and sources rows

## Per-date matrix

| Date | Crawl | Clean | Analysis | SourceHealth | Reliability | Lifecycle/Events | Trend | Audit | Daily status/health | DB | Result | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-06-29 | YES | NO | NO | NO | NO | NO | NO | NO | NO | NO | NOT_RECOVERABLE | MISSING_CLEAN |
| 2026-06-30 | YES | NO | NO | NO | NO | NO | NO | NO | NO | NO | NOT_RECOVERABLE | MISSING_CLEAN |
| 2026-07-01 | YES | NO | NO | NO | NO | NO | NO | NO | NO | NO | NOT_RECOVERABLE | MISSING_CLEAN |
| 2026-07-02 | YES | NO | NO | NO | NO | NO | NO | NO | NO | NO | NOT_RECOVERABLE | MISSING_CLEAN |
| 2026-07-03 | YES | NO | NO | NO | NO | NO | NO | NO | NO | NO | NOT_RECOVERABLE | MISSING_CLEAN |
| 2026-07-04 | NO | YES | NO | NO | NO | NO | NO | NO | NO | NO | NOT_RECOVERABLE | MISSING_RAW; MISSING_MANIFEST |
| 2026-07-06 | YES | NO | NO | NO | NO | NO | NO | NO | NO | NO | NOT_RECOVERABLE | MISSING_CLEAN |
| 2026-07-07 | YES | YES | YES | NO | YES | YES | YES | YES | NO | NO | PARTIAL_BACKFILL | Derived analysis recovered; actual historical daily run status is unavailable, so Daily Health/DB history were not fabricated |
| 2026-07-08 | YES | YES | YES | NO | YES | YES | YES | YES | NO | NO | PARTIAL_BACKFILL | Derived analysis recovered; actual historical daily run status is unavailable, so Daily Health/DB history were not fabricated |
| 2026-07-14 | YES | NO | NO | NO | NO | NO | NO | NO | NO | NO | NOT_RECOVERABLE | MISSING_CLEAN |
| 2026-07-15 | YES | NO | NO | NO | NO | NO | NO | NO | NO | NO | NOT_RECOVERABLE | MISSING_CLEAN |
| 2026-09-01 | YES | YES | YES | NO | YES | YES | YES | YES | NO | NO | PARTIAL_BACKFILL | Derived analysis recovered; actual historical daily run status is unavailable, so Daily Health/DB history were not fabricated |
| 2026-09-02 | YES | YES | YES | NO | YES | YES | YES | YES | NO | NO | PARTIAL_BACKFILL | Derived analysis recovered; actual historical daily run status is unavailable, so Daily Health/DB history were not fabricated |
| 2026-09-03 | YES | YES | YES | NO | YES | YES | YES | YES | NO | NO | PARTIAL_BACKFILL | Derived analysis recovered; actual historical daily run status is unavailable, so Daily Health/DB history were not fabricated |
| 2026-09-04 | YES | YES | YES | NO | YES | YES | YES | YES | NO | NO | PARTIAL_BACKFILL | Derived analysis recovered; actual historical daily run status is unavailable, so Daily Health/DB history were not fabricated |
| 2026-09-07 | YES | YES | YES | NO | YES | YES | YES | YES | NO | NO | PARTIAL_BACKFILL | Derived analysis recovered; actual historical daily run status is unavailable, so Daily Health/DB history were not fabricated |
| 2026-09-15 | YES | YES | YES | YES | YES | YES | YES | YES | YES | YES | ALREADY_COMPLETE | Canonical daily derived chain and operations history already existed; preserved |
| 2026-09-16 | YES | YES | YES | YES | YES | YES | YES | YES | YES | YES | ALREADY_COMPLETE | Canonical daily derived chain and operations history already existed; preserved |
| 2026-09-17 | YES | YES | YES | YES | YES | YES | YES | YES | YES | YES | ALREADY_COMPLETE | Canonical daily derived chain and operations history already existed; preserved |

## Unrecoverable dates

- 2026-06-29: MISSING_CLEAN. Reconstructing the missing observation would require inventing or recrawling historical evidence.
- 2026-06-30: MISSING_CLEAN. Reconstructing the missing observation would require inventing or recrawling historical evidence.
- 2026-07-01: MISSING_CLEAN. Reconstructing the missing observation would require inventing or recrawling historical evidence.
- 2026-07-02: MISSING_CLEAN. Reconstructing the missing observation would require inventing or recrawling historical evidence.
- 2026-07-03: MISSING_CLEAN. Reconstructing the missing observation would require inventing or recrawling historical evidence.
- 2026-07-04: MISSING_RAW; MISSING_MANIFEST. Reconstructing the missing observation would require inventing or recrawling historical evidence.
- 2026-07-06: MISSING_CLEAN. Reconstructing the missing observation would require inventing or recrawling historical evidence.
- 2026-07-14: MISSING_CLEAN. Reconstructing the missing observation would require inventing or recrawling historical evidence.
- 2026-07-15: MISSING_CLEAN. Reconstructing the missing observation would require inventing or recrawling historical evidence.

## Recomputed artifacts

- 2026-07-07: `data/analysis/classification/2026-07-07.jsonl` from `data/clean/2026-07-07.json`; taxonomy SHA `bf228dc29dfda76ce974d4acab88769939aa4d61`; RECOMPUTED_WITH_CURRENT_TAXONOMY because the structured classification artifact was missing
- 2026-07-08: `data/analysis/classification/2026-07-08.jsonl` from `data/clean/2026-07-08.json`; taxonomy SHA `bf228dc29dfda76ce974d4acab88769939aa4d61`; RECOMPUTED_WITH_CURRENT_TAXONOMY because the structured classification artifact was missing
- 2026-09-01: `data/analysis/classification/2026-09-01.jsonl` from `data/clean/2026-09-01.json`; taxonomy SHA `bf228dc29dfda76ce974d4acab88769939aa4d61`; RECOMPUTED_WITH_CURRENT_TAXONOMY because the structured classification artifact was missing
- 2026-09-02: `data/analysis/classification/2026-09-02.jsonl` from `data/clean/2026-09-02.json`; taxonomy SHA `bf228dc29dfda76ce974d4acab88769939aa4d61`; RECOMPUTED_WITH_CURRENT_TAXONOMY because the structured classification artifact was missing
- 2026-09-03: `data/analysis/classification/2026-09-03.jsonl` from `data/clean/2026-09-03.json`; taxonomy SHA `bf228dc29dfda76ce974d4acab88769939aa4d61`; RECOMPUTED_WITH_CURRENT_TAXONOMY because the structured classification artifact was missing
- 2026-09-04: `data/analysis/classification/2026-09-04.jsonl` from `data/clean/2026-09-04.json`; taxonomy SHA `bf228dc29dfda76ce974d4acab88769939aa4d61`; RECOMPUTED_WITH_CURRENT_TAXONOMY because the structured classification artifact was missing
- 2026-09-07: `data/analysis/classification/2026-09-07.jsonl` from `data/clean/2026-09-07.json`; taxonomy SHA `bf228dc29dfda76ce974d4acab88769939aa4d61`; RECOMPUTED_WITH_CURRENT_TAXONOMY because the structured classification artifact was missing

## Remaining gaps

- 2026-06-29: actual daily run status / Daily Health / operations history unavailable
- 2026-06-29: original full production AI job analysis and structured classification are unavailable
- 2026-06-30: actual daily run status / Daily Health / operations history unavailable
- 2026-06-30: original full production AI job analysis and structured classification are unavailable
- 2026-07-01: actual daily run status / Daily Health / operations history unavailable
- 2026-07-01: original full production AI job analysis and structured classification are unavailable
- 2026-07-02: actual daily run status / Daily Health / operations history unavailable
- 2026-07-02: original full production AI job analysis and structured classification are unavailable
- 2026-07-03: actual daily run status / Daily Health / operations history unavailable
- 2026-07-03: original full production AI job analysis and structured classification are unavailable
- 2026-07-04: actual daily run status / Daily Health / operations history unavailable
- 2026-07-04: original full production AI job analysis and structured classification are unavailable
- 2026-07-06: actual daily run status / Daily Health / operations history unavailable
- 2026-07-06: original full production AI job analysis and structured classification are unavailable
- 2026-07-07: actual daily run status / Daily Health / operations history unavailable
- 2026-07-07: original full production AI job analysis artifact unavailable; structured current-taxonomy classification is used
- 2026-07-08: actual daily run status / Daily Health / operations history unavailable
- 2026-07-08: original full production AI job analysis artifact unavailable; structured current-taxonomy classification is used
- 2026-07-14: actual daily run status / Daily Health / operations history unavailable
- 2026-07-14: original full production AI job analysis and structured classification are unavailable
- 2026-07-15: actual daily run status / Daily Health / operations history unavailable
- 2026-07-15: original full production AI job analysis and structured classification are unavailable
- 2026-09-01: actual daily run status / Daily Health / operations history unavailable
- 2026-09-01: original full production AI job analysis artifact unavailable; structured current-taxonomy classification is used
- 2026-09-02: actual daily run status / Daily Health / operations history unavailable
- 2026-09-02: original full production AI job analysis artifact unavailable; structured current-taxonomy classification is used
- 2026-09-03: actual daily run status / Daily Health / operations history unavailable
- 2026-09-03: original full production AI job analysis artifact unavailable; structured current-taxonomy classification is used
- 2026-09-04: actual daily run status / Daily Health / operations history unavailable
- 2026-09-04: original full production AI job analysis artifact unavailable; structured current-taxonomy classification is used
- 2026-09-07: actual daily run status / Daily Health / operations history unavailable
- 2026-09-07: original full production AI job analysis artifact unavailable; structured current-taxonomy classification is used
- 2026-09-15: original full production AI job analysis artifact unavailable; structured current-taxonomy classification is used
- 2026-09-16: original full production AI job analysis artifact unavailable; structured current-taxonomy classification is used
- 2026-09-17: original full production AI job analysis artifact unavailable; structured current-taxonomy classification is used

## Trend reliability finding

PASS: 33 platform-date observations with an unreliable metric family carry explicit reason codes. `trend_comparability` excludes those platform/family pairs and emits null deltas when no comparable platform remains, so source failure is not reported as market movement.

## REQUIRES_USER_DECISION

Lifecycle currently advances by successive available observations rather than calendar-consecutive runs. Gaps found: 2026-07-08→2026-09-01 (55 days), 2026-09-04→2026-09-07 (3 days), 2026-09-07→2026-09-15 (8 days). Boundary NEW/REMOVED events are valid observation-to-observation facts but must not be described as daily market movement without a production semantics decision.
