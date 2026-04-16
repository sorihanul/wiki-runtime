# LOCK RUNTIME POLICY

This document defines the minimum policy for inspecting and clearing long-running loop locks.

It covers only two lock files:

- `autopilot.lock`
- `watch.lock`

## Lock States

- `running`
  - the recorded PID is still alive
  - the lock must not be removed

- `stale`
  - the lock file exists but the PID is no longer alive
  - the lock can be removed safely

- `absent`
  - the lock file does not exist
  - the loop is not currently locked

## Commands

- check status
  - `powershell -ExecutionPolicy Bypass -File "./scripts/lock_status.ps1"`
- clear stale locks
  - `powershell -ExecutionPolicy Bypass -File "./scripts/clear_stale_locks.ps1"`

## Rules

- Never remove a live lock.
- Remove only dead locks.
- Keep stale-lock cleanup at loop startup.
- If the state is unclear, check `lock-status` first.
