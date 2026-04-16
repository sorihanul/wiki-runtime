# PROMOTION QUEUE ENGINE

This document defines the engine that collects promotion candidates from `wiki_lite` into one operational queue.

## Why It Exists

- If only `promote-preview` exists, notes must be reviewed one by one.
- At larger scale, you need to see `promote now`, `needs stronger evidence`, and `keep in lite` in one surface.
- The promotion queue turns that decision into an operational view using `ready / review / blocked`.

## Command

- `powershell -ExecutionPolicy Bypass -File "./scripts/promotion_queue.ps1"`

## Output

- `./reports/promotion_queue_YYYYMMDD_HHMMSS.md`

## Default Handling

- Scan all notes under `wiki_lite/WIKI`.
- Assign a recommended canon kind for each note.
- If the promotion gate passes, place the note in `ready`.
- If more evidence or metadata is needed, place it in `review`.
- If the note should not be promoted in its current state, place it in `blocked`.

## Operating Rule

- Read the top `promote now` lines first.
- Then process the `ready queue`.
- Revisit the `review queue` after improving evidence, scope, or reusable rule content.
- Send the `blocked queue` either back to lite retention or into the existing canon update path.
