# Grid of cases for 2 to 10 boats, EEM 2026 medium-voltage tariff, PV energy sent to the grid paid 0.05 EUR/kWh, seed 1, Garmin routes.
# For each fleet size: solar 0 or 100 kWp, battery none / 200 kWh at 50 kW / 200 kWh at 100 kW (no plant without solar and battery),
# at three grid limits: the full connection (50 kW per boat), 60 pct and 40 pct of it. Cases already simulated are not repeated.
# From the repo root, once per window, each in its own PowerShell (three windows, about the same amount of work each):
#     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#     .\run_grid.ps1 1
#     .\run_grid.ps1 2
#     .\run_grid.ps1 3
# Each window works in its own copy of the repo (pyport_sim_g1, ...). Results go to results\grid_mv.
# The jobs are ordered by grid limit (full connection first), so an early stop still leaves complete rows.
# A run whose CSV exists is skipped, so the script can be restarted.
param([int]$Window = 1, [double]$ExportPrice = 0.05)

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$repo = (Get-Location).Path
if (-not (Test-Path (Join-Path $repo "assets\tariff\eem_mt_winter.json"))) {
    Write-Error "assets\tariff\eem_mt_winter.json is missing: run 'python make_eem_tariffs.py' first."
    exit 1
}
$work = $repo + "_g" + $Window
$out = Join-Path $repo "results\grid_mv"
New-Item -ItemType Directory -Force $out | Out-Null
if (Test-Path $work) { Remove-Item -Recurse -Force $work }
robocopy $repo $work /E /XD results old_results results_summary .git __pycache__ /XF *.db /NFL /NDL /NJH /NJS /NP | Out-Null
Set-Location $work

$mt = "assets/tariff/eem_mt_{season}.json"
# window, boats, solar kWp, battery kWh, battery kW, grid limit kW
$jobs = @(
    @(1, 2, 0, 200, 50, 100),
    @(2, 2, 0, 200, 100, 100),
    @(3, 2, 100, 0, 0, 100),
    @(1, 2, 100, 200, 100, 100),
    @(2, 3, 0, 200, 50, 150),
    @(3, 3, 0, 200, 100, 150),
    @(1, 3, 100, 0, 0, 150),
    @(2, 3, 100, 200, 100, 150),
    @(3, 4, 0, 200, 50, 200),
    @(1, 4, 100, 200, 100, 200),
    @(2, 5, 0, 200, 50, 250),
    @(3, 5, 0, 200, 100, 250),
    @(1, 5, 100, 0, 0, 250),
    @(2, 5, 100, 200, 100, 250),
    @(3, 6, 0, 200, 50, 300),
    @(1, 6, 0, 200, 100, 300),
    @(2, 6, 100, 0, 0, 300),
    @(3, 6, 100, 200, 100, 300),
    @(1, 7, 0, 200, 50, 350),
    @(2, 7, 0, 200, 100, 350),
    @(3, 7, 100, 0, 0, 350),
    @(1, 7, 100, 200, 50, 350),
    @(2, 7, 100, 200, 100, 350),
    @(3, 8, 0, 200, 50, 400),
    @(1, 8, 0, 200, 100, 400),
    @(2, 8, 100, 0, 0, 400),
    @(3, 8, 100, 200, 100, 400),
    @(1, 9, 0, 200, 50, 450),
    @(2, 9, 0, 200, 100, 450),
    @(3, 9, 100, 0, 0, 450),
    @(1, 9, 100, 200, 50, 450),
    @(2, 9, 100, 200, 100, 450),
    @(3, 10, 0, 200, 50, 500),
    @(1, 10, 0, 200, 100, 500),
    @(2, 10, 100, 0, 0, 500),
    @(3, 10, 100, 200, 100, 500),
    @(1, 2, 0, 200, 50, 60),
    @(1, 2, 0, 200, 100, 60),
    @(2, 2, 100, 0, 0, 60),
    @(1, 2, 100, 200, 50, 60),
    @(2, 2, 100, 200, 100, 60),
    @(1, 3, 0, 200, 50, 90),
    @(2, 3, 0, 200, 100, 90),
    @(1, 3, 100, 0, 0, 90),
    @(2, 3, 100, 200, 50, 90),
    @(1, 3, 100, 200, 100, 90),
    @(3, 4, 100, 0, 0, 120),
    @(2, 4, 100, 200, 100, 120),
    @(1, 5, 0, 200, 50, 150),
    @(3, 5, 0, 200, 100, 150),
    @(2, 5, 100, 0, 0, 150),
    @(1, 5, 100, 200, 50, 150),
    @(3, 5, 100, 200, 100, 150),
    @(2, 6, 0, 200, 50, 180),
    @(1, 6, 0, 200, 100, 180),
    @(3, 6, 100, 0, 0, 180),
    @(2, 6, 100, 200, 50, 180),
    @(1, 6, 100, 200, 100, 180),
    @(3, 7, 0, 200, 50, 210),
    @(2, 7, 0, 200, 100, 210),
    @(1, 7, 100, 0, 0, 210),
    @(3, 7, 100, 200, 50, 210),
    @(2, 7, 100, 200, 100, 210),
    @(1, 8, 0, 200, 50, 240),
    @(3, 8, 0, 200, 100, 240),
    @(2, 8, 100, 0, 0, 240),
    @(1, 8, 100, 200, 50, 240),
    @(3, 8, 100, 200, 100, 240),
    @(2, 9, 0, 200, 50, 270),
    @(1, 9, 0, 200, 100, 270),
    @(3, 9, 100, 0, 0, 270),
    @(2, 9, 100, 200, 50, 270),
    @(1, 9, 100, 200, 100, 270),
    @(3, 10, 0, 200, 50, 300),
    @(2, 10, 0, 200, 100, 300),
    @(1, 10, 100, 0, 0, 300),
    @(3, 10, 100, 200, 50, 300),
    @(2, 10, 100, 200, 100, 300),
    @(1, 2, 0, 200, 50, 40),
    @(1, 2, 0, 200, 100, 40),
    @(1, 2, 100, 0, 0, 40),
    @(1, 2, 100, 200, 50, 40),
    @(1, 2, 100, 200, 100, 40),
    @(3, 3, 0, 200, 50, 60),
    @(1, 3, 0, 200, 100, 60),
    @(3, 3, 100, 0, 0, 60),
    @(1, 3, 100, 200, 50, 60),
    @(2, 3, 100, 200, 100, 60),
    @(3, 4, 100, 0, 0, 80),
    @(1, 4, 100, 200, 100, 80),
    @(2, 5, 0, 200, 50, 100),
    @(3, 5, 0, 200, 100, 100),
    @(1, 5, 100, 0, 0, 100),
    @(2, 5, 100, 200, 50, 100),
    @(3, 5, 100, 200, 100, 100),
    @(1, 6, 100, 0, 0, 120),
    @(2, 6, 100, 200, 100, 120),
    @(3, 7, 0, 200, 50, 140),
    @(1, 7, 0, 200, 100, 140),
    @(2, 7, 100, 0, 0, 140),
    @(3, 7, 100, 200, 50, 140),
    @(1, 7, 100, 200, 100, 140),
    @(2, 8, 0, 200, 50, 160),
    @(3, 8, 0, 200, 100, 160),
    @(1, 8, 100, 0, 0, 160),
    @(2, 8, 100, 200, 50, 160),
    @(3, 8, 100, 200, 100, 160),
    @(1, 9, 0, 200, 50, 180),
    @(2, 9, 0, 200, 100, 180),
    @(3, 9, 100, 0, 0, 180),
    @(1, 9, 100, 200, 50, 180),
    @(2, 9, 100, 200, 100, 180),
    @(3, 10, 0, 200, 50, 200),
    @(1, 10, 0, 200, 100, 200),
    @(2, 10, 100, 0, 0, 200),
    @(3, 10, 100, 200, 50, 200),
    @(1, 10, 100, 200, 100, 200)
)

$mine = @($jobs | Where-Object { $_[0] -eq $Window })
$done = 0
for ($i = 0; $i -lt $jobs.Count; $i++) {
    $j = $jobs[$i]
    if ($j[0] -ne $Window) { continue }
    $tag = "g_n" + $j[1] + "_pv" + $j[2] + "_b" + $j[3] + "_p" + $j[4] + "_cap" + $j[5] + "_s1"
    $csv = Join-Path $out ($tag + ".csv")
    $done++
    if (Test-Path $csv) { Write-Host "skip $tag (already done)"; continue }
    $runArgs = @("--boat-counts", $j[1], "--pv-kwp", $j[2], "--bess-kwh", $j[3], "--grid-limit-kw", $j[5], "--seed", "1", "--tariff-json", $mt)
    if ($j[3] -gt 0) { $runArgs += @("--bess-kw", $j[4]) }
    Write-Host ((Get-Date).ToString("HH:mm") + "  job " + $done + " of " + $mine.Count + "  " + $tag)
    python garmin_scaling_experiment.py @runArgs --export-price $ExportPrice --out-csv $csv 2>&1 | Tee-Object (Join-Path $out ("log_" + $tag + ".txt")) | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Warning "$tag failed, see results\grid_mv\log_$tag.txt" }
}
Set-Location $repo
Write-Host "Window $Window finished."