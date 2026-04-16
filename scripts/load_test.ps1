param(
    [ValidateSet("s", "m", "l")]
    [string]$Scale = "s"
)

python "$PSScriptRoot\runtime_load_test.py" --scale $Scale
