# CANON UPDATE ENGINE

This document defines how existing canon notes are reviewed and updated.

## Why It Exists

- If a target canon note already exists, a promotion candidate cannot always be handled as a new promotion.
- In that case, the issue is closer to canon refresh than to a blocked promotion.
- The canon update queue separates such cases into `refresh existing` and `review merge`.

## Commands

- `powershell -ExecutionPolicy Bypass -File "./scripts/update_queue.ps1"`
- `powershell -ExecutionPolicy Bypass -File "./scripts/refresh_canon.ps1" -SourceName "note.md" -Kind syntheses`
- `powershell -ExecutionPolicy Bypass -File "./scripts/merge_preview.ps1" -SourceName "note.md" -Kind syntheses -TargetName "existing.md"`

## Output

- `./reports/canon_update_queue_YYYYMMDD_HHMMSS.md`

## Default Handling

- Check whether the target canon note referenced by the current lite note actually exists.
- If the canon note came from the same source, prefer `refresh existing`.
- If metadata is missing, drifting, or the canon body differs, send it to the refresh path.
- If the target is the same but the source role or meaning differs, send it to `review merge`.

## Decision Rules

- `refresh existing`
  - when a canon note from the same source no longer matches the current lite note
  - treat it as an immediate refresh candidate by default
- `review merge`
  - when the same target is referenced but merge judgment is still required
  - prefer human review over automatic refresh
  - use `MERGE_DECISION_ENGINE.md` together with `merge_preview`
