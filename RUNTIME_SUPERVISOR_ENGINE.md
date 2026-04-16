# RUNTIME SUPERVISOR ENGINE

This document defines the higher-level execution surface that chains multiple wiki runtime flows together.

## Why It Exists

- As the runtime grows, the cost of remembering execution order grows with it.
- The supervisor cycle runs multiple flows in a fixed mode sequence.
- It also leaves a governance report so the operator can read the current day state immediately.
- The human-first surfaces are `reports/supervisor_latest.md` and the current `supervisor_daily_YYYYMMDD.md`.
- This surface also exposes state names such as `sync_runtime / repair_runtime / apply_knowledge_changes / idle_watch`.

## Commands

- `powershell -ExecutionPolicy Bypass -File "./scripts/supervisor_cycle.ps1" -Mode intake`
- `powershell -ExecutionPolicy Bypass -File "./scripts/supervisor_cycle.ps1" -Mode maintenance`
- `powershell -ExecutionPolicy Bypass -File "./scripts/supervisor_cycle.ps1" -Mode full`
- `powershell -ExecutionPolicy Bypass -File "./scripts/intake_autorun.ps1"`
- `powershell -ExecutionPolicy Bypass -File "./scripts/maintenance_autorun.ps1"`
- `powershell -ExecutionPolicy Bypass -File "./scripts/intake_loop.ps1"`
- `powershell -ExecutionPolicy Bypass -File "./scripts/maintenance_loop.ps1"`
- `powershell -ExecutionPolicy Bypass -File "./scripts/autopilot.ps1" -Mode full`
- `powershell -ExecutionPolicy Bypass -File "./scripts/mode.ps1" -Mode runtime -Action run -RuntimeMode full`

## Modes

- `intake`
  - ingest -> compile -> governance
- `maintenance`
  - lint -> repair -> governance
- `full`
  - ingest -> compile -> lint -> repair -> governance

## Operating Tiers

- `starter`
  - manual inspection without long-running loops
- `runtime`
  - bounded automation only, such as supervisor and autorun paths
- `autopilot`
  - enables long-running loops
  - should be entered explicitly through `mode.ps1` or `autopilot.ps1`

## Bounded Automation Entry Points

- `ingest.ps1 -AutoCycle`
  - runs compile and governance only when new lite notes are created
- `repair.ps1 -AutoCycle`
  - runs repair and governance when lint is not clean

## Long-Running Entry Points

- `intake_loop.ps1`
  - handles raw-intake monitoring and intake autorun only
- `maintenance_loop.ps1`
  - runs maintenance autorun on a schedule
- `autopilot.ps1 -Mode full`
  - use only when intake and maintenance should be combined in one loop
- `maintenance_loop` and `autopilot full` both use the same `_runtime_state/autopilot.lock`, so they must not run together.
