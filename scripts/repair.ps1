param(
    [switch]$AutoCycle
)

$ErrorActionPreference = "Stop"
$script_path = Join-Path $PSScriptRoot "wiki_runtime.py"

if ($AutoCycle) {
    python $script_path workflow-maintenance-autorun
}
else {
    python $script_path workflow-repair
}
