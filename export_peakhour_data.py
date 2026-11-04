"""Writes dashboard/peakhour.js from the peak-hour runs (run from the repo root):

    python export_peakhour_data.py

Reads results/peakhour/opt_*.csv (charging on arrival, smart charging, plant with the optimiser)
and results/peakhour/plain_*.csv (plant without smart charging).
"""
import csv, glob, io, json, os, re

def row(path):
    with io.open(path, encoding="utf8", newline="") as f:
        return next(csv.DictReader(f))

out = []
for p in sorted(glob.glob(os.path.join("results", "peakhour", "opt_*.csv"))):
    if p.endswith("_seasons.csv"):
        continue   # per-season companion file written by the experiment
    m = re.search(r"opt_pv(\d+)_b(\d+)_p(\d+)_n(\d+)(?:_cap(\d+))?", os.path.basename(p))
    pv, b, bkw, n = map(int, m.groups()[:4])
    cap = int(m.group(5)) if m.group(5) else n * 50   # no _cap in the name: no grid limit (boats x 50 kW)
    o = row(p)
    pl = os.path.join("results", "peakhour", os.path.basename(p).replace("opt_", "plain_"))
    q = row(pl) if os.path.exists(pl) else None
    out.append({"boats": n, "cap": cap, "pv": pv, "b": b, "bkw": bkw,
                "pkb": float(o["baseline_peakhour_kw"]), "pks": float(o["scheduled_peakhour_kw"]),
                "pkd": float(o["der_peakhour_kw"]),
                "pkp": float(q["der_peakhour_kw"]) if q else float(o["baseline_peakhour_kw"])})
os.makedirs("dashboard", exist_ok=True)
with io.open(os.path.join("dashboard", "peakhour.js"), "w", encoding="utf8") as f:
    f.write("window.PEAKHOUR_DATA = " + json.dumps(out, separators=(",", ":")) + ";\n")
print(len(out), "plants written to dashboard/peakhour.js")
