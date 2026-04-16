param(
    [Parameter(Mandatory = $true)]
    [string]$SourceName,
    [ValidateSet("topics", "entities", "concepts", "syntheses")]
    [string]$Kind = "topics",
    [Parameter(Mandatory = $true)]
    [string]$TargetName
)

$ErrorActionPreference = "Stop"
$script_path = Join-Path $PSScriptRoot "wiki_runtime.py"

$args = @(
    $script_path,
    "merge-preview",
    $SourceName,
    "--kind",
    $Kind,
    "--target-name",
    $TargetName
)

python @args
