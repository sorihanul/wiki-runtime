# REPAIR QUEUE ENGINE

This document defines the engine that turns inspection results into an actionable repair queue.

## Why It Exists

- Conflict reports and staleness reports alone still require a human to re-plan the next action.
- The repair queue turns them directly into a worklist for what to read, merge, and review next.

## Command

- `powershell -ExecutionPolicy Bypass -File "./scripts/repair_queue.ps1"`

## Output

- `./reports/repair_queue_YYYYMMDD_HHMMSS.md`

## Default Handling

- Convert conflict candidates into a `merge or clean up` work queue.
- Convert stale candidates into a `review, demote, or confirm replacement` queue.
- Convert weak-basis canon notes into a `metadata confidence queue`.
- Render the queue in the order `priority now -> prioritized queue -> detailed queue` so it can be acted on immediately.

## Priority Rules

- `high`
  - divergent duplicate, explicit conflict, shared source, forced stale
- `medium`
  - old canon stale cases, long-unreviewed canon, canon notes with multiple weak basis signals
- `low`
  - periodic review or single-basis reinforcement items that do not create immediate runtime instability

The goal is not to force full reading of the whole queue.
The goal is to let the operator choose the next action from the top `priority now` lines first.
