param(
    [ValidateSet("starter", "runtime", "autopilot")]
    [string]$Mode = "starter",

    [ValidateSet("show", "run")]
    [string]$Action = "show",

    [ValidateSet("intake", "maintenance", "full")]
    [string]$RuntimeMode = "full",

    [double]$Interval = 2.0,
    [double]$SettleSeconds = 4.0,
    [double]$MaintenanceEveryMinutes = 15.0
)

$ErrorActionPreference = "Stop"
$script_path = Join-Path $PSScriptRoot "wiki_runtime.py"

if ($Action -eq "show") {
    python $script_path mode-brief --mode $Mode
    exit 0
}

switch ($Mode) {
    "starter" {
        python $script_path mode-brief --mode starter
    }
    "runtime" {
        python $script_path supervisor-cycle --mode $RuntimeMode
    }
    "autopilot" {
        python -u $script_path autopilot --interval $Interval --settle-seconds $SettleSeconds --maintenance-every-minutes $MaintenanceEveryMinutes
    }
}
