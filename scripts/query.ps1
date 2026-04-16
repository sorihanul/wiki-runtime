param(
    [Parameter(Mandatory = $true)]
    [string]$Query,
    [int]$TopK = 10,
    [string]$Domain,
    [double]$ReliabilityMin,
    [double]$HotWeight = 0.7,
    [switch]$SaveResidue
)

$ErrorActionPreference = "Stop"
$script_path = Join-Path $PSScriptRoot "wiki_runtime.py"

$args = @(
    $script_path,
    "query",
    $Query,
    "-k",
    $TopK
)

if ($Domain) {
    $args += @("--domain", $Domain)
}
if ($PSBoundParameters.ContainsKey("ReliabilityMin")) {
    $args += @("--reliability-min", $ReliabilityMin)
}
if ($PSBoundParameters.ContainsKey("HotWeight")) {
    $args += @("--hot-weight", $HotWeight)
}
if ($SaveResidue) {
    $args += "--save-residue"
}

python @args
