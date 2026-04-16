# MERGE DECISION ENGINE

This document defines the decision surface for conflicts between an existing canon note and a new lite candidate.

## Why It Exists

- `review merge` cases are not safely closed by automatic refresh.
- In those cases, you must choose between merge, fork, or keep-existing.
- The merge decision surface is a thin operational layer for that judgment.

## Commands

- `powershell -ExecutionPolicy Bypass -File "./scripts/merge_preview.ps1" -SourceName "note.md" -Kind syntheses -TargetName "existing.md"`
- `powershell -ExecutionPolicy Bypass -File "./scripts/merge_apply.ps1" -SourceName "note.md" -Kind syntheses -TargetName "existing.md" -Decision fork_new_target`

## Default Decisions

- If body overlap is high, prefer `merge_into_existing`.
- If body overlap is weak, prefer `fork_new_target`.
- If the body is the same and only metadata differs, prefer `keep_existing`.
- If the case is ambiguous, use `review_manually`.

## Execution Rules

- `merge_into_existing`
  - combine canon body and evidence into the existing note
- `fork_new_target`
  - branch into a new canon file
- `keep_existing`
  - keep the existing canon note and log only the decision
