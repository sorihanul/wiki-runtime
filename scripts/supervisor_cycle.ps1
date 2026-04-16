param(
    [ValidateSet("intake", "maintenance", "full")]
    [string]$Mode = "full"
)

$ErrorActionPreference = "Stop"
$script_path = Join-Path $PSScriptRoot "wiki_runtime.py"
python $script_path supervisor-cycle --mode $Mode
