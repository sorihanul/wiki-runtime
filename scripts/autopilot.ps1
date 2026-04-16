param(
    [ValidateSet("full", "maintenance")]
    [string]$Mode = "full",
    [double]$Interval = 2.0,
    [double]$SettleSeconds = 4.0,
    [double]$MaintenanceEveryMinutes = 15.0
)

$ErrorActionPreference = "Stop"
$script_path = Join-Path $PSScriptRoot "wiki_runtime.py"
python -u $script_path autopilot --mode $Mode --interval $Interval --settle-seconds $SettleSeconds --maintenance-every-minutes $MaintenanceEveryMinutes
