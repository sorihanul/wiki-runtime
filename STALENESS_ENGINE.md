# STALENESS ENGINE

This document defines how `wiki runtime` detects and reviews stale notes.

## What It Detects

- notes with `stale_flag=true`
- notes that already carry `supersession`
- canon notes that exceed freshness thresholds
- canon or lite notes that exceed review thresholds

## Why It Exists

- If old notes are retrieved as if they were current, the wiki becomes unreliable immediately.
- Before deletion, the system needs stale markers and review priority.

## Commands

- `powershell -ExecutionPolicy Bypass -File "./scripts/staleness.ps1"`
- `powershell -ExecutionPolicy Bypass -File "./scripts/mark_stale.ps1"`

## Default Handling

- Superseded notes are treated as stale.
- Canon notes are judged by both old freshness values and delayed review.
- Lite notes are considered review candidates only when they are `adopt` or `hold`.

## Stale Marking

- `mark_stale.ps1` writes `stale_flag=true` onto canon notes with clear stale conditions.
- At the current stage, only `forced stale` and `canon age stale` are treated as auto-mark candidates.
