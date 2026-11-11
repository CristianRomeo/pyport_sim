# Sweep of the grid connection for four boats: finds the smallest connection that serves all the trips in each scenario.
# EEM 2026 tariff in medium voltage, PV energy sent to the grid paid 0.05 EUR/kWh, seed 1, Garmin routes.
# From the repo root, once per window, each in its own PowerShell:
#     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#     .\scripts\run_sweep_cap.ps1 1     # charging on arrival, smart charging and a 100 kWh battery at 160, 175, 185 kW; 200 kWh / 100 kW at 60 kW
#     .\scripts\run_sweep_cap.ps1 2     # 200 kWh / 100 kW at 70 kW; 200 kWh / 50 kW at 100 and 110 kW; 100 kWp + 200 kWh / 50 kW at 110 kW
#     .\scripts\run_sweep_cap.ps1 3     # plant with charging on arrival (no smart charging): 200 kWh / 100 kW at 80, 120, 150 kW
# Each window works in its own copy of the repo (pyport_sim_w1, ...). Results go to results\sweep_mv.
# A run whose CSV exists is skipped, so the script can be restarted.
param([int]$Window = 1, [double]$ExportPrice = 0.05)

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$repo = (Get-Location).Path
if (-not (Test-Path (Join-Path $repo "assets\tariff\eem_mt_winter.json"))) {
    Write-Error "assets\tariff\eem_mt_winter.json is missing: run 'python make_eem_tariffs.py' first."
    exit 1
}
$work = $repo + "_w" + $Window
$out = Join-Path $repo "results\sweep_mv"
New-Item -ItemType Directory -Force $out | Out-Null
if (Test-Path $work) { Remove-Item -Recurse -Force $work }
robocopy $repo $work /E /XD results old_results results_summary .git __pycache__ /XF *.db /NFL /NDL /NJH /NJS /NP | Out-Null
Set-Location $work

$mt = "assets/tariff/eem_mt_{season}.json"
# window, solar kWp, battery kWh, battery kW, grid limit kW, plain (1 = plant with charging on arrival, no smart charging)
$jobs = @(
    @(1, 0, 100, 25, 160, 0), @(1, 0, 100, 25, 175, 0), @(1, 0, 100, 25, 185, 0), @(1, 0, 200, 100, 60, 0),
    @(2, 0, 200, 100, 70, 0), @(2, 0, 200, 50, 100, 0), @(2, 0, 200, 50, 110, 0), @(2, 100, 200, 50, 110, 0),
    @(3, 0, 200, 100, 80, 1), @(3, 0, 200, 100, 120, 1), @(3, 0, 200, 100, 150, 1)
)

for ($i = 0; $i -lt $jobs.Count; $i++) {
    $j = $jobs[$i]
    if ($j[0] -ne $Window) { continue }
    $kind = $(if ($j[5] -eq 1) { "plain" } else { "sw" })
    $tag = $kind + "_n4_pv" + $j[1] + "_b" + $j[2] + "_p" + $j[3] + "_cap" + $j[4] + "_s1"
    $csv = Join-Path $out ($tag + ".csv")
    if (Test-Path $csv) { Write-Host "skip $tag (already done)"; continue }
    $runArgs = @("--boat-counts", "4", "--pv-kwp", $j[1], "--bess-kwh", $j[2], "--bess-kw", $j[3], "--grid-limit-kw", $j[4], "--seed", "1", "--tariff-json", $mt)
    if ($j[5] -eq 1) { $runArgs += @("--skip-scheduled", "--plain-der") }
    Write-Host ((Get-Date).ToString("HH:mm") + "  job " + ($i + 1) + " of " + $jobs.Count + "  " + $tag)
    python garmin_scaling_experiment.py @runArgs --export-price $ExportPrice --out-csv $csv 2>&1 | Tee-Object (Join-Path $out ("log_" + $tag + ".txt")) | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Warning "$tag failed, see results\sweep_mv\log_$tag.txt" }
}
Set-Location $repo
Write-Host "Window $Window finished."