# MAP

## Structure

```text
wiki-runtime/
  README.md
  START_HERE.md
  MAP.md
  POLICY.md
  QUALITY_METADATA.md
  RETRIEVAL_POLICY.md
  WORKFLOW_SURFACE.md
  MODE_SURFACE.md
  scripts/
  reports/
  templates/
  wiki/
  wiki_lite/
  retrieval/
  validation/
  vendor/
```

## Core Layers

- `wiki_lite`
  - intake layer for new material and recent work
- `wiki`
  - canon layer for long-lived notes
- `retrieval`
  - read-order layer that narrows what to open first
- `scripts`
  - command surface for `ingest`, `compile`, `query`, `lint`, and `repair`
- `reports`
  - `operator`, `supervisor`, and `governance` status surfaces

## Public Surface

For first use, remember only this:

- documents:
  - `README.md`
  - `START_HERE.md`
  - `POLICY.md`
  - `QUALITY_METADATA.md`
  - `RETRIEVAL_POLICY.md`
- commands:
  - `ingest`
  - `compile`
  - `query`
  - `lint`
  - `repair`
- surfaces:
  - `reports/operator_latest.md`
  - `reports/supervisor_latest.md`
  - `reports/governance_latest.md`

## Default Flow

1. Put new material in `wiki_lite/RAW`.
2. Run `ingest` to produce `wiki_lite/WIKI` and `wiki_lite/LOG`.
3. Run `compile` to refresh hot and cold indexes.
4. Read in this order:
   `retrieval -> wiki canon -> wiki_lite -> source trace`
5. Run `lint` and `repair` to keep wiki quality stable.
6. Promote only stable notes into `wiki` canon.

## Advanced References

Go deeper only when needed.

- Maintenance:
  - `MAINTENANCE_RUNTIME.md`
  - `CONFLICT_ENGINE.md`
  - `STALENESS_ENGINE.md`
  - `REPAIR_QUEUE_ENGINE.md`
- Promotion and update:
  - `PROMOTION_QUEUE_ENGINE.md`
  - `CANON_UPDATE_ENGINE.md`
  - `MERGE_DECISION_ENGINE.md`
- Operations:
  - `MODE_SURFACE.md`
  - `REPORT_ARCHIVE_POLICY.md`
  - `USAGE_CENTERED_LOAD_TEST_PLAN.md`

## Query Flow

1. narrow candidates with `retrieval`
2. read `wiki` canon first
3. compare with recent `wiki_lite` notes
4. inspect source trace only when needed

## Operator Flow

1. `reports/operator_latest.md`
2. `reports/supervisor_latest.md`
3. `reports/governance_latest.md`
4. open `reports/*_daily_YYYYMMDD.md` only when a dated summary is needed
