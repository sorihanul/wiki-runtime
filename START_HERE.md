# START HERE

This package is a wiki runtime for keeping a large `wiki` readable, searchable, and maintainable.

Start with these five documents:

1. [MAP.md](/F:/LLM/GitHub/wiki-runtime/MAP.md)
2. [POLICY.md](/F:/LLM/GitHub/wiki-runtime/POLICY.md)
3. [QUALITY_METADATA.md](/F:/LLM/GitHub/wiki-runtime/QUALITY_METADATA.md)
4. [RETRIEVAL_POLICY.md](/F:/LLM/GitHub/wiki-runtime/RETRIEVAL_POLICY.md)
5. [WORKFLOW_SURFACE.md](/F:/LLM/GitHub/wiki-runtime/WORKFLOW_SURFACE.md)

## Core Rules

- new material enters through `wiki_lite`
- only durable notes move into `wiki` canon
- `retrieval` is a read-order router, not the knowledge store
- `operator` is the first operations surface, but real read priority is decided by `RETRIEVAL_POLICY`

## First Run Order

1. `powershell -ExecutionPolicy Bypass -File "./scripts/operator_summary.ps1"`
2. `powershell -ExecutionPolicy Bypass -File "./scripts/mode.ps1" -Mode starter -Action show`
3. `powershell -ExecutionPolicy Bypass -File "./scripts/ingest.ps1"`
4. `powershell -ExecutionPolicy Bypass -File "./scripts/compile.ps1"`
5. `powershell -ExecutionPolicy Bypass -File "./scripts/query.ps1" -Query "your question"`
6. `powershell -ExecutionPolicy Bypass -File "./scripts/lint.ps1"`
7. `powershell -ExecutionPolicy Bypass -File "./scripts/repair.ps1"`

Use `./scripts/watch.ps1` only when you actually want a repeating intake watcher.

## First Surfaces To Open

1. `reports/operator_latest.md`
2. `reports/supervisor_latest.md`
3. `reports/governance_latest.md`

Interpretation rule:

- `operator_latest` is the current operations board
- `supervisor_latest` and `governance_latest` are latest cycle records
- if counts differ, read them according to role before assuming drift

## Query Read Order

1. narrow candidates with `retrieval`
2. read `wiki` canon first
3. compare with recent `wiki_lite` notes
4. check source traces only when the decision still needs support

## Advanced References

Open only when needed.

- Maintenance:
  - [MAINTENANCE_RUNTIME.md](/F:/LLM/GitHub/wiki-runtime/MAINTENANCE_RUNTIME.md)
  - [CONFLICT_ENGINE.md](/F:/LLM/GitHub/wiki-runtime/CONFLICT_ENGINE.md)
  - [STALENESS_ENGINE.md](/F:/LLM/GitHub/wiki-runtime/STALENESS_ENGINE.md)
  - [REPAIR_QUEUE_ENGINE.md](/F:/LLM/GitHub/wiki-runtime/REPAIR_QUEUE_ENGINE.md)
- Promotion and update:
  - [PROMOTION_QUEUE_ENGINE.md](/F:/LLM/GitHub/wiki-runtime/PROMOTION_QUEUE_ENGINE.md)
  - [CANON_UPDATE_ENGINE.md](/F:/LLM/GitHub/wiki-runtime/CANON_UPDATE_ENGINE.md)
  - [MERGE_DECISION_ENGINE.md](/F:/LLM/GitHub/wiki-runtime/MERGE_DECISION_ENGINE.md)
- Operations:
  - [MODE_SURFACE.md](/F:/LLM/GitHub/wiki-runtime/MODE_SURFACE.md)
  - [REPORT_ARCHIVE_POLICY.md](/F:/LLM/GitHub/wiki-runtime/REPORT_ARCHIVE_POLICY.md)
  - [USAGE_CENTERED_LOAD_TEST_PLAN.md](/F:/LLM/GitHub/wiki-runtime/USAGE_CENTERED_LOAD_TEST_PLAN.md)
  - [PUBLISHING_GITHUB.md](/F:/LLM/GitHub/wiki-runtime/PUBLISHING_GITHUB.md)

## Validation Reading

If `./scripts/validate.ps1` passes, you can trust at least these:

- entry-document alignment
- lint cleanliness
- `operator` state-language alignment
- latest and daily surface sync
- cycle artifact suppression for unchanged input
- selective regeneration when input changes
- lock and archive behavior

Two risks still need separate verification:

- long-running loop contention
- long-duration performance at larger scale

## Derived Validation Surface

- `validation/VALIDATION_FAILURE_EXAMPLE.md` is generated
- do not edit it manually
- regenerate it with `./scripts/generate_validation_failure_example.ps1`
