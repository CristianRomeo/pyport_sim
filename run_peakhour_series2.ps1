# Average grid power in the peak hours for the 16 remaining plants of the reduced case list
# (other fleet sizes and grid limits). The nine four-boat plants without a limit are done by run_peakhour_series.ps1.
# EEM 2026 tariff in medium voltage, PV energy sent to the grid paid 0.05 EUR/kWh, seed 1, Garmin routes.
# From the repo root (patch_peakhour.py must already have been run), each in its own PowerShell
# (Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass):
#     .\run_peakhour_series2.ps1 1     # with the optimiser: charging on arrival, smart charging, plant
#     .\run_peakhour_series2.ps1 2     # without smart charging: plant + charging on arrival
# Each window works in its own copy of the repo (pyport_sim_k1, ...). Results go to results\peakhour.
# A run whose CSV exists is skipped, so the script can be restarted.
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
$pb = @(0, 200, 100)     # battery only: pv kWp, battery kWh, battery kW
$pp = @(100, 200, 50)    # 100 kWp + 200 kWh / 50 kW
# (boats, grid limit in kW, plant)
$cases = @(
    @(2, 80, $pb), @(2, 80, $pp), @(2, 120, $pp),
    @(3, 120, $pp), @(3, 80, $pb),
    @(4, 120, $pb), @(4, 120, $pp), @(4, 80, $pb), @(4, 80, $pp),
    @(5, 250, $pp), @(5, 120, $pp),
    @(6, 300, $pp), @(6, 120, $pp), @(6, 120, $pb),
    @(8, 400, $pp), @(10, 500, $pp)
)

foreach ($c in $cases) {
    $n = $c[0]; $cap = $c[1]; $p = $c[2]
    $tag = $(if ($Window -eq 1) { "opt" } else { "plain" }) + "_pv" + $p[0] + "_b" + $p[1] + "_p" + $p[2] + "_n" + $n + "_cap" + $cap + "_s1"
    $runArgs = @("--boat-counts", $n, "--pv-kwp", $p[0], "--bess-kwh", $p[1], "--bess-kw", $p[2], "--seed", "1", "--tariff-json", $mt)
    if ($cap -lt $n * 50) { $runArgs += @("--grid-limit-kw", $cap) }
    if ($Window -ne 1) { $runArgs += @("--skip-scheduled", "--plain-der") }
    Run $tag $runArgs
}
