# Average grid power in the peak hours (for the peak-hour power charge) of the four-boat plants, no grid limit.
# EEM 2026 tariff in medium voltage, PV energy sent to the grid paid 0.05 EUR/kWh, seed 1, trips from the Garmin routes.
# Before the first run, from the repo root:
#     python patch_peakhour.py
# Then, each in its own PowerShell (Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass):
#     .\run_peakhour_series.ps1 1
#     .\run_peakhour_series.ps1 2
# Window 1: nine plants with the optimiser (gives charging on arrival, smart charging and the plant in one run)
# Window 2: the same nine plants without smart charging (charging on arrival + rule-based battery)
# Each window works in its own copy of the repo (pyport_sim_k1, ...) so the database files do not collide.
# Results go to results\peakhour of the real repo. A run whose CSV exists is skipped, so the script can be restarted.
param([int]$Window = 1, [double]$ExportPrice = 0.05)

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$repo = (Get-Location).Path
if (-not (Select-String -Path (Join-Path $repo "boats_scaling_experiment.py") -Pattern "peakhour" -Quiet)) {
    Write-Error "boats_scaling_experiment.py has no peak-hour column: run 'python patch_peakhour.py' first."
    exit 1
}
if (-not (Test-Path (Join-Path $repo "assets\tariff\eem_mt_winter.json"))) {
    Write-Error "assets\tariff\eem_mt_winter.json is missing: run 'python make_eem_tariffs.py' first."
    exit 1
}
$work = $repo + "_k" + $Window
$out = Join-Path $repo "results\peakhour"
New-Item -ItemType Directory -Force $out | Out-Null

if (Test-Path $work) { Remove-Item -Recurse -Force $work }
robocopy $repo $work /E /XD results old_results results_summary .git __pycache__ /XF *.db /NFL /NDL /NJH /NJS /NP | Out-Null
Set-Location $work

function Run([string]$tag, [string[]]$extra) {
    $csv = Join-Path $out ($tag + ".csv")
    if (Test-Path $csv) { Write-Host "skip $tag (already done)"; return }
    Write-Host ((Get-Date).ToString("HH:mm") + "  $tag")
    python garmin_scaling_experiment.py @extra --export-price $ExportPrice --out-csv $csv 2>&1 | Tee-Object (Join-Path $out ("log_" + $tag + ".txt")) | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Warning "$tag failed, see results\peakhour\log_$tag.txt" }
}

$mt = "assets/tariff/eem_mt_{season}.json"
# (pv kWp, battery kWh, battery kW)
$plants = @(@(0, 100, 25), @(0, 200, 100), @(50, 0, 0), @(50, 100, 25), @(100, 0, 0), @(100, 100, 25), @(100, 200, 50), @(150, 0, 0), @(150, 100, 25))

foreach ($p in $plants) {
    $tag = $(if ($Window -eq 1) { "opt" } else { "plain" }) + "_pv" + $p[0] + "_b" + $p[1] + "_p" + $p[2] + "_n4_s1"
    $runArgs = @("--boat-counts", "4", "--pv-kwp", $p[0], "--bess-kwh", $p[1], "--seed", "1", "--tariff-json", $mt)
    if ($p[1] -gt 0) { $runArgs += @("--bess-kw", $p[2]) }
    if ($Window -ne 1) { $runArgs += @("--skip-scheduled", "--plain-der") }
    Run $tag $runArgs
}
