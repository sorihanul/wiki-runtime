# REPORT ARCHIVE POLICY

This document defines the minimum policy for keeping the `reports` folder usable over long runtimes.

The core rule is simple:

- keep human-facing surfaces and files currently referenced by the runtime
- archive older detailed artifacts
- keep only a small recent window per report family in the top-level `reports` folder

## Root Retention Window

- `governance_cycle_*`
  - keep the most recent 2 at the root
- `supervisor_cycle_*`
  - keep the most recent 2 at the root
- `repair_queue_*`
  - keep the most recent 1 at the root
- `promotion_queue_*`
  - keep the most recent 1 at the root
- `canon_update_queue_*`
  - keep the most recent 1 at the root

This retention window is the minimum needed to preserve useful recent history without letting the top-level `reports` folder grow without bound.

## Keep At Root

- `governance_latest.md`
- `governance_daily_YYYYMMDD.md`
- `supervisor_latest.md`
- `supervisor_daily_YYYYMMDD.md`
- reports directly referenced by the current `_runtime_state`
- reports linked by the current summary surfaces
- the latest `load_test` validation set required by validation
  - keep one latest `md/json` pair per scale at the root

## Archive Candidates

- older detailed artifacts beyond the retention window
- unreferenced old `governance_cycle_*`
- unreferenced old `supervisor_cycle_*`
- unreferenced old `repair_queue_*`
- unreferenced old `promotion_queue_*`
- unreferenced old `canon_update_queue_*`
- old `load_test_*` artifacts except the latest required validation set
- temporary smoke or log files such as `_.txt`

## Commands

- dry run
  - `powershell -ExecutionPolicy Bypass -File "./scripts/archive_reports.ps1"`
- apply move
  - `powershell -ExecutionPolicy Bypass -File "./scripts/archive_reports.ps1" -Apply`

## First Status Surface

- `python "./scripts/wiki_runtime.py" status`
  - focus first on:
    - `cleanup_candidates_now`
    - `cleanup_candidates_by_type`
    - `kept_in_reports_now`
    - `cleanup_recommended_now`
- `./reports/governance_latest.md`
- `./reports/supervisor_latest.md`

## Archive Location

- `./reports/archive/YYYYMMDD/`

If a date can be read from the filename, archive into that date bucket.
Otherwise, use the file modification date.

## Summary Link Rewriting

- `latest` surfaces directly protect only current root-level detail reports.
- `daily` surfaces exist to preserve past history.
- When archiving runs, old detail-report links inside `daily` surfaces are rewritten to `archive/YYYYMMDD/...`.

This prevents `daily` summaries from permanently protecting old root-level reports and blocking cleanup.

## Why This Exists

- `latest` and `daily` links must not break.
- If a report referenced by the current cache disappears, runtime behavior becomes unstable.
- Validation also expects the latest load-test artifacts to remain at the root.

In other words, archive is not an aggressive deletion feature.
It is a safe cleanup feature that also controls how many detailed artifacts remain at the top-level `reports` surface.
