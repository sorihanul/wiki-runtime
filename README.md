# wiki-runtime

`wiki-runtime` is a three-layer wiki runtime for keeping a large note base readable, retrievable, and maintainable over time.

This repository is a public reference implementation derived from a separate local working repository. Treat it as an adaptation base for a wiki system, not as a turnkey product.

## What It Does

- Handles new material in `wiki_lite`
- Promotes only durable notes into `wiki` canon
- Uses `retrieval` to narrow read order before full reading
- Uses `lint` and `repair` to keep wiki quality stable

The goal is not a giant autonomous brain. The goal is a stable `wiki` that stays readable, searchable, and maintainable.

## Quick Start

Read in this order:

1. [START_HERE.md](./START_HERE.md)
2. [MAP.md](./MAP.md)
3. [POLICY.md](./POLICY.md)
4. [QUALITY_METADATA.md](./QUALITY_METADATA.md)
5. [RETRIEVAL_POLICY.md](./RETRIEVAL_POLICY.md)
6. [PUBLIC_RELEASE_CHECKLIST.md](./PUBLIC_RELEASE_CHECKLIST.md)
7. [AUTOMATION_PIPELINE.md](./AUTOMATION_PIPELINE.md)

Run in this order:

1. `powershell -ExecutionPolicy Bypass -File "./scripts/operator_summary.ps1"`
2. `powershell -ExecutionPolicy Bypass -File "./scripts/mode.ps1" -Mode starter -Action show`
3. `powershell -ExecutionPolicy Bypass -File "./scripts/ingest.ps1"`
4. `powershell -ExecutionPolicy Bypass -File "./scripts/compile.ps1"`
5. `powershell -ExecutionPolicy Bypass -File "./scripts/query.ps1" -Query "your question"`
6. `powershell -ExecutionPolicy Bypass -File "./scripts/lint.ps1"`
7. `powershell -ExecutionPolicy Bypass -File "./scripts/repair.ps1"`

Check these generated surfaces after a run:

- `reports/operator_latest.md`
- `reports/supervisor_latest.md`
- `reports/governance_latest.md`

## Runtime Layout

- `wiki_lite`: intake layer for new material and recent work
- `wiki`: canon layer for long-lived notes
- `retrieval`: read-order layer for narrowing what to open first
- `scripts`: command surface for `ingest`, `compile`, `query`, `lint`, and `repair`
- `reports`: generated `operator`, `supervisor`, and `governance` status surfaces
- `templates`: note and log templates used by the runtime
- `validation`: baseline validation rules and failure examples

## Default Workflow

1. Put new material into `wiki_lite/RAW`.
2. Run `ingest` to create lite notes and logs.
3. Run `compile` to rebuild hot and cold indexes.
4. Run `query`, then read in this order: `retrieval -> wiki canon -> wiki_lite -> source trace`.
5. Run `lint` and `repair` to keep the wiki clean.
6. Promote only notes that have enough long-term value for canon.

## Further Reading

- Policy: [POLICY.md](./POLICY.md), [QUALITY_METADATA.md](./QUALITY_METADATA.md), [RETRIEVAL_POLICY.md](./RETRIEVAL_POLICY.md)
- Maintenance: [MAINTENANCE_RUNTIME.md](./MAINTENANCE_RUNTIME.md), [CONFLICT_ENGINE.md](./CONFLICT_ENGINE.md), [STALENESS_ENGINE.md](./STALENESS_ENGINE.md), [REPAIR_QUEUE_ENGINE.md](./REPAIR_QUEUE_ENGINE.md)
- Promotion and update: [PROMOTION_QUEUE_ENGINE.md](./PROMOTION_QUEUE_ENGINE.md), [CANON_UPDATE_ENGINE.md](./CANON_UPDATE_ENGINE.md), [MERGE_DECISION_ENGINE.md](./MERGE_DECISION_ENGINE.md)
- Operational surfaces: [WORKFLOW_SURFACE.md](./WORKFLOW_SURFACE.md), [MODE_SURFACE.md](./MODE_SURFACE.md), [REPORT_ARCHIVE_POLICY.md](./REPORT_ARCHIVE_POLICY.md), [USAGE_CENTERED_LOAD_TEST_PLAN.md](./USAGE_CENTERED_LOAD_TEST_PLAN.md)

## Retrieval Wiring

Wire the retrieval backend with one of these:

- Environment variable `WIKI_RETRIEVAL_SCRIPT`
- `./vendor/ivk2_improved.py`

The legacy alias `WIKI_IVK2_SCRIPT` is still accepted.

## Validation Baseline

If `./scripts/validate.ps1` passes, you can trust at least these:

- Entry-document alignment
- Lint cleanliness
- `operator / supervisor / governance` latest surface sync
- No duplicate cycle artifacts for unchanged input
- Selective regeneration when meaningful input changes
- Lock and archive behavior in the sandbox

Separate checks are still required for long-running loop contention and very large long-duration workloads.
