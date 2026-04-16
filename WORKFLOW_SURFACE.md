# WORKFLOW SURFACE

This document defines the simple outer workflow surface that exposes the internal runtime as a small set of practical commands.

## Core Commands

- `ingest`
  - Converts new raw input into real lite notes and records the trail.
- `compile`
  - Rebuilds hot and cold indexes and carries the current maintenance snapshot with it.
- `query`
  - Queries the compiled knowledge surface.
  - With `-SaveResidue`, stores retrieval residue as a note for later work.
- `lint`
  - Checks missing metadata, conflicts, and stale candidates in one pass.
  - Also checks `broken wikilink`, `broken evidence ref`, and `empty core section`.
- `repair`
  - Turns inspection output into a real work queue and shows the highest-priority items first.
  - Reuses the existing queue report when the state is unchanged.
- `watch`
  - Watches `wiki_lite/RAW` and triggers `intake-autorun` when new input settles.
  - Refuses to start if `autopilot full` is already watching the same raw-intake surface.
- `mode`
  - Single entry surface for `starter / runtime / autopilot`.
  - `starter` shows explanation and manual-use guidance, `runtime` runs the supervisor path, and `autopilot` runs long loops.
  - `intake_loop` and `autopilot full` cannot start together because they share the same raw-intake surface.

## Promotion Helper Commands

- `promote-preview`
  - Decides whether the current lite note is `ready / review / blocked`.
- `promote`
  - Promotes only notes whose preview result is `ready`.
  - Use `--force` only for exceptions.
- `promotion-queue`
  - Builds one promotion queue across the full `wiki_lite` workspace.
  - Puts immediate promotion items and reinforcement candidates at the top.
- `update-queue`
  - Separates candidates that already point to an existing canon note.
  - Treats them as update work, not new promotion.
- `refresh-canon`
  - Applies actual refreshes for `refresh existing` items from the update queue.
  - Use it when a canon note from the same source no longer matches the current lite note.
- `merge-preview`
  - Measures overlap between an existing canon note and a new candidate in merge-review cases.
  - Recommends `merge_into_existing / fork_new_target / keep_existing / review_manually`.
- `merge-apply`
  - Applies the chosen merge action.
  - Run `merge-preview` first.

## Higher-Level Operational Commands

- `governance-cycle`
  - Refreshes repair, promotion, and update surfaces together.
  - Summarizes current wiki state and next action at the top of the report.
  - Human-first reading should start from `reports/governance_latest.md` and the current `governance_daily_YYYYMMDD.md`.
  - Also refreshes `reports/operator_latest.md` at the end.
  - Realigns daily headers to the current date if they drift.
  - Reuses the existing cycle report and latest daily entry when input is unchanged.
  - Creates new cycle and daily entries only when the input actually changes.
  - Suppresses unnecessary cycle regeneration from unrelated root-doc or residue changes.
  - Suppresses regeneration caused only by file mtime changes.
  - Suppresses queue regeneration when only non-queue metadata fields change.
- `supervisor-cycle`
  - Runs the most common workflow chain by mode.
  - Also leaves a governance report at the end.
  - Human-first reading should use `reports/supervisor_latest.md` and the current `supervisor_daily_YYYYMMDD.md`.
  - Also refreshes `reports/operator_latest.md` at the end.
  - Realigns daily headers to the current date if they drift.
  - Reuses the existing cycle report and latest daily entry when input is unchanged.
  - Creates new cycle and daily entries only when the input actually changes.
  - Suppresses unnecessary cycle regeneration from unrelated root-doc or residue changes.
  - Suppresses regeneration caused only by file mtime changes.
  - Suppresses queue regeneration when only non-queue metadata fields change.
- `intake-autorun`
  - Chains compile and governance only when ingest actually creates new lite notes.
- `maintenance-autorun`
  - Adds repair when lint is not clean, then leaves a governance surface.
  - Skips repair and governance regeneration when the lint fingerprint is unchanged.
- `query residue`
  - Stores retrieval traces as lite assets instead of saving full answer prose.
  - This matches the current retrieval-centered query design better.
  - Residue is treated as usage trace, not as a canon promotion candidate, so it stays out of promotion and update queues.

## Validation Support Commands

- `validate`
  - Checks document alignment, lint cleanliness, recent load-test freshness, and leftover test artifacts against the TOML validation profile.
  - Also checks operator and supervisor state language, surface rendering, and sandbox lock/archive behavior.
  - `./scripts/validate_markdown.ps1` renders the same result as a human-readable Markdown surface.
  - `./scripts/validate_failure_example.ps1` shows a synthetic failure example immediately.
  - `./scripts/generate_validation_failure_example.ps1` regenerates `validation/VALIDATION_FAILURE_EXAMPLE.md`.
  - `validation/VALIDATION_FAILURE_EXAMPLE.md` is a derived example artifact and should be regenerated rather than edited manually.
- `archive-reports`
  - Use dry-run first to inspect archive candidates, then `-Apply` to move them.
  - Archive advisory values also appear in `status`, `governance_latest`, and `supervisor_latest`.
  - The surface now shows not only total candidate count but also which report families are piling up.
- `operator-summary`
  - Compresses `governance_latest`, `supervisor_latest`, lock state, and archive advisory into one operator surface.
  - Read `operator_latest` as the current operations board, and `governance_latest` or `supervisor_latest` as last-cycle records.
  - Use it when you want one file to open first.
- `lock-status`
  - Shows whether `autopilot.lock` and `watch.lock` are running, stale, or absent.
  - Enforces mutual exclusion between `watch` and `autopilot full`.
  - Also uses `intake_scope.lock` internally to reduce cross-competition on the raw-intake surface.
- `clear-stale-locks`
  - Removes only stale locks and preserves live loop locks.

## Why This Surface Exists

- As internal runtime logic grows stronger, the outer command surface should become simpler.
- Users remember task names more easily than internal engine names like `maintenance`, `conflict`, or `staleness`.
- This surface hides internal structure without giving up real operational control.
