# Simulations with the EEM 2026 tariff (medium voltage and BTE), PV energy sent to the grid paid 0.05 EUR/kWh.
# Before the first run, from the repo root:
#     python patch_eem.py
#     python make_eem_tariffs.py
# Then, once per window, each in its own PowerShell (Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass):
#     .\run_eem_series.ps1 1
#     .\run_eem_series.ps1 2
#     .\run_eem_series.ps1 3
# Window 1: medium voltage, four boats, no grid limit, six plants, seeds 1-2
# Window 2: medium voltage, grid limit 120 kW (three plants, seeds 1-2) and 100 kWp + 200 kWh with 2, 6, 10 boats
# Window 3: BTE, four boats, four plants, seed 1; medium voltage, the six plants of window 1, seed 3
# Each window works in its own copy of the repo (pyport_sim_e1, ...) so the database files do not collide.
# Results go to results\eem of the real repo. A run whose CSV exists is skipped, so the script can be restarted.
param([int]$Window = 1, [double]$ExportPrice = 0.05)

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$repo = (Get-Location).Path
if (-not (Test-Path (Join-Path $repo "assets\tariff\eem_mt_winter.json"))) {
    Write-Error "assets\tariff\eem_mt_winter.json is missing: run 'python patch_eem.py' and 'python make_eem_tariffs.py' first."
    exit 1
}
$work = $repo + "_e" + $Window
$out = Join-Path $repo "results\eem"
New-Item -ItemType Directory -Force $out | Out-Null

if (Test-Path $work) { Remove-Item -Recurse -Force $work }
robocopy $repo $work /E /XD results old_results results_summary .git __pycache__ /XF *.db /NFL /NDL /NJH /NJS /NP | Out-Null
Set-Location $work

function Run([string]$tag, [string[]]$extra) {
    $csv = Join-Path $out ($tag + ".csv")
    if (Test-Path $csv) { Write-Host "skip $tag (already done)"; return }
    Write-Host ((Get-Date).ToString("HH:mm") + "  $tag")
    python garmin_scaling_experiment.py @extra --export-price $ExportPrice --out-csv $csv 2>&1 | Tee-Object (Join-Path $out ("log_" + $tag + ".txt")) | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Warning "$tag failed, see results\eem\log_$tag.txt" }
}

$mt = "assets/tariff/eem_mt_{season}.json"
$bte = "assets/tariff/eem_bte_{season}.json"
# (pv kWp, battery kWh, battery kW)
$plants = @(@(0, 100, 25), @(0, 200, 100), @(50, 0, 0), @(100, 0, 0), @(100, 100, 25), @(100, 200, 50))

function Plant([string]$name, [string]$tariff, $p, [int]$seed, [string[]]$more) {
    $tag = $name + "_pv" + $p[0] + "_b" + $p[1] + "_p" + $p[2] + "_n4_s" + $seed
    $runArgs = @("--boat-counts", "4", "--pv-kwp", $p[0], "--bess-kwh", $p[1], "--seed", $seed, "--tariff-json", $tariff) + $more
    if ($p[1] -gt 0) { $runArgs += @("--bess-kw", $p[2]) }
    Run $tag $runArgs
}

switch ($Window) {
    1 {
        foreach ($seed in 1, 2) { foreach ($p in $plants) { Plant "mt" $mt $p $seed @() } }
    }
    2 {
        foreach ($seed in 1, 2) {
            foreach ($p in @(@(0, 100, 25), @(0, 200, 100), @(100, 200, 50))) {
                Plant "mtcap120" $mt $p $seed @("--grid-limit-kw", "120")
            }
        }
        Run "mt_pv100_b200_fleet_s1" @("--boat-counts", "2", "6", "10", "--pv-kwp", "100", "--bess-kwh", "200", "--seed", "1", "--tariff-json", $mt)
    }
    3 {
        foreach ($p in @(@(0, 100, 25), @(0, 200, 100), @(100, 0, 0), @(100, 200, 50))) { Plant "bte" $bte $p 1 @() }
        foreach ($p in $plants) { Plant "mt" $mt $p 3 @() }
    }
}
Set-Location $repo
Write-Host "Window $Window finished."
