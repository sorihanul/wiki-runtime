# wiki-runtime

`wiki-runtime` is a three-layer wiki runtime built to keep a large note base readable, retrievable, and maintainable over time.

This repository is the public derivative of the working source root at `F:\LLM\wiki-runtime`.
It should be read as a reference implementation and adaptation base for a wiki system, not as a turnkey product.

## What It Does

- handles new material in `wiki_lite`
- promotes only durable notes into `wiki` canon
- uses `retrieval` to narrow read order before full reading
- uses `lint` and `repair` to keep wiki quality stable

The goal is not a giant autonomous brain.
The goal is a stable `wiki` that stays readable, searchable, and maintainable.

## Most Users Only Need This

Read these first:

1. [START_HERE.md](/F:/LLM/GitHub/wiki-runtime/START_HERE.md)
2. [MAP.md](/F:/LLM/GitHub/wiki-runtime/MAP.md)
3. [POLICY.md](/F:/LLM/GitHub/wiki-runtime/POLICY.md)
4. [QUALITY_METADATA.md](/F:/LLM/GitHub/wiki-runtime/QUALITY_METADATA.md)
5. [RETRIEVAL_POLICY.md](/F:/LLM/GitHub/wiki-runtime/RETRIEVAL_POLICY.md)
6. [PUBLIC_RELEASE_CHECKLIST.md](/F:/LLM/GitHub/wiki-runtime/PUBLIC_RELEASE_CHECKLIST.md)
7. [AUTOMATION_PIPELINE.md](/F:/LLM/GitHub/wiki-runtime/AUTOMATION_PIPELINE.md)

Run these first:

- `powershell -ExecutionPolicy Bypass -File "./scripts/operator_summary.ps1"`
- `powershell -ExecutionPolicy Bypass -File "./scripts/mode.ps1" -Mode starter -Action show`
- `powershell -ExecutionPolicy Bypass -File "./scripts/ingest.ps1"`
- `powershell -ExecutionPolicy Bypass -File "./scripts/compile.ps1"`
- `powershell -ExecutionPolicy Bypass -File "./scripts/query.ps1" -Query "your question"`
- `powershell -ExecutionPolicy Bypass -File "./scripts/lint.ps1"`
- `powershell -ExecutionPolicy Bypass -File "./scripts/repair.ps1"`

Open these surfaces first:

- `reports/operator_latest.md`
- `reports/supervisor_latest.md`
- `reports/governance_latest.md`

## Core Layers

- `wiki_lite`
  - intake layer for new material and recent work
- `wiki`
  - canon layer for long-lived notes
- `retrieval`
  - read-order layer for narrowing what to open first
- `scripts`
  - command surface for `ingest`, `compile`, `query`, `lint`, and `repair`
- `reports`
  - `operator`, `supervisor`, and `governance` status surfaces

## Default Flow

1. Put new material into `wiki_lite/RAW`.
2. Run `ingest` to create lite notes and logs.
3. Run `compile` to rebuild hot and cold indexes.
4. Run `query` and read in this order:
   `retrieval -> wiki canon -> wiki_lite -> source trace`
5. Run `lint` and `repair` to keep the wiki clean.
6. Promote only notes that have enough long-term value for canon.

## Advanced References

Read only when needed.

Policy:

- [POLICY.md](/F:/LLM/GitHub/wiki-runtime/POLICY.md)
- [QUALITY_METADATA.md](/F:/LLM/GitHub/wiki-runtime/QUALITY_METADATA.md)
- [RETRIEVAL_POLICY.md](/F:/LLM/GitHub/wiki-runtime/RETRIEVAL_POLICY.md)

Maintenance:

- [MAINTENANCE_RUNTIME.md](/F:/LLM/GitHub/wiki-runtime/MAINTENANCE_RUNTIME.md)
- [CONFLICT_ENGINE.md](/F:/LLM/GitHub/wiki-runtime/CONFLICT_ENGINE.md)
- [STALENESS_ENGINE.md](/F:/LLM/GitHub/wiki-runtime/STALENESS_ENGINE.md)
- [REPAIR_QUEUE_ENGINE.md](/F:/LLM/GitHub/wiki-runtime/REPAIR_QUEUE_ENGINE.md)

Promotion and update:

- [PROMOTION_QUEUE_ENGINE.md](/F:/LLM/GitHub/wiki-runtime/PROMOTION_QUEUE_ENGINE.md)
- [CANON_UPDATE_ENGINE.md](/F:/LLM/GitHub/wiki-runtime/CANON_UPDATE_ENGINE.md)
- [MERGE_DECISION_ENGINE.md](/F:/LLM/GitHub/wiki-runtime/MERGE_DECISION_ENGINE.md)

Operational surfaces:

- [WORKFLOW_SURFACE.md](/F:/LLM/GitHub/wiki-runtime/WORKFLOW_SURFACE.md)
- [MODE_SURFACE.md](/F:/LLM/GitHub/wiki-runtime/MODE_SURFACE.md)
- [REPORT_ARCHIVE_POLICY.md](/F:/LLM/GitHub/wiki-runtime/REPORT_ARCHIVE_POLICY.md)
- [USAGE_CENTERED_LOAD_TEST_PLAN.md](/F:/LLM/GitHub/wiki-runtime/USAGE_CENTERED_LOAD_TEST_PLAN.md)

## Retrieval Wiring

Wire the retrieval backend with one of these:

- environment variable `WIKI_RETRIEVAL_SCRIPT`
- `./vendor/ivk2_improved.py`

The legacy alias `WIKI_IVK2_SCRIPT` is still accepted.

## Validation Baseline

If `./scripts/validate.ps1` passes, you can trust at least these:

- entry-document alignment
- lint cleanliness
- `operator / supervisor / governance` latest surface sync
- no duplicate cycle artifacts for unchanged input
- selective regeneration when meaningful input changes
- lock and archive behavior in the sandbox

Separate checks are still required for long-running loop contention and very large long-duration workloads.
