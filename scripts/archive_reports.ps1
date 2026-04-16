param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$script_path = Join-Path $PSScriptRoot "wiki_runtime.py"

if ($Apply) {
    python $script_path archive-reports --apply
} else {
    python $script_path archive-reports
}
