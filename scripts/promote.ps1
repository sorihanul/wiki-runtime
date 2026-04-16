param(
    [Parameter(Mandatory = $true)]
    [string]$SourceName,
    [ValidateSet("topics", "entities", "concepts", "syntheses")]
    [string]$Kind = "topics",
    [string]$TargetName,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$script_path = Join-Path $PSScriptRoot "wiki_runtime.py"

$args = @(
    $script_path,
    "promote",
    $SourceName,
    "--kind",
    $Kind
)

if ($TargetName) {
    $args += @("--target-name", $TargetName)
}
if ($Force) {
    $args += "--force"
}

python @args
