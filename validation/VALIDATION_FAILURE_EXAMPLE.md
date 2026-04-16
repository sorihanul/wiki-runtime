# validation-report

- profile: `synthetic`
- status: `fail`
- finding_count: `3`

## repair focus
- focus: `state_surface`
  summary: `Realign operator, mode, and supervisor state language.`
  related_checks: `operator_alignment`
- focus: `archive_runtime`
  summary: `Restore the boundary between protected archive surfaces and movable candidates first.`
  related_checks: `archive_sandbox`
- focus: `docs_entry`
  summary: `Realign entry documents and entry-surface language first.`
  related_checks: `doc_alignment`

## next steps
- check: `operator_alignment`
  why: `Operator, mode, and supervisor surfaces use inconsistent state language.`
  first_files: `reports/operator_latest.md, reports/supervisor_latest.md, MODE_SURFACE.md`
  first_command: `./scripts/operator_summary.ps1`
- check: `archive_sandbox`
  why: `Protected archive surfaces and movable candidates are out of sync.`
  first_files: `scripts/wiki_runtime.py, REPORT_ARCHIVE_POLICY.md, reports`
  first_command: `./scripts/archive_reports.ps1`
- check: `doc_alignment`
  why: `Entry documents and entry-surface language are out of sync.`
  first_files: `README.md, START_HERE.md, MAP.md, RETRIEVAL_POLICY.md`

## findings
- check: `operator_alignment`
  path: `reports/supervisor_latest.md`
  message: `synthetic mismatch`
  why: `Operator, mode, and supervisor surfaces use inconsistent state language.`
  first_files: `reports/operator_latest.md, reports/supervisor_latest.md, MODE_SURFACE.md`
  first_command: `./scripts/operator_summary.ps1`
- check: `archive_sandbox`
  path: `reports/`
  message: `synthetic archive drift`
  why: `Protected archive surfaces and movable candidates are out of sync.`
  first_files: `scripts/wiki_runtime.py, REPORT_ARCHIVE_POLICY.md, reports`
  first_command: `./scripts/archive_reports.ps1`
- check: `doc_alignment`
  path: `README.md`
  message: `synthetic doc drift`
  why: `Entry documents and entry-surface language are out of sync.`
  first_files: `README.md, START_HERE.md, MAP.md, RETRIEVAL_POLICY.md`
