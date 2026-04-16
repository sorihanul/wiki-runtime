# MODE SURFACE

This document defines the outer surface for choosing how heavily to run `wiki-runtime`.

The core rule is simple:

- Do not always run the heaviest mode just because the features exist.

## Three Modes

- `starter`
  - manual inspection first
  - the operator runs ingest, compile, query, lint, and repair directly
  - use it when attaching a new repository or testing stability at small scale

- `runtime`
  - bounded automation
  - uses bundled flows such as `supervisor_cycle`, `intake_autorun`, and `maintenance_autorun`
  - fits operations that run inspection loops several times per day
  - the human-first surfaces are `reports/supervisor_latest.md` and the current `supervisor_daily_YYYYMMDD.md`
  - `mode.ps1 -Action show` also exposes the current `operator` state name and summary

- `autopilot`
  - long-running loop mode
  - choose from `intake-only`, `maintenance-only`, or `full`
  - use it only when a continuously running loop is actually needed
  - `watch` and `autopilot full` are blocked from starting together because they both monitor raw intake

## Single Entry Surface

- show only
  - `powershell -ExecutionPolicy Bypass -File "./scripts/mode.ps1" -Mode starter -Action show`
  - `powershell -ExecutionPolicy Bypass -File "./scripts/mode.ps1" -Mode runtime -Action show`
  - `powershell -ExecutionPolicy Bypass -File "./scripts/mode.ps1" -Mode autopilot -Action show`

- run
  - `starter`
    - `powershell -ExecutionPolicy Bypass -File "./scripts/mode.ps1" -Mode starter -Action run`
    - in practice this still shows guidance only, because starter is a manual mode
  - `runtime`
    - `powershell -ExecutionPolicy Bypass -File "./scripts/mode.ps1" -Mode runtime -Action run -RuntimeMode full`
  - `autopilot`
    - `powershell -ExecutionPolicy Bypass -File "./scripts/mode.ps1" -Mode autopilot -Action run`
    - or `./scripts/intake_loop.ps1`, `./scripts/maintenance_loop.ps1`, `./scripts/autopilot.ps1 -Mode full`
    - if `./scripts/intake_loop.ps1` is already running, `autopilot.ps1 -Mode full` will not start

## Mode Rules

- `starter`
  - no long-running loops
  - default path: `ingest -> compile -> query -> lint -> repair`
  - cheapest operating surface

- `runtime`
  - bounded automation only
  - default path: `supervisor_cycle` or `*_autorun`
  - fits operations where a human still checks results in the middle

- `autopilot`
  - long-running loops enabled
  - `intake_loop.ps1` for intake only
  - `maintenance_loop.ps1` for maintenance only
  - `autopilot.ps1 -Mode full` only when both should be combined in one loop
  - `intake_loop.ps1` and `autopilot.ps1 -Mode full` are mutually exclusive

## Human-First Surfaces

- always open first
  - `./reports/operator_latest.md`
- when daily accumulation matters
  - `./reports/supervisor_daily_YYYYMMDD.md`
  - `./reports/governance_daily_YYYYMMDD.md`
- when detailed operational state is needed
  - `./reports/supervisor_latest.md`
  - `./reports/governance_latest.md`

## One-Line Rule

- `starter` should stay cheap and simple.
- `runtime` is convenient, but still human-checked.
- `autopilot` should be enabled only for long-running operation.
