"""Builds three alternative tariff files from assets/tariff/default_tariff.json, same format and
same time bands, only the price spread changes (price' = 0.20 + k * (price - 0.20)):
  assets/tariff/tariff_flat.json    k = 0    (0.20 EUR/kWh all day: no arbitrage)
  assets/tariff/tariff_narrow.json  k = 0.3  (0.176 / 0.20 / 0.23)
  assets/tariff/tariff_wide.json    k = 2    (0.05 / 0.20 / 0.35)
Run from the repo root:  python make_tariffs.py"""
import json
from pathlib import Path
src = json.load(open("assets/tariff/default_tariff.json", encoding="utf-8"))
for name, k in (("flat", 0.0), ("narrow", 0.3), ("wide", 1.5)):
    d = json.loads(json.dumps(src))
    d["name"] = f"Tariff sensitivity: {name}"
    d["description"] = f"Default bands with the spread around 0.20 EUR/kWh multiplied by {k}"
    for day in d["tariff"].values():
        for t, p in day["pricing"].items():
            day["pricing"][t] = round(0.20 + k * (p - 0.20), 4)
    out = Path("assets/tariff") / f"tariff_{name}.json"
    json.dump(d, open(out, "w", encoding="utf-8"), indent=2)
    vals = sorted({p for day in d["tariff"].values() for p in day["pricing"].values()})
    print(out, vals)
