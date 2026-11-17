"""Builds the EEM 2026 tariff files for the four simulated weeks (run from the repo root):

    python make_eem_tariffs.py

Writes assets/tariff/eem_<level>_<season>.json for level mt (medium voltage) and bte, season winter,
spring, summer, autumn. Same format as default_tariff.json (15-minute prices, one entry per weekday,
the same every day because the EEM daily cycle is the same all week).

Source (data inventory, rows GRD-02): EEM 'Tarifas de Venda a Clientes Finais na RAM em 2026' and 'Ciclo
Horario RAM' (ERSE Directive 10/2025). Energy prices in EUR/kWh, per period and hour band, in the order
peak / full / normal off-peak / super off-peak.
  Period I and IV  = quarters 1 and 4 (1 Jan-31 Mar, 1 Oct-31 Dec)
  Period II and III = quarters 2 and 3 (1 Apr-30 Sep)
Hour bands (daily cycle, all voltage levels):
  winter time:  peak 10:30-12:00 and 18:30-21:00; full 09:00-10:30, 12:00-18:30, 21:00-23:00
  summer time:  peak 10:30-13:00 and 20:30-22:00; full 09:00-10:30, 13:00-20:30, 22:00-23:00
  both:         normal off-peak 06:00-09:00 and 23:00-02:00; super off-peak 02:00-06:00
The simulated weeks: winter = Jan 2025 (winter time, period I), spring = Apr 2025 (summer time, period II),
summer = Jul 2025 (summer time, period III), autumn = 13 Oct 2025 (summer time, still on until 26 Oct,
period IV).
Only the energy price is here. The contracted-power and peak-power terms and the fixed daily term are not
part of the simulated cost (they do not depend on the schedule in this model)."""
import json
from pathlib import Path

PRICES = {   # level -> period group -> (peak, full, normal, super)
    "mt":  {"I_IV": (0.1226, 0.1139, 0.0952, 0.0866), "II_III": (0.1119, 0.1079, 0.0947, 0.0910)},
    "bte": {"I_IV": (0.1530, 0.1408, 0.1170, 0.1029), "II_III": (0.1420, 0.1346, 0.1161, 0.1075)},
}
SEASON = {"winter": ("I_IV", False), "spring": ("II_III", True), "summer": ("II_III", True), "autumn": ("I_IV", True)}
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def band(minute, summer_time):
    """0 peak, 1 full, 2 normal off-peak, 3 super off-peak for a minute of the day."""
    h = minute / 60.0
    if 2 <= h < 6:
        return 3
    if 6 <= h < 9 or h >= 23 or h < 2:
        return 2
    peak = (10.5 <= h < 13 or 20.5 <= h < 22) if summer_time else (10.5 <= h < 12 or 18.5 <= h < 21)
    return 0 if peak else 1


def build(level, season):
    group, summer_time = SEASON[season]
    p = PRICES[level][group]
    pricing = {}
    for slot in range(96):
        m = slot * 15
        pricing[f"{m // 60:02d}:{m % 60:02d}"] = p[band(m, summer_time)]
    return {
        "name": f"EEM 2026 {level.upper()} - {season}",
        "description": f"EEM 2026 four-period tariff, {level.upper()}, {season} week "
                       f"({'summer' if summer_time else 'winter'} time, periods {group.replace('_', ' and ')}). Energy term only.",
        "currency": "EUR",
        "unit": "kWh",
        "tariff": {str(d): {"day_name": DAYS[d], "pricing": dict(pricing)} for d in range(7)},
    }


for level in PRICES:
    for season in SEASON:
        out = Path("assets/tariff") / f"eem_{level}_{season}.json"
        d = build(level, season)
        json.dump(d, open(out, "w", encoding="utf-8"), indent=2)
        vals = sorted({v for v in d["tariff"]["0"]["pricing"].values()})
        print(out, vals)
