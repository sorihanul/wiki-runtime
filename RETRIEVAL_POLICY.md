# RETRIEVAL POLICY

This document defines the read-order policy after the retrieval layer narrows the candidate set.

The `operator` surface does not override this policy.
It only compresses the first reading surface into `operator_latest -> supervisor_latest -> governance_latest`.
`operator` is an entry surface. Actual retrieval priority is decided by this document.

## Default Priority

1. `wiki` canon notes
2. recent `wiki_lite` notes
3. source traces

## Weighting Rules

- If `freshness` is recent, increase the `wiki_lite` weight.
- If `confidence` is low, increase the `wiki` weight.
- If `claim_state=opinion`, prefer `wiki_lite` first.
- If `supersession` exists, read the higher-level or replacement note first.

## Metadata Reliability Weights

- `evidence_mode=explicit` carries the strongest trust.
- `evidence_mode=listed` means multiple evidence items are present.
- `evidence_mode=trace` means only a source trace is present and should not be over-trusted.
- `confidence_basis=explicit` means the confidence value was set directly by a human or authoring step.
- `confidence_basis=source_count` means confidence was inferred from evidence count.
- `confidence_basis=conservative_default` means the value is an automatic conservative estimate and should not get excessive priority.
- `source_count_basis=trace_only` means even `source_count=1` should still be treated as a single trace-level source.
- `source_count_basis=evidence_refs` means the count reflects explicitly listed evidence references.

## Operational Interpretation

- Even a `wiki` canon note should be treated as review-priority if `evidence_mode=trace` and `confidence_basis=conservative_default` appear together.
- Weak basis metadata still affects query ranking.
  In practice, `evidence_mode=trace`, `confidence_basis=conservative_default`, and `source_count_basis=trace_only` should reduce default ranking.
- Even when a `wiki_lite` note is recent, canon should win if the `wiki` note has explicit evidence.
- For conflict-oriented questions, notes with `conflict_with` should be ranked higher.
- For `stale`, `supersession`, or `replacement` questions, stale or superseded notes should be ranked higher.

## Conflict Handling

- If `conflict_with` exists, open both notes and record the difference.
- If the conflict persists, leave a `conflict` marker in `wiki`.

## Minimum Retrieval Loop

1. top 10 candidates from the retrieval layer
2. pull 3 notes from `wiki` and 3 from `wiki_lite`
3. check whether there is an active conflict
4. read the source trace only if the decision still needs support
