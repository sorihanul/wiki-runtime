param(
    [Parameter(Mandatory = $true)]
    [string]$SourceName,
    [ValidateSet("topics", "entities", "concepts", "syntheses")]
    [string]$Kind = "topics",
    [string]$TargetName
)

$ErrorActionPreference = "Stop"
$script_path = Join-Path $PSScriptRoot "wiki_runtime.py"

$args = @(
    $script_path,
    "promote-preview",
    $SourceName,
    "--kind",
    $Kind
)

if ($TargetName) {
    $args += @("--target-name", $TargetName)
}

python @args
