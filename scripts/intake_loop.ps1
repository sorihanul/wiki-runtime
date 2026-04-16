param(
    [double]$Interval = 2.0,
    [double]$SettleSeconds = 4.0
)

$ErrorActionPreference = "Stop"
$script_path = Join-Path $PSScriptRoot "wiki_runtime.py"
python -u $script_path watch --interval $Interval --settle-seconds $SettleSeconds
