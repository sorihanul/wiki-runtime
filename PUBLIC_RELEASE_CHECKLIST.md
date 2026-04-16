# Public Release Checklist

Use this checklist before treating the repository as a public release candidate.

## Positioning

- the repository reads like a `wiki runtime`, not like an internal lab dump
- `README`, `START_HERE`, and `MAP` agree on purpose and first-use flow
- the package is centered on wiki quality, not on autonomous runtime claims

## Packaging

- no private absolute paths remain in public-facing docs, templates, or sample notes
- generated databases are ignored
- generated `reports/` output is ignored except for README-level guidance
- generated `_runtime_state/` files are ignored except for README-level guidance
- public-facing sample surfaces are intentional, small, and safe

## Runtime Surface

- first-use commands are still clear:
  - `ingest`
  - `compile`
  - `query`
  - `lint`
  - `repair`
- `operator`, `supervisor`, and `governance` surfaces still read cleanly after regeneration
- user-facing runtime output reads like a public tool, not like a private notebook

## Validation

Run these before release:

1. `python "./scripts/wiki_runtime.py" status`
2. `powershell -ExecutionPolicy Bypass -File "./scripts/validate.ps1"`
3. if runtime surfaces changed, regenerate:
   - `./scripts/governance_cycle.ps1`
   - `./scripts/supervisor_cycle.ps1 -Mode intake`
   - `./scripts/operator_summary.ps1`

## Final Gate

- publish only from the dedicated public repository root
- keep the separate working repository as the source of truth
- do not publish directly from any draft or private workspace

## One-Line Rule

If the repository still looks like a working runtime notebook instead of a reusable wiki package, it is not ready yet.
