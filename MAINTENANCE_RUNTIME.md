# MAINTENANCE RUNTIME

This document defines the maintenance rules that keep `wiki runtime` stable at larger scale.

## Maintenance Loops

- `weekly`
  - check `stale_flag` candidates
  - detect duplicate notes
  - update conflict markers

- `monthly`
  - review promotion and demotion candidates
  - refresh `supersession`
  - rebuild indexes

## Automatic Cleanup Rules

- Notes with `supersession` are treated as `stale_flag=true`.
- Rejected `wiki_lite` notes move to `LOG`.
- If two or more `wiki` notes conflict, register `conflict_with`.

## Promotion And Demotion Hooks

- Promotion candidates should be reviewed within 7 days after they are marked `adopt` in `wiki_lite`.
- Demotion candidates should be reviewed within 30 days after they are marked `stale_flag=true`.

## Minimum Schedule

- `build_all.ps1` once per month
- `query.ps1` for day-to-day questions
- `promote.ps1` once per week
- `conflict.ps1` once per week
- `staleness.ps1` once per week
- `mark_conflicts.ps1` when conflict markers need to be applied
- `mark_stale.ps1` when stale markers need to be applied
- `repair_queue.ps1` when a repair worklist is needed
