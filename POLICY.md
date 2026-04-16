# POLICY

## Core Law

1. Do not confuse `wiki_lite` with `wiki`.
2. New input starts in `wiki_lite` by default.
3. `wiki` accepts only formally promoted notes.
4. Queries should pass through retrieval candidate narrowing first.
5. Prefer updating existing notes over creating duplicates.

## Promotion Rule

Only consider promotion to `wiki` when most of the following conditions hold:

- it has already been reused more than once
- it has two or more sources or evidence items
- it can be time-scoped
- it is likely to be called again from other questions
- it behaves more like an operating rule or structural knowledge than a simple opinion

The execution gate is stricter:

- if `status!=adopt`, do not promote by default
- if `claim_state=opinion`, do not promote by default
- if `distilled` is empty, do not promote
- if the target canon file already exists, do not overwrite it blindly
- if the note does not meet enough conditions, leave it as `review` or `blocked` in `promote-preview`

## Query Rule

- If recency matters most, check `wiki_lite` first.
- If stability matters most, check `wiki` first.
- If the two conflict, prioritize formal canon rules from `wiki` while still exposing recent signals from `wiki_lite`.

## Reclassification Rule

Each `wiki_lite` note should be classified into one of four states:

- `adopt`
- `already-covered`
- `hold`
- `reject`

Even `reject` leaves a trace in `LOG`.

## Temporal Rule

- Always record dates for date-sensitive claims.
- Treat aging claims through stale markers and review-priority adjustment before deletion.

## Index Rule

- `hot.sqlite` includes only real notes under `wiki_lite\WIKI`.
- `wiki_lite\WIKI\README.md` stays out of the search corpus.
- `cold.sqlite` includes only canon notes under `topics / entities / concepts / syntheses`, not the entire `wiki` tree.
- `wiki\README.md`, `wiki\index.md`, `wiki\log.md`, and folder-level `README.md` files stay out of the search corpus.
- If later expansion is needed, add `global.sqlite` as a separate layer.

## Runtime Link

- Follow `QUALITY_METADATA.md` for the quality metadata contract.
- Follow `RETRIEVAL_POLICY.md` for retrieval policy.
- Follow `MAINTENANCE_RUNTIME.md` for maintenance loops.
- Follow `CONFLICT_ENGINE.md` for conflict review.
- Follow `STALENESS_ENGINE.md` for stale review.
