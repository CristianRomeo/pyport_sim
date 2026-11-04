# Plant WITHOUT smart charging (charging on arrival + rule-based battery) against charging on arrival.
# EEM 2026 tariff in medium voltage, PV energy sent to the grid paid 0.05 EUR/kWh, trips from the Garmin routes.
# Before the first run, from the repo root:
#     python patch_plain.py
# Then, once per window, each in its own PowerShell (Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass):
#     .\run_plain_series.ps1 1
#     .\run_plain_series.ps1 2
# Window 1: seed 1 - four boats, two plants, five grid limits; battery 200 kWh / 100 kW with 5 and 6 boats at 80 and 120 kW
# Window 2: seed 2 - four boats, two plants, five grid limits
# Window 3: seed 1 - no grid limit (connection big enough for every trip), the seven other plants of the earlier tables
# Window 4: seed 2 - same as window 3
# Window 5: seed 1 - no grid limit, 2, 3, 5, 6, 8 and 10 boats, battery 200 kWh / 100 kW and PV 100 kWp + 200 kWh / 50 kW
# Each window works in its own copy of the repo (pyport_sim_p1, ...) so the database files do not collide.
# Results go to results\plain of the real repo. A run whose CSV exists is skipped, so the script can be restarted.
param([int]$Window = 1, [double]$ExportPrice = 0.05)

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$repo = (Get-Location).Path
if (-not (Select-String -Path (Join-Path $repo "boats_scaling_experiment.py") -Pattern "PLAIN_DER" -Quiet)) {
    Write-Error "boats_scaling_experiment.py has no --plain-der flag: run 'python patch_plain.py' first."
    exit 1
}
if (-not (Test-Path (Join-Path $repo "assets\tariff\eem_mt_winter.json"))) {
    Write-Error "assets\tariff\eem_mt_winter.json is missing: run 'python make_eem_tariffs.py' first."
    exit 1
}
$work = $repo + "_p" + $Window
$out = Join-Path $repo "results\plain"
New-Item -ItemType Directory -Force $out | Out-Null

if (Test-Path $work) { Remove-Item -Recurse -Force $work }
robocopy $repo $work /E /XD results old_results results_summary .git __pycache__ /XF *.db /NFL /NDL /NJH /NJS /NP | Out-Null
Set-Location $work

function Run([string]$tag, [string[]]$extra) {
    $csv = Join-Path $out ($tag + ".csv")
    if (Test-Path $csv) { Write-Host "skip $tag (already done)"; return }
    Write-Host ((Get-Date).ToString("HH:mm") + "  $tag")
    python garmin_scaling_experiment.py @extra --skip-scheduled --plain-der --export-price $ExportPrice --out-csv $csv 2>&1 | Tee-Object (Join-Path $out ("log_" + $tag + ".txt")) | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Warning "$tag failed, see results\plain\log_$tag.txt" }
}

$mt = "assets/tariff/eem_mt_{season}.json"
# (pv kWp, battery kWh, battery kW)
$plants = @(@(0, 200, 100), @(100, 200, 50))
# grid limit in kW; 0 = no limit
$caps = @(0, 150, 120, 100, 80)
# the other plants of the earlier tables (no grid limit)
$others = @(@(0, 100, 25), @(50, 0, 0), @(50, 100, 25), @(100, 0, 0), @(100, 100, 25), @(150, 0, 0), @(150, 100, 25))

function Plant([string]$boats, $p, [int]$cap, [int]$seed) {
    $tag = "plain_cap" + $cap + "_pv" + $p[0] + "_b" + $p[1] + "_p" + $p[2] + "_n" + $boats.Replace(" ", "") + "_s" + $seed
    $runArgs = @("--boat-counts") + $boats.Split(" ") + @("--pv-kwp", $p[0], "--bess-kwh", $p[1], "--seed", $seed, "--tariff-json", $mt)
    if ($p[1] -gt 0) { $runArgs += @("--bess-kw", $p[2]) }
    if ($cap -gt 0) { $runArgs += @("--grid-limit-kw", $cap) }
    Run $tag $runArgs
}

switch ($Window) {
    1 {
        foreach ($p in $plants) { foreach ($c in $caps) { Plant "4" $p $c 1 } }
        foreach ($c in 120, 80) { Plant "5 6" $plants[0] $c 1 }
    }
    2 {
        foreach ($p in $plants) { foreach ($c in $caps) { Plant "4" $p $c 2 } }
    }
    3 {
        foreach ($p in $others) { Plant "4" $p 0 1 }
    }
    4 {
        foreach ($p in $others) { Plant "4" $p 0 2 }
    }
    5 {
        foreach ($p in $plants) { Plant "2 3 5 6 8 10" $p 0 1 }
    }
}
Set-Location $repo
Write-Host "Window $Window finished."
