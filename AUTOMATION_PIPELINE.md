# Automation Pipeline

This document describes a general automation model for `wiki-runtime`.

It is intentionally written as a reusable reference.
It does not assume any private folder layout, user-specific workspace, or local machine path.

## Goal

The goal is not to turn every markdown file into canon automatically.

The goal is to:

- collect newly created markdown files from defined source folders
- evaluate whether they are usable wiki material
- send accepted material into `wiki_lite/RAW`
- run the normal runtime path
- apply a conservative promotion gate for canon
- keep ambiguous or low-confidence items in queues instead of forcing them forward

The core rule is simple:

- collect broadly
- promote narrowly

## Pipeline Stages

The recommended pipeline has five stages.

1. `collector`
- watches defined source folders
- captures new `.md` files
- records metadata and deduplicates by path, modified time, and content hash

2. `evaluator`
- reads collected candidates
- classifies them as:
  - `accept`
  - `hold`
  - `reject`

3. `intake`
- sends accepted items into `wiki_lite/RAW`
- runs:
  - `ingest`
  - `compile`
  - optionally `lint`

4. `promotion_gate`
- reviews `wiki_lite/WIKI` notes
- decides whether a note is:
  - `promotion_ready`
  - `promotion_hold`
  - `promotion_rejected`

5. `maintenance`
- runs periodic quality and cleanup routines
- includes:
  - `lint`
  - `repair`
  - report archival
  - queue refresh

## Suggested Automation Layout

One practical layout is:

```text
automation/
  WATCH/
    SOURCES/
    RULES/
  QUEUE/
    collected/
    accepted/
    held/
    rejected/
    promotion_ready/
    promotion_hold/
    promotion_rejected/
    maintenance/
  LOG/
    collector/
    evaluator/
    intake/
    promotion/
    maintenance/
  STATE/
    collector_state.json
    evaluator_state.json
    intake_state.json
    promotion_state.json
    maintenance_state.json
```

This keeps automation state separate from the wiki runtime itself.

## Source-Folder Rules

The collector should only watch explicitly registered source folders.

Recommended rules:

- watch only `.md` files
- use recursive scanning only where needed
- store file metadata before evaluation
- deduplicate using at least:
  - source path
  - modified timestamp
  - content hash

Avoid watching generated runtime folders directly unless that is a deliberate secondary-harvest workflow.

Examples of folders that are usually poor default watch targets:

- runtime logs
- index folders
- cache folders
- previously generated queue folders

## Evaluation Policy

The evaluator should decide only whether a file is worth entering the wiki intake path.

It should not decide final canon structure.

### `accept`

Use `accept` when the file:

- contains reusable explanation, synthesis, or structured notes
- is more than transient chatter or scratch text
- has enough content to survive light transformation
- could plausibly help future retrieval or knowledge reuse

### `hold`

Use `hold` when the file:

- looks useful but is ambiguous
- may be duplicate or too noisy
- needs a human or later pass
- has mixed value and should not be pushed forward automatically

### `reject`

Use `reject` when the file is primarily:

- temporary scratch text
- operational residue
- low-content chatter
- empty or near-empty markdown
- generated output with no reuse value

## Intake Rules

Accepted files should be wrapped or copied into `wiki_lite/RAW`.

After that, the runtime should follow its normal path:

1. `ingest`
2. `compile`
3. optional `lint`

The intake stage should preserve source trace information.

Useful metadata fields include:

- source path
- source bucket
- import timestamp
- import mode

## Promotion Gate

This is the most conservative layer.

Automatic promotion into canon should happen only when the note strongly satisfies the runtime's promotion criteria.

Typical requirements:

- promotable status
- reusable claim shape
- non-empty distilled signal
- reusable rule present
- acceptable evidence strength
- acceptable confidence
- acceptable scope
- no obvious canon conflict
- no serious freshness problem

If the result is ambiguous, the note should go to `promotion_hold`, not to canon.

## Maintenance Layer

Maintenance should be periodic, bounded, and boring.

Recommended tasks:

- refresh lint state
- generate or refresh repair queues
- archive old report surfaces
- refresh hold queues
- refresh promotion-review queues

Maintenance should not:

- redesign the runtime structure
- make broad merge decisions automatically
- rewrite canon aggressively

## Human Role

In a healthy automation setup, humans should not process every file manually.

Humans should mostly see:

- `hold` queue
- `promotion_hold` queue
- repair queue
- conflict and staleness queue

That means automation handles repetition, while humans handle exceptions.

## Recommended Implementation Order

Do not implement the full system all at once.

Build it in this order:

### Phase 1

- collector
- evaluator
- intake

This gives a usable intake pipeline quickly.

### Phase 2

- lint automation
- repair queue refresh
- report archival

### Phase 3

- promotion gate
- promotion-ready and promotion-hold queues

### Phase 4

- scheduled maintenance
- long-running watch loops
- exception queue summaries

## Validation Checklist

Automation should be verified stage by stage.

### Collection

- new markdown files are detected
- already processed files are not duplicated

### Evaluation

- obvious low-value files are rejected
- reusable notes are accepted
- ambiguous files are held

### Intake

- accepted files appear in `wiki_lite/RAW`
- `ingest` runs successfully
- `compile` runs successfully

### Promotion

- weak notes do not auto-promote
- strong notes can be surfaced as promotion-ready
- ambiguous notes land in promotion-hold

### Maintenance

- repair queues refresh correctly
- report archival triggers when accumulation thresholds are met

## One-Line Summary

`wiki-runtime` automation should not try to automate certainty.
It should automate collection, triage, intake, and bounded maintenance, while keeping canon promotion deliberately conservative.
