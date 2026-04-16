param(
    [double]$Interval = 2.0,
    [double]$MaintenanceEveryMinutes = 15.0
)

$ErrorActionPreference = "Stop"
$script_path = Join-Path $PSScriptRoot "wiki_runtime.py"
python -u $script_path autopilot --mode maintenance --interval $Interval --settle-seconds 4.0 --maintenance-every-minutes $MaintenanceEveryMinutes
