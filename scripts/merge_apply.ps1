param(
    [Parameter(Mandatory = $true)]
    [string]$SourceName,
    [ValidateSet("topics", "entities", "concepts", "syntheses")]
    [string]$Kind = "topics",
    [Parameter(Mandatory = $true)]
    [string]$TargetName,
    [Parameter(Mandatory = $true)]
    [ValidateSet("merge_into_existing", "fork_new_target", "keep_existing")]
    [string]$Decision,
    [string]$NewTargetName,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$script_path = Join-Path $PSScriptRoot "wiki_runtime.py"

$args = @(
    $script_path,
    "merge-apply",
    $SourceName,
    "--kind",
    $Kind,
    "--target-name",
    $TargetName,
    "--decision",
    $Decision
)

if ($NewTargetName) {
    $args += @("--new-target-name", $NewTargetName)
}
if ($Force) {
    $args += "--force"
}

python @args
