"""Writes dashboard/peakhour.js from the medium-voltage runs (run from the repo root):

    python export_peakhour_data.py

For every plant, boats and grid limit of results/eem_mv and results/sweep_mv it stores the average grid power in the
peak hours (pkb, pks, pkd: charging on arrival, smart charging, plant with the optimiser) and the peak power of the
15-minute averages, on which the contracted power is billed (kb, ks, kd). pkp and kp are the same two numbers for the
plant without smart charging, read from the plain_*.csv files of results/peakhour_mv and results/sweep_mv
(they equal the values of charging on arrival where there is no such run). Seeds are averaged.
"""
import collections, csv, glob, io, json, os


def rows(path):
    with io.open(path, encoding="utf8", newline="") as f:
        return list(csv.DictReader(f))


def key(r):
    return (int(r["num_boats"]), round(float(r["contracted_power_kw"])), round(float(r["pv_kwp"] or 0)),
            round(float(r["bess_kwh"] or 0)), round(float(r["bess_kw"] or 0)))


def f(r, k):
    return float(r[k])


def mean(v):
    return sum(v) / len(v)


smart, plain = collections.defaultdict(list), collections.defaultdict(list)
for p in sorted(glob.glob("results/eem_mv/*.csv") + glob.glob("results/sweep_mv/sw_*.csv") + glob.glob("results/grid_mv/g_*.csv")):
    if not p.endswith("_seasons.csv"):
        for r in rows(p):
            smart[key(r)].append(r)
for p in sorted(glob.glob("results/peakhour_mv/plain_*.csv") + glob.glob("results/sweep_mv/plain_*.csv")):
    if not p.endswith("_seasons.csv"):
        for r in rows(p):
            plain[key(r)].append(r)

out = []
for k in sorted(smart):
    rs, q = smart[k], plain.get(k)
    boats, cap, pv, b, bkw = k
    e = {"boats": boats, "cap": cap, "pv": pv, "b": b, "bkw": bkw,
         "pkb": round(mean([f(r, "baseline_peakhour_kw") for r in rs]), 1),
         "pks": round(mean([f(r, "scheduled_peakhour_kw") for r in rs]), 1),
         "pkd": round(mean([f(r, "der_peakhour_kw") for r in rs]), 1),
         "kb": round(mean([f(r, "baseline_peak_kw") for r in rs]), 1),
         "ks": round(mean([f(r, "scheduled_peak_kw") for r in rs]), 1),
         "kd": round(mean([f(r, "der_peak_kw") for r in rs]), 1)}
    e["pkp"] = round(mean([f(r, "der_peakhour_kw") for r in q]), 1) if q else e["pkb"]
    e["kp"] = round(mean([f(r, "der_peak_kw") for r in q]), 1) if q else e["kb"]
    out.append(e)
os.makedirs("dashboard", exist_ok=True)
with io.open(os.path.join("dashboard", "peakhour.js"), "w", encoding="utf8") as fh:
    fh.write("window.PEAKHOUR_DATA = " + json.dumps(out, separators=(",", ":")) + ";\n")
print(len(out), "plants written to dashboard/peakhour.js")