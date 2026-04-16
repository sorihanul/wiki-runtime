# USAGE CENTERED LOAD TEST PLAN

This document defines the usage-centered load test plan for validating `wiki-runtime` at larger scale.

## Goal

- Check whether usability holds as document count grows.
- The real criterion is not storage volume, but whether `question -> retrieval -> judgment -> next action` still works.
- Before raw performance numbers, check whether the runtime still produces usable answers, usable work queues, and usable canon.

## Core Questions

- When the corpus grows to 100, 1,000, or 10,000 notes, does `query` still narrow to readable candidates?
- When conflict and stale notes are mixed in, do `lint` and `repair` still reduce human effort?
- Even when compile cost grows, does the runtime avoid collapsing into a full reread model?
- Do `wiki_lite` and `wiki` keep their roles without blurring together?

## Test Principles

- Measure usage performance before storage performance.
- Check whether the design still avoids reading the whole corpus.
- It matters more to learn where the runtime breaks under deliberate stress than to produce a clean no-issue run.

## Scale

- `S`
  - about `100` notes
  - basic flow verification
- `M`
  - about `1,000` notes
  - mixed conflict, stale, and supersession conditions
- `L`
  - about `10,000` notes
  - checks retrieval bias, duplicate accumulation, and rising inspection cost

## Dataset Families

- `healthy`
  - healthy notes with solid metadata
- `conflict`
  - duplicate title, shared source, or conflicting canon cases
- `stale`
  - old freshness, overdue review, and supersession-bound notes
- `bias`
  - a corpus over-concentrated around a specific topic
- `mixed`
  - a mixture of the four families above

## Deliberately Injected Problems

- notes with the same title but different canon content
- two or more canon notes promoted from the same source
- stale notes still marked `stale_flag=false`
- superseded notes that still rise in retrieval
- cases where lite notes outrank canon too often
- notes with valid metadata but weak actual content

## Required Flow Sequence

1. `ingest`
   - confirm that raw and lite workspaces remain visibly separated
2. `compile`
   - confirm hot and cold indexes rebuild correctly
3. `query`
   - confirm query narrows to relevant candidates
4. `lint`
   - confirm missing metadata, conflicts, and stale cases are detected
5. `repair`
   - confirm results are turned into a work queue a human can act on immediately

## Usage Criteria

- Do the top query hits directly help answer the question?
- Can the next action be chosen immediately from the repair queue?
- Does the system expose stale and conflict distinctions clearly?
- Do the roles of canon and lite remain visible in answers and work queues?

## Success Criteria

- `query` does not spread into the whole corpus for the same question
- `lint` does not miss deliberately injected problems
- `mark_conflicts` and `mark_stale` do not over-apply changes
- `repair queue` renders as a readable action list
- paths and indexes stay consistent after `compile`

## Failure Signals

- the same small subset of notes is returned for every question
- lite notes keep overrunning canon
- superseded notes keep appearing at the top
- the repair queue is too long or lists only states without actionable phrasing
- mark commands apply changes too aggressively

## Metrics

- query hit count and layer distribution
- number of policy warnings
- `conflict-report` and `staleness-report` detection counts
- number of notes modified by `mark_*`
- repair-queue generation time and item count
- single-run compile time

## Execution Order

1. `S` healthy set
2. `S` mixed set
3. `M` mixed set
4. `L` bias set
5. `L` mixed set

## First Practical Sequence

1. On the `S` scale, inject 5 conflict cases, 5 stale cases, and 5 supersession cases
2. Run `lint -> mark_* -> repair -> query`
3. If the result diverges from expectation, adjust the rules
4. Then move up to the `M` scale

## Expected Artifacts

- sample test datasets
- execution logs
- repair queue output documents
- failure-case notes
- adjusted policy or metadata rules

## Current Implemented Surface

- `powershell -ExecutionPolicy Bypass -File "./scripts/load_test.ps1" -Scale s`
- This command clones the current runtime into a separate sandbox, seeds synthetic raw and canon data,
  and runs one full pass of `ingest -> compile -> lint -> mark_conflicts -> mark_stale -> repair -> query`.
- Results are written to `./reports/load_test_*.md` and `./reports/load_test_*.json` without touching the original workspace.

## One-Line Conclusion

- The goal of this test is not to prove how many notes can be stored, but whether the runtime remains usable as the corpus grows.
