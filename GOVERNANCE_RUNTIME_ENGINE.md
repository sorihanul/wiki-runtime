# GOVERNANCE RUNTIME ENGINE

This document defines the higher-level surface that bundles `repair -> promotion -> update` into one operational governance pass.

## Why It Exists

- As the runtime grows, the cost of remembering execution order grows with it.
- The governance cycle summarizes current state and next action in one place.
- It helps the operator choose what to do today before opening every individual queue.

## Command

- `powershell -ExecutionPolicy Bypass -File "./scripts/governance_cycle.ps1"`

## Output

- `./reports/governance_cycle_YYYYMMDD_HHMMSS.md`

## Default Handling

- Refresh the repair queue.
- Refresh the promotion queue.
- Refresh the update queue.
- Summarize clean-state signals and top next actions together.
