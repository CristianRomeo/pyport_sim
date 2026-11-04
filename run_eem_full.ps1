# Completes the set of cases with the EEM 2026 medium-voltage tariff, so that every case of the dashboard
# has an EEM version (the cases of run_eem_series.ps1 are already done and are not repeated).
# From the repo root, once per window, each in its own PowerShell:
#     Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#     .\run_eem_full.ps1 1
#     .\run_eem_full.ps1 2
#     .\run_eem_full.ps1 3
# The jobs are shared between the three windows so that each has about the same amount of work. Each window works in its own copy of the
# repo (pyport_sim_f1, ...). Results go to results\eem. A run whose CSV exists is skipped, so the script can be
# restarted. Four-boat cases run with seeds 1 and 2, cases with other fleet sizes with seed 1.
param([int]$Window = 1, [double]$ExportPrice = 0.05)

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$repo = (Get-Location).Path
if (-not (Test-Path (Join-Path $repo "assets\tariff\eem_mt_winter.json"))) {
    Write-Error "assets\tariff\eem_mt_winter.json is missing: run 'python patch_eem.py' and 'python make_eem_tariffs.py' first."
    exit 1
}
$work = $repo + "_f" + $Window
$out = Join-Path $repo "results\eem"
New-Item -ItemType Directory -Force $out | Out-Null
if (Test-Path $work) { Remove-Item -Recurse -Force $work }
robocopy $repo $work /E /XD results old_results results_summary .git __pycache__ /XF *.db /NFL /NDL /NJH /NJS /NP | Out-Null
Set-Location $work

$mt = "assets/tariff/eem_mt_{season}.json"
# boats (space separated), solar kWp, battery kWh, battery kW, grid limit kW (0 = boats x 50 kW), seed
$jobs = @(
    @("2 3 5 6", 0, 200, 100, 120, 1), @("2 3 4 5 6", 0, 200, 100, 80, 1),
    @("4", 0, 100, 25, 80, 1), @("4", 0, 100, 25, 80, 2),
    @("4 5 6", 0, 200, 50, 120, 1), @("4", 0, 200, 50, 80, 1), @("4", 0, 200, 50, 80, 2), @("4", 0, 200, 50, 120, 2),
    @("4", 0, 300, 50, 120, 1), @("4", 0, 300, 50, 120, 2), @("4", 0, 300, 50, 80, 1), @("4", 0, 300, 50, 80, 2),
    @("5 6", 0, 300, 100, 120, 1), @("5 6", 0, 300, 100, 80, 1),
    @("5 6", 0, 400, 100, 120, 1), @("5 6", 0, 400, 100, 80, 1),
    @("4", 0, 200, 100, 150, 1), @("4", 0, 200, 100, 150, 2), @("4", 0, 200, 100, 100, 1), @("4", 0, 200, 100, 100, 2),
    @("4", 0, 200, 100, 80, 2),
    @("2 3 5 6", 100, 200, 50, 120, 1), @("2 3 4 5 6", 100, 200, 50, 80, 1),
    @("4", 100, 200, 50, 150, 1), @("4", 100, 200, 50, 150, 2), @("4", 100, 200, 50, 100, 1), @("4", 100, 200, 50, 100, 2),
    @("4", 100, 200, 50, 80, 2),
    @("4", 50, 100, 25, 0, 1), @("4", 50, 100, 25, 0, 2),
    @("4", 150, 0, 0, 0, 1), @("4", 150, 0, 0, 0, 2),
    @("4", 150, 100, 25, 0, 1), @("4", 150, 100, 25, 0, 2),
    @("3 5 8", 100, 200, 50, 0, 1)
)

# each job goes to the window with the least work so far (work = number of boat counts in the job)
$load = @(0, 0, 0)
for ($i = 0; $i -lt $jobs.Count; $i++) {
    $j = $jobs[$i]
    $w = 0
    if ($load[1] -lt $load[$w]) { $w = 1 }
    if ($load[2] -lt $load[$w]) { $w = 2 }
    $load[$w] += ($j[0] -split " ").Count
    if ($w -ne ($Window - 1)) { continue }
    $tag = "f_n" + ($j[0] -replace " ", "") + "_pv" + $j[1] + "_b" + $j[2] + "_p" + $j[3] + "_cap" + $j[4] + "_s" + $j[5]
    $csv = Join-Path $out ($tag + ".csv")
    if (Test-Path $csv) { Write-Host "skip $tag (already done)"; continue }
    $runArgs = @("--boat-counts") + ($j[0] -split " ") + @("--pv-kwp", $j[1], "--bess-kwh", $j[2], "--seed", $j[5], "--tariff-json", $mt)
    if ($j[2] -gt 0) { $runArgs += @("--bess-kw", $j[3]) }
    if ($j[4] -gt 0) { $runArgs += @("--grid-limit-kw", $j[4]) }
    Write-Host ((Get-Date).ToString("HH:mm") + "  job " + ($i + 1) + " of " + $jobs.Count + "  " + $tag)
    python garmin_scaling_experiment.py @runArgs --export-price $ExportPrice --out-csv $csv 2>&1 | Tee-Object (Join-Path $out ("log_" + $tag + ".txt")) | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Warning "$tag failed, see results\eem\log_$tag.txt" }
}
Set-Location $repo
Write-Host "Window $Window finished."
