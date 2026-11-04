# Simulations with a price for the PV energy sent to the grid.
# Run from the repo root, once per window, each in its own PowerShell:
#     .\run_export_series.ps1 1
#     .\run_export_series.ps1 2
#     .\run_export_series.ps1 3
# Window 1: four boats, no grid limit, seven solar/battery sizes, seeds 1-3
# Window 2: four boats, 100 kWp + 200 kWh, grid limit 150/120/100/80 kW, seeds 1-3
# Window 3: 100 kWp + 200 kWh with 2, 3, 5, 6, 8 and 10 boats, seed 1
# Each window works in its own copy of the repo (pyport_sim_w1, ...) so the database files of the windows
# do not collide. Results go to results\export of the real repo. A run whose CSV already exists is skipped,
# so the script can be started again after an interruption.
param([int]$Window = 1, [double]$ExportPrice = 0.05)

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$repo = (Get-Location).Path
$work = $repo + "_w" + $Window
$out = Join-Path $repo "results\export"
New-Item -ItemType Directory -Force $out | Out-Null

if (-not (Test-Path $work)) {
    robocopy $repo $work /E /XD results old_results results_summary .git __pycache__ /XF *.db /NFL /NDL /NJH /NJS /NP | Out-Null
}
Set-Location $work

function Run([string]$tag, [string[]]$extra) {
    $csv = Join-Path $out ($tag + ".csv")
    if (Test-Path $csv) { Write-Host "skip $tag (already done)"; return }
    Write-Host ((Get-Date).ToString("HH:mm") + "  $tag")
    python garmin_scaling_experiment.py @extra --export-price $ExportPrice --out-csv $csv 2>&1 | Tee-Object (Join-Path $out ("log_" + $tag + ".txt")) | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Warning "$tag failed, see results\export\log_$tag.txt" }
}

$plants = @(@(50, 0), @(50, 100), @(100, 0), @(100, 100), @(100, 200), @(150, 0), @(150, 100))

switch ($Window) {
    1 {
        foreach ($seed in 1, 2, 3) {
            foreach ($p in $plants) {
                Run ("pv" + $p[0] + "_b" + $p[1] + "_n4_s" + $seed) @("--boat-counts", "4", "--pv-kwp", $p[0], "--bess-kwh", $p[1], "--seed", $seed)
            }
        }
    }
    2 {
        foreach ($seed in 1, 2, 3) {
            foreach ($cap in 150, 120, 100, 80) {
                Run ("pv100_b200_n4_cap" + $cap + "_s" + $seed) @("--boat-counts", "4", "--pv-kwp", "100", "--bess-kwh", "200", "--grid-limit-kw", $cap, "--seed", $seed)
            }
        }
    }
    3 {
        Run "pv100_b200_fleet_s1" @("--boat-counts", "2", "3", "5", "6", "8", "10", "--pv-kwp", "100", "--bess-kwh", "200", "--seed", "1")
    }
}
Set-Location $repo
Write-Host "Window $Window finished."
