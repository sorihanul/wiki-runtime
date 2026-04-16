# QUALITY METADATA

This document defines the quality metadata contract that keeps `wiki runtime` stable at larger scale.
`wiki_lite` and `wiki` use the same key family, but the canon layer applies the rules more strictly.

## Required Metadata Keys

- `claim_state`: `fact / inference / opinion / hypothesis`
- `evidence`: evidence link, source trace, or original source location
- `freshness`: `date` or `range`
- `confidence`: `low / medium / high`
- `supersession`: replacement note path or higher-level note path
- `scope`: valid scope, boundary, or applicable domain

## Recommended Metadata Keys

- `source_count`: number of distinct sources
- `source_count_basis`: how `source_count` was derived
- `last_reviewed`: last review date
- `stale_flag`: `true / false`
- `conflict_with`: conflicting note path
- `evidence_mode`: `explicit / listed / trace`
- `confidence_basis`: `explicit / source_count / conservative_default`

## Application Rules

- `wiki_lite` can pass with the minimum set `claim_state / freshness / confidence`.
- `wiki` cannot be promoted without `claim_state / evidence / freshness / confidence / supersession`.
- If a note has `supersession`, it is treated as `stale_flag=true`.
- `conflict_with` is exposed as a retrieval-time conflict warning.
- Auto-generated notes should default to conservative confidence.
- Even when `source_count=1`, the metadata should still show whether that value is `trace_only` or `explicit`.
- If `evidence` points only to a source trace, mark it as `evidence_mode=trace`.

## Example

```yaml
claim_state: fact
evidence: wiki/topics/index.md
freshness: 2026-04-14
confidence: high
supersession: wiki/topics/new-index.md
scope: "wiki_lite promotion rule"
```
