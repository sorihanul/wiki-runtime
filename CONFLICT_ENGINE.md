# CONFLICT ENGINE

This document defines how `wiki runtime` detects and reviews conflict conditions.

## What It Detects

- canon notes with the same title
- canon notes promoted from the same source
- notes that already carry `conflict_with`
- notes with the same title but different canon content

## Why It Exists

- At larger scale, retrieval becomes unstable as soon as the same claim is carried by multiple notes.
- Handling conflict only at search time is too late.
- Conflict candidates should be detected first at the canon layer.

## Commands

- `powershell -ExecutionPolicy Bypass -File "./scripts/conflict.ps1"`
- `powershell -ExecutionPolicy Bypass -File "./scripts/mark_conflicts.ps1"`

## Default Handling

- For duplicate titles, check first whether the case is really an update to an existing canon note.
- For shared-source cases, check whether there is a valid reason to keep two separate canon notes.
- For explicit conflicts, verify first that the `conflict_with` target actually exists.

## Conflict Marking

- `mark_conflicts.ps1` writes `conflict_with` directly onto strong conflict candidates.
- At the current stage, only `divergent duplicate`, `shared source`, and `explicit conflict` are treated as auto-mark candidates.
