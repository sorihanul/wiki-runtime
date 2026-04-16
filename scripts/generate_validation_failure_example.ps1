$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$output = Join-Path $root "validation\VALIDATION_FAILURE_EXAMPLE.md"
python "$PSScriptRoot\runtime_validate.py" --synthetic-fail --format markdown --output $output
Write-Output $output
