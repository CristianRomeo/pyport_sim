"""
Ad-hoc analysis script (not part of the economics package's public API):
scan the number of boats/chargers served by a FIXED PV+BESS installation
and find the fleet size at which the investment's payback/NPV turns
favourable.

All technical parameters (PV, BESS, charger, vessel) are sourced from
data_variable_inventory.xlsx - see the comments next to each constant
below for the inventory ID and whether the value is a confirmed Funchal
figure or the PyPort reference default (used where Funchal-specific data
is still "To define"). Do not change these without updating the matching
inventory row/comment.

For each boat count N and each representative week (winter, spring,
summer, autumn by default, see SEASONS) this script runs THREE 7-day
simulations (the engine caps days at 7 regardless of what is passed):
  1. baseline  - N boats/chargers, NO PV, NO BESS
  2. scheduled - N boats/chargers, NO PV, NO BESS, but the MILP optimizer on
                 (smart charging in the cheap hours)
  3. der       - N boats/chargers, PV + BESS + MILP optimizer enabled

The investment (PV+BESS) is credited only with scheduled - der, because
smart charging alone costs nothing; baseline - scheduled is reported as the
value of scheduling (use --skip-scheduled for the old two-scenario run).

Each week stands for a quarter of the year. The yearly cost is the sum of
the weekly costs times the weeks they stand for; the battery life uses the
cycles of all the weeks. The summary CSV keeps one row per boat count (the
weekly columns hold the average week of the year, so the demo and the
sensitivity table work unchanged); the weeks one by one are written to
<out-csv>_seasons.csv. Use --seasons summer for a quick test, or
--seasons sep for the old single September week.

...then feeds the weekly cost difference into economics.payback to get
simple payback, discounted payback and NPV, using the SAME fixed CAPEX
(PV+BESS only - chargers are assumed already installed/sunk cost, so they
are not added to CAPEX here; see --include-charger-capex to add them).

Each scenario also reports a SERVICE LEVEL KPI: the fraction of trips
trip_manager assigned for the week that the boat actually completed
(returned to port), vs. skipped by the optimizer as infeasible or
cancelled in real time after 6 PM. This matters because a scenario can
show a very low weekly grid cost simply by not actually serving most of
the fleet's trips (undersized charger/PV/BESS relative to demand) - that
is a capacity shortfall, not a real saving, and cost figures should never
be read without checking the service level alongside them.

CONTRACTED POWER NOTE: the grid-import limit (contracted_power) is not a
sourced Funchal value (inventory GRD-01: still to be requested from the
marina/EEM). With a fixed 80 kW cap the grid, not the optimizer, made most
trips infeasible as the fleet grew (baseline service level fell to ~77 %
at 4 boats), which distorted the savings and the NPV. Following the
supervisor's decision of 26 Oct 2026, contracted_power now scales with the
fleet: P_cont = num_boats x CHARGER_KW (all chargers can run at once).

Holding that default fixed while scaling the fleet from 2 to 10 boats
means the grid-import cap, not the MILP solver, is what makes most trips
infeasible at scale: each route_8 trip needs ~91 kWh/boat, so serving
trip 1 for N boats before the ~8h45 morning deadline requires roughly
(N * 91 kWh) / 8.75 h of average grid power - already ~104 kW for N=10,
above the 80 kW cap, before trip 2 or 3 are even considered. The optimizer
correctly reports this as infeasible (SKIPPED) rather than finding a
"better" schedule, because there isn't one while the cap stays fixed -
no amount of extra solver time or a looser mip_gap changes that.

For this reason contracted_power is FIXED at 80 kW for every fleet size
(CONTRACTED_POWER_KW below). It is a hard constraint set by the supervisor
("for now"): the fleet can grow, the grid connection cannot. It is
deliberately not a CLI parameter and is never scaled with num_boats, so
results at every fleet size are directly comparable.

PRICE ABOVE A POWER THRESHOLD: --excess-threshold-kw (default 80) and
--excess-factor (default 1 = off) price the grid import above that power at
factor x the tariff. The surcharge is applied after the simulation, so the
optimizer does not try to avoid it: the optimized scenarios are then a
conservative estimate. The summary CSV also stores, per scenario, the cost
(at the normal tariff) and the energy above the threshold, so any other
factor can be applied afterwards without simulating again.

POWER CHARGE ON THE PEAK (alternative to the price above): the CSV also stores
the highest weekly grid peak of each scenario and the "kW-months above the
threshold" per year (peak above --excess-threshold-kw, times the 3 billing
months each season stands for). A charge of R EUR/kW-month on the excess peak
costs R x kW-months per year; summarize_runs.py --peak-rate R applies it. Only
one week per season is simulated, so the monthly peak is approximated by that
week's peak (the real monthly peak can only be higher).

This does NOT touch your existing scenario_*.db files - every run writes
to its own new db named scenario_scaling_{baseline|der}_{N}boats.db, so
nothing you've already produced is at risk. Each run calls Open-Meteo for
weather, so expect this to take a while per boat count (two full sim runs
each).

Usage (defaults to testing 2,3,4,5,6,8,10 boats):
    python boats_scaling_experiment.py
    python boats_scaling_experiment.py --boat-counts 2 4 6 8 10 12
    python boats_scaling_experiment.py --include-charger-capex

Requires economics.payback / economics.capex_opex (already in your repo).
"""

import argparse
import contextlib
import csv
import io
import os
import random
import re
import sys
from pathlib import Path

from models import Port, Boat, Charger, PV, BESS, BESSControlStrategy
from config import Settings, SimulationMode
from database import DatabaseManager
from simulation import SimulationEngine
from economics.run_economics import grid_cost_split, grid_peak_kw, grid_export_kwh, grid_peak_hour_kw

PEAKHOUR = {}   # average import power in the peak hours of the last run of each scenario tag, kW
SUMMER_TIME = {"winter": False}   # every other simulated week is in summer time
from economics.capex_opex import CapexBreakdown, OpexBreakdown
from economics.payback import evaluate_investment, bess_replacement_schedule, bess_price_decline_for_case
from economics.degradation import bess_life_years_from_weeks

# All values below are taken from data_variable_inventory.xlsx (sheet
# "Variables"), preferring a confirmed Funchal value where one exists and
# falling back to the PyPort reference value (traceable to the original
# PyPort validation thesis, Garces 2026) where Funchal data is still
# "To define". Previous versions of this script used ad hoc/back-calculated
# numbers (e.g. a 4.6 kW "shore charger" inferred from one old simulation
# run) instead of sourced data - replaced here per inventory ID.

# PV-01: PyPort ref = 50 kWp DC; Funchal reference case ~100 kWp (SMA STP
# 50-41 inverter, 50 kW AC / 75 kW DC, typical oversizing 1.3-1.5x). Using
# the Funchal reference value.
PV_KW = 100.0

# BES-01/02/03: PyPort ref = 200 kWh capacity, 50 kW max charge/discharge.
# Funchal datasheet gives only per-module figures (8.28-22.08 kWh/module,
# scalable), no single system-level total yet - using PyPort ref.
BESS_KWH = 200.0
BESS_KW = 50.0
# BES-04: PyPort ref = 0.90; Funchal datasheet states round-trip efficiency
# >= 96%. Using the Funchal value (0.96) - note this model applies a single
# efficiency factor per charge/discharge event, so if that round-trip figure
# needs splitting into one-way charge/discharge efficiencies this should be
# revisited.
BESS_EFFICIENCY = 0.96

# EVS-01/02/03: PyPort ref = 22 kW AC, eta=0.95, 1:1 charger:boat ratio -
# this is also the exact charger spec used in PyPort's own Funchal pier
# validation scenario (Garces 2026, Sec. 3.3), so it is the most defensible
# "real" value available, not a placeholder. The actual EVSE product being
# quoted (Aqua superPower Aqua 75, EVS-01 notes) is rated even higher
# (75 kW) - 22 kW is already a conservative choice relative to that.
CHARGER_KW = 22.0
CHARGER_EFFICIENCY = 0.95

# VES-01/02/03/04/06: PyPort reference vessel. Funchal fleet data (VES-07)
# is real but highly heterogeneous (12 kW electric hybrid up to 375 kW
# diesel per engine, across 7 different operators) and no single
# representative electrifiable vessel has been confirmed yet for the case
# study (range_speed and a Funchal-specific battery_capacity are still
# "To define" in the inventory) - so the PyPort reference vessel is used
# as the most defensible single value, pending that data.
BOAT_SPEC = dict(motor_power=120, weight=2500, length=8.5,
                  battery_capacity=150, range_speed=15.0, soc=0.30)

# Boat types for mixed fleets (--fleet-mix). Electric equivalents assumed from the
# Funchal inventory (VES-07), not manufacturer data. charger_kw = charger per boat.
#   ref = PyPort reference vessel (the default when --fleet-mix is not used)
#   rib = small fast boat / RIB, few passengers
#   cat = tourist catamaran
#   lux = luxury catamaran
BOAT_TYPES = {
    "ref": (dict(BOAT_SPEC), None),
    "rib": (dict(motor_power=80, weight=1800, length=7.5, battery_capacity=100,
                 range_speed=15.0, soc=0.30), 22.0),
    "cat": (dict(motor_power=150, weight=9000, length=15.0, battery_capacity=250,
                 range_speed=15.0, soc=0.30), 50.0),
    "lux": (dict(motor_power=250, weight=14000, length=16.0, battery_capacity=350,
                 range_speed=15.0, soc=0.30), 100.0),
}
FLEET_TYPES = None        # list of type names, one per boat, set by --fleet-mix
FLEET_MIX_LABEL = ""

# GRD-01: grid-import limit, SCALED with the fleet (supervisor decision,
# 26 Oct 2026): every charger can run at full power at the same time, so
# the grid connection never limits the service level and the NPV is not
# distorted by trips lost to an undersized connection.
#   P_cont = number of boats x charger power
# CHARGER_KW is read at call time, so scripts that override it (e.g. the
# Garmin wrapper) are followed automatically.
# GRID_LIMIT_KW (set by --grid-limit-kw) is an EXPERIMENT override: when given,
# the same fixed grid limit is used for every fleet size, e.g. 80 kW to test a
# power cap. None (default) keeps the supervisor's rule above.
GRID_LIMIT_KW = None

# SEED (set by --seed): when given, the trip assignment is seeded from the seed,
# the season and the fleet size just before every scenario, so the baseline,
# the scheduled baseline and the DER scenario of one week get the SAME trips
# (a paired comparison: the savings no longer carry the noise of different route
# draws), and runs with the same seed but a different plant or grid limit are
# paired too. None (default) keeps the old behaviour: a fresh random draw for
# every scenario.
SEED = None
PLAIN_DER = False   # plant scenario with charging on arrival and rule-based battery (no optimiser)


def contracted_power_for(num_boats: int) -> float:
    if GRID_LIMIT_KW is not None:
        return GRID_LIMIT_KW
    if FLEET_TYPES:
        return sum((BOAT_TYPES[t][1] or CHARGER_KW) for t in FLEET_TYPES)
    return num_boats * CHARGER_KW

START_DATE = "2025-09-01"  # legacy single week ("sep")

# Representative weeks of the year: name -> (start date, weeks of the year it
# stands for). The four weeks start on a Monday and avoid public holidays
# (so the trip rule gives the normal 2 or 3 trips per day: 3 from May to
# October, else 2). Each stands for a quarter of the year: 365 / 7 / 4 weeks.
WEEKS_PER_QUARTER = 365.0 / 7.0 / 4.0
SEASONS = {
    "winter": ("2025-01-13", WEEKS_PER_QUARTER),   # 2 trips a day
    "spring": ("2025-04-07", WEEKS_PER_QUARTER),   # 2 trips a day
    "summer": ("2025-07-14", WEEKS_PER_QUARTER),   # 3 trips a day
    "autumn": ("2025-10-13", WEEKS_PER_QUARTER),   # 3 trips a day
    "sep":    (START_DATE, 365.0 / 7.0),           # the old single week
}
ALL_SEASONS = ["winter", "spring", "summer", "autumn"]

# Twelve monthly weeks (a Monday per month, no public holiday in the week).
# Each stands for 1/12 of the year; --seasons normalises the weights anyway.
MONTH_STARTS = ["2025-01-13", "2025-02-10", "2025-03-10", "2025-04-07",
                "2025-05-12", "2025-06-02", "2025-07-14", "2025-08-04",
                "2025-09-08", "2025-10-13", "2025-11-10", "2025-12-15"]
for _i, _d in enumerate(MONTH_STARTS, 1):
    SEASONS[f"m{_i:02d}"] = (_d, 365.0 / 7.0 / 12.0)
TARIFF_PATH = "assets/tariff/default_tariff.json"
EXPORT_PRICE = 0.0   # EUR per kWh paid for PV energy sent to the grid (--export-price)


def build_port(num_boats: int, with_der: bool, contracted_power: float, tariff_path: str = None) -> Port:
    port = Port(
        name="Funchal",
        contracted_power=contracted_power,
        lat=32.64542,
        lon=-16.90841,
        tariff_path=tariff_path or TARIFF_PATH,
    )
    port.export_price_eur_kwh = EXPORT_PRICE
    for i in range(1, num_boats + 1):
        kind = FLEET_TYPES[i - 1] if FLEET_TYPES else "ref"
        spec, charger_kw = BOAT_TYPES[kind]
        boat = Boat(name=f"SeaBreeze_{i}", **spec)
        charger = Charger(name=f"FastCharger_{i}", max_power=(charger_kw or CHARGER_KW),
                           efficiency=CHARGER_EFFICIENCY)
        port.add_boat(boat)
        port.add_charger(charger)

    if with_der and PV_KW > 0:
        pv_system = PV(
            # PV-02: PyPort ref tilt = 30 deg; Funchal real value ~32 deg
            # (roughly equal to latitude, standard optimal-tilt rule).
            name="Solar_Array_1", capacity=PV_KW, tilt=32.0, azimuth=180.0,
            latitude=port.lat, longitude=port.lon,
        )
        port.add_pv(pv_system)

    if with_der and BESS_KWH > 0:
        bess = BESS(
            # soc_min/max (0.10/0.90): PyPort ref, close to Funchal's
            # "typically 5-10% / 95-100%" (BES-05/06, no exact datasheet
            # value published). initial_soc=0.50: matches BES-07's
            # confirmed Funchal value exactly.
            name="Battery_Storage_1", capacity=BESS_KWH,
            max_charge_power=BESS_KW, max_discharge_power=BESS_KW,
            efficiency=BESS_EFFICIENCY, soc_min=0.10, soc_max=0.90,
            initial_soc=0.50,
            control_strategy=BESSControlStrategy.DEFAULT,
        )
        port.add_bess(bess)

    return port


class _Tee(io.TextIOBase):
    """Write to both the real stdout (so the console stays live) and a
    buffer we can parse afterwards for service-level stats."""

    def __init__(self, real_stdout, buffer):
        self._real = real_stdout
        self._buffer = buffer

    def write(self, s):
        self._real.write(s)
        self._buffer.write(s)
        return len(s)

    def flush(self):
        self._real.flush()


# Matches trip-assignment lines like "     SeaBreeze_3: 3 trip(s) - [...]"
_ASSIGNED_RE = re.compile(r": (\d+) trip\(s\) -")
# Matches the engine's real completion line, e.g.
# "  <- SeaBreeze_3 returned from route_8 at 12:45, SOC=51.7%"
_RETURNED_RE = re.compile(r"returned from \S+ at")


def db_path_for(tag: str, season: str, num_boats: int) -> str:
    return f"scenario_scaling_{tag}_{season}_{num_boats}boats.db"


def run_scenario(num_boats: int, with_der: bool, contracted_power: float,
                 start_date: str = None, season: str = "sep",
                 use_optimizer: bool = None, excess_threshold_kw: float = 80.0) -> tuple:
    """
    Run one 7-day scenario starting on start_date (default: START_DATE).
    Returns (weekly_cost_eur, service_level, assigned_trips, excess_eur, excess_kwh, peak_kw):
    the weekly cost at the normal tariff, and the cost (at the normal tariff)
    and energy of the grid import above excess_threshold_kw, so a surcharge on
    that energy can be applied afterwards without simulating again.

    service_level = fraction of ASSIGNED trips that the boat actually
    completed (returned to port), out of all trips trip_manager assigned
    for the week - i.e. it also counts a trip skipped by the optimizer as
    infeasible, or cancelled in real time after 6 PM, as NOT served. A low
    weekly grid cost achieved by silently dropping trips is not a real
    saving, so this KPI must always be read alongside the cost columns.
    """
    if use_optimizer is None:
        use_optimizer = with_der
    if with_der and PLAIN_DER:
        use_optimizer = False
    tag = ("derplain" if PLAIN_DER else "der") if with_der else ("scheduled" if use_optimizer else "baseline")
    db_path = db_path_for(tag, season, num_boats)

    tariff_now = TARIFF_PATH.replace("{season}", season)   # one file per simulated week if the path has {season}
    port = build_port(num_boats, with_der, contracted_power, tariff_now)

    settings = Settings(
        timestep=900,
        mode=SimulationMode.BATCH,
        db_path=db_path,
        use_optimizer=use_optimizer,
        power_limit_mode=True,
        bess_rule_based=bool(with_der and PLAIN_DER),
    )
    if os.path.exists(db_path):
        os.remove(db_path)
    db_manager = DatabaseManager(settings.db_path)
    db_manager.initialize_schema()
    db_manager.initialize_default_metrics()

    if SEED is not None:
        random.seed(f"{SEED}-{season}-{num_boats}")

    sim = SimulationEngine(
        port=port, settings=settings, db_manager=db_manager,
        start_date=start_date or START_DATE, days=14,  # capped to 7 by the engine
    )

    buffer = io.StringIO()
    with contextlib.redirect_stdout(_Tee(sys.stdout, buffer)):
        sim.run()
    log_text = buffer.getvalue()

    assigned_trips = sum(int(m.group(1)) for m in _ASSIGNED_RE.finditer(log_text))
    completed_trips = len(_RETURNED_RE.findall(log_text))
    service_level = (completed_trips / assigned_trips) if assigned_trips else float("nan")

    weekly_cost, excess_eur, excess_kwh = grid_cost_split(
        db_manager, port.name, tariff_now, excess_threshold_kw)
    export_kwh = grid_export_kwh(db_manager, port.name)
    if export_kwh > 0:
        print(f"  -> exported to the grid: {export_kwh:.1f} kWh, paid EUR {EXPORT_PRICE:.3f}/kWh")
    weekly_cost -= EXPORT_PRICE * export_kwh
    peak_kw = grid_peak_kw(db_manager, port.name, tariff_now)
    PEAKHOUR[tag] = grid_peak_hour_kw(db_manager, port.name, tariff_now, SUMMER_TIME.get(season, True))
    print(
        f"  -> {db_path}: contracted_power={contracted_power:.1f}kW, "
        f"weekly grid cost = EUR {weekly_cost:.2f}, "
        f"import above {excess_threshold_kw:.0f} kW = {excess_kwh:.1f} kWh, "
        f"peak = {peak_kw:.1f} kW, "
        f"service level = {completed_trips}/{assigned_trips} trips "
        f"({service_level:.1%})"
    )
    return weekly_cost, service_level, assigned_trips, excess_eur, excess_kwh, peak_kw


def main():
    global PLAIN_DER, EXPORT_PRICE, PV_KW, BESS_KWH, BESS_KW, GRID_LIMIT_KW, SEED, TARIFF_PATH, FLEET_TYPES, FLEET_MIX_LABEL
    parser = argparse.ArgumentParser(description="Boat-count scaling sensitivity for a fixed PV+BESS install")
    parser.add_argument("--boat-counts", type=int, nargs="+", default=[2, 3, 4, 5, 6, 8, 10],
                         help="Boat/charger counts to test (default: 2 3 4 5 6 8 10)")
    parser.add_argument("--include-charger-capex", action="store_true",
                         help="Also add N x EVSE charger CAPEX/OPEX (default: chargers treated as sunk cost)")
    parser.add_argument("--discount-rate", type=float, default=0.07)
    parser.add_argument("--horizon-years", type=int, default=20)
    parser.add_argument("--bess-life-years", type=float, default=None,
                         help="Fixed battery life in years (0 = no replacement). "
                              "Default: derived from the simulated battery cycling")
    parser.add_argument("--bess-calendar-life", type=float, default=15.0,
                         help="Upper limit on the derived battery life, from time ageing (default 15)")
    parser.add_argument("--bess-price-decline", type=float, default=0.0,
                         help="Yearly fall of the battery price used for the replacement (default 0)")
    parser.add_argument("--bess-decline-case", choices=["low", "mid", "high"], default=None,
                         help="Named battery price decline (NREL ATB): low 1.5%%, mid 3.5%%, high 5.5%% a year")
    parser.add_argument("--seasons", nargs="+", choices=sorted(SEASONS), default=ALL_SEASONS,
                         help="Representative weeks to simulate (default: winter spring summer autumn; "
                              "sep = the old single September week). Use one name for a quick test.")
    parser.add_argument("--skip-scheduled", action="store_true",
                         help="Skip the third scenario (baseline with optimizer, no PV/BESS). Then ALL the "
                              "saving is credited to PV+BESS, including what smart charging alone would give")
    parser.add_argument("--pv-kwp", type=float, default=PV_KW,
                         help="PV size in kWp (0 = no PV). Default 100")
    parser.add_argument("--bess-kwh", type=float, default=BESS_KWH,
                         help="Battery capacity in kWh (0 = no battery, no replacements). Default 200")
    parser.add_argument("--bess-kw", type=float, default=None,
                         help="Battery charge/discharge power in kW (default: 50, or capacity/4 if smaller)")
    parser.add_argument("--excess-threshold-kw", type=float, default=80.0,
                         help="Grid power above which energy costs more (default 80 kW)")
    parser.add_argument("--excess-factor", type=float, default=1.0,
                         help="Price multiplier for the grid import above the threshold "
                              "(default 1 = no surcharge; 2 = double). Applied after the simulation: "
                              "the optimizer is not aware of it, so with a surcharge the savings "
                              "of the optimized scenarios are conservative")
    parser.add_argument("--grid-limit-kw", type=float, default=None,
                         help="EXPERIMENT: fixed grid-import limit in kW for every fleet size "
                              "(default: boats x charger kW). A limit below the charging demand "
                              "makes the optimizer spread or skip charging, so check service level")
    parser.add_argument("--seed", type=int, default=None,
                         help="seed the trip assignment (per season and fleet size) so all scenarios of "
                              "a week get the same trips and a run can be repeated exactly. "
                              "Default: unseeded, a different draw every time")
    parser.add_argument("--tariff-json", default=None,
                         help="EXPERIMENT: tariff file to use instead of assets/tariff/default_tariff.json "
                              "(same format). Used for the tariff-shape sensitivity.")
    parser.add_argument("--export-price", type=float, default=0.0,
                         help="EUR per kWh paid for the PV energy sent to the grid (default 0: the surplus "
                              "is worth nothing). The optimizer and the cost both use it; keep it below the "
                              "cheapest import price (0.12 in the default tariff)")
    parser.add_argument("--fleet-mix", default=None,
                         help="EXPERIMENT: boat types, e.g. rib:2,cat:1,lux:1 (types ref, rib, cat, lux). "
                              "The number of boats is the sum; --boat-counts is overridden.")
    parser.add_argument("--plain-der", action="store_true",
                         help="EXPERIMENT: the plant runs with charging on arrival and a rule-based battery "
                              "(PV surplus, peak shaving, off-peak charging) instead of the optimiser. "
                              "Use with --skip-scheduled: the saving is then against charging on arrival.")
    parser.add_argument("--out-csv", default="boats_scaling_results.csv")
    args = parser.parse_args()
    if args.bess_decline_case:
        if args.bess_price_decline:
            parser.error("Use either --bess-price-decline or --bess-decline-case, not both.")
        args.bess_price_decline = bess_price_decline_for_case(args.bess_decline_case)

    if args.tariff_json:
        TARIFF_PATH = args.tariff_json
        print(f"Tariff file: {TARIFF_PATH}")
    GRID_LIMIT_KW = args.grid_limit_kw
    if not 0.0 <= args.export_price <= 0.10:
        parser.error("--export-price must be between 0 and 0.10 EUR/kWh")
    EXPORT_PRICE = args.export_price
    if EXPORT_PRICE:
        print(f"Export price: EUR {EXPORT_PRICE:.3f} per kWh")
    if args.fleet_mix:
        FLEET_TYPES = []
        for part in args.fleet_mix.split(","):
            name, count = part.split(":")
            if name not in BOAT_TYPES:
                parser.error(f"unknown boat type {name!r}; choose from {sorted(BOAT_TYPES)}")
            FLEET_TYPES += [name] * int(count)
        FLEET_MIX_LABEL = args.fleet_mix
        args.boat_counts = [len(FLEET_TYPES)]
        print(f"Fleet mix: {FLEET_MIX_LABEL} -> {len(FLEET_TYPES)} boats")
    SEED = args.seed
    PLAIN_DER = args.plain_der
    if PLAIN_DER:
        print("Plant scenario: charging on arrival + rule-based battery (no optimiser)")
    PV_KW = args.pv_kwp
    BESS_KWH = args.bess_kwh
    BESS_KW = args.bess_kw if args.bess_kw is not None else min(50.0, BESS_KWH / 4.0)
    print(f"Plant under test: PV {PV_KW:.0f} kWp, BESS {BESS_KWH:.0f} kWh / {BESS_KW:.0f} kW")

    rows = []
    season_rows = []
    year_weeks = 365.0 / 7.0
    # The chosen weeks always stand for a whole year: with all four seasons
    # each counts a quarter, with a single one (quick test) it counts it all.
    weight_scale = year_weeks / sum(SEASONS[name][1] for name in args.seasons)
    for n in args.boat_counts:
        contracted_power = contracted_power_for(n)
        print(f"\n=== {n} boats (contracted_power = {contracted_power:.1f} kW) ===")
        annual_baseline = annual_der = annual_sched = 0.0
        export_year = 0.0
        exc_eur = {"base": 0.0, "sched": 0.0, "der": 0.0}
        exc_kwh = {"base": 0.0, "sched": 0.0, "der": 0.0}
        peak_exc = {"base": 0.0, "sched": 0.0, "der": 0.0}   # kW-months/year above threshold
        peak_max = {"base": 0.0, "sched": 0.0, "der": 0.0}   # highest weekly peak, kW
        ph_sum = {"base": 0.0, "sched": 0.0, "der": 0.0}    # average peak-hour power x weeks
        completed_base = completed_der = completed_sched = assigned_total = 0.0
        der_weeks = []
        for season in args.seasons:
            start, weeks = SEASONS[season][0], SEASONS[season][1] * weight_scale
            print(f"--- {season}: week starting {start} (counts for {weeks:.1f} weeks of the year) ---")
            print("Running baseline (no PV/BESS)...")
            thr, fac = args.excess_threshold_kw, args.excess_factor
            base_cost, base_sl, assigned, base_xe, base_xk, base_pk = run_scenario(
                n, False, contracted_power, start, season, excess_threshold_kw=thr)
            base_cost += (fac - 1.0) * base_xe
            sched_cost, sched_sl, sched_xe, sched_xk, sched_pk = float("nan"), float("nan"), 0.0, 0.0, 0.0
            if not args.skip_scheduled:
                print("Running scheduled baseline (optimizer, no PV/BESS)...")
                sched_cost, sched_sl, _, sched_xe, sched_xk, sched_pk = run_scenario(
                    n, False, contracted_power, start, season, use_optimizer=True,
                    excess_threshold_kw=thr)
                sched_cost += (fac - 1.0) * sched_xe
            print("Running DER scenario (PV+BESS+optimizer)...")
            der_cost, der_sl, assigned_der, der_xe, der_xk, der_pk = run_scenario(
                n, True, contracted_power, start, season, excess_threshold_kw=thr)
            der_cost += (fac - 1.0) * der_xe

            # Power-charge basis: kW of weekly peak above the threshold, times the
            # billing months the season stands for (a 13-week season = 3 months).
            months = weeks * 12.0 / year_weeks
            for key, tg in (("base", "baseline"), ("sched", "scheduled"), ("der", "derplain" if PLAIN_DER else "der")):
                ph_sum[key] += PEAKHOUR.get(tg, 0.0) * weeks
            for key, pk in (("base", base_pk), ("sched", sched_pk), ("der", der_pk)):
                peak_exc[key] += max(0.0, pk - args.excess_threshold_kw) * months
                peak_max[key] = max(peak_max[key], pk)
            for key, xe, xk in (("base", base_xe, base_xk), ("sched", sched_xe, sched_xk), ("der", der_xe, der_xk)):
                exc_eur[key] += xe * weeks
                exc_kwh[key] += xk * weeks
            annual_baseline += base_cost * weeks
            annual_der += der_cost * weeks
            der_export = grid_export_kwh(DatabaseManager(db_path_for("derplain" if PLAIN_DER else "der", season, n)), "Funchal")
            export_year += der_export * weeks
            if not args.skip_scheduled:
                annual_sched += sched_cost * weeks
                completed_sched += sched_sl * assigned * weeks
            assigned_total += assigned * weeks
            completed_base += base_sl * assigned * weeks
            completed_der += der_sl * assigned_der * weeks
            der_weeks.append((DatabaseManager(db_path_for("derplain" if PLAIN_DER else "der", season, n)), weeks))
            season_rows.append({
                "num_boats": n, "season": season, "start_date": start, "weeks": round(weeks, 2),
                "assigned_trips": assigned,
                "baseline_weekly_eur": round(base_cost, 2), "baseline_service_level": round(base_sl, 3),
                "der_weekly_eur": round(der_cost, 2), "der_service_level": round(der_sl, 3),
                "baseline_excess_kwh": round(base_xk, 1), "scheduled_excess_kwh": round(sched_xk, 1),
                "der_excess_kwh": round(der_xk, 1),
                "der_export_kwh": round(der_export, 1),
                "baseline_peak_kw": round(base_pk, 1), "scheduled_peak_kw": round(sched_pk, 1),
                "der_peak_kw": round(der_pk, 1),
                "scheduled_weekly_eur": "" if args.skip_scheduled else round(sched_cost, 2),
                "scheduled_service_level": "" if args.skip_scheduled else round(sched_sl, 3),
                "weekly_savings_eur": round((base_cost if args.skip_scheduled else sched_cost) - der_cost, 2),
            })

        # Year totals, then the "average week" that reproduces them when the
        # rest of the pipeline multiplies a week by 365 / 7.
        baseline_weekly = annual_baseline / year_weeks
        der_weekly = annual_der / year_weeks
        baseline_service = completed_base / assigned_total if assigned_total else float("nan")
        der_service = completed_der / assigned_total if assigned_total else float("nan")
        assigned_week = assigned_total / year_weeks

        # The investment is credited only with what PV+BESS add on top of smart
        # charging: savings = scheduled baseline - DER (plain baseline if skipped).
        sched_weekly = annual_sched / year_weeks
        sched_service = completed_sched / assigned_total if assigned_total else float("nan")
        reference_weekly = baseline_weekly if args.skip_scheduled else sched_weekly
        weekly_savings = reference_weekly - der_weekly
        scheduling_savings = baseline_weekly - sched_weekly if not args.skip_scheduled else 0.0
        daily_savings = weekly_savings / 7.0

        evse_units = n if args.include_charger_capex else 0
        capex = CapexBreakdown(bess_kwh=BESS_KWH, bess_kw=BESS_KW if BESS_KWH > 0 else 0.0,
                               pv_wp=PV_KW * 1000, evse_units=evse_units)
        opex = OpexBreakdown(bess_capex=BESS_KWH * capex.bess_eur_per_kwh,
                              pv_wp=PV_KW * 1000, evse_units=evse_units)

        if BESS_KWH <= 0:
            bess_life = 0.0  # no battery: nothing to replace
        elif args.bess_life_years is None:
            bess_life = bess_life_years_from_weeks(
                der_weeks,
                "Funchal",  # PyPort logs bess_charge/discharge under the port name
                BESS_KWH,
                calendar_life_years=args.bess_calendar_life,
            )
            print(f"  Battery life derived from the simulated cycling: {bess_life:.1f} years")
        else:
            bess_life = args.bess_life_years
        replacements = bess_replacement_schedule(
            BESS_KWH * capex.bess_eur_per_kwh,
            bess_life,
            args.horizon_years,
            args.bess_price_decline,
        )
        replacements_extended = bess_replacement_schedule(
            BESS_KWH * capex.bess_eur_per_kwh,
            bess_life,
            args.horizon_years + 10,
            args.bess_price_decline,
        )
        result = evaluate_investment(
            capex_eur=capex.total(),
            daily_savings_eur=daily_savings,
            annual_opex_eur=opex.total(),
            discount_rate=args.discount_rate,
            horizon_years=args.horizon_years,
            bess_replacements=replacements,
            bess_replacements_extended=replacements_extended,
        )

        rows.append({
            "num_boats": n,
            "fleet_mix": FLEET_MIX_LABEL,
            "pv_kwp": PV_KW,
            "bess_kwh": BESS_KWH,
            "bess_kw": BESS_KW if BESS_KWH > 0 else 0.0,
            "contracted_power_kw": round(contracted_power, 1),
            "seed": "" if args.seed is None else args.seed,
            "excess_threshold_kw": args.excess_threshold_kw,
            "excess_factor": args.excess_factor,
            "baseline_excess_eur_week": round(exc_eur["base"] / year_weeks, 2),
            "scheduled_excess_eur_week": "" if args.skip_scheduled else round(exc_eur["sched"] / year_weeks, 2),
            "der_excess_eur_week": round(exc_eur["der"] / year_weeks, 2),
            "baseline_excess_kwh_week": round(exc_kwh["base"] / year_weeks, 1),
            "scheduled_excess_kwh_week": "" if args.skip_scheduled else round(exc_kwh["sched"] / year_weeks, 1),
            "der_excess_kwh_week": round(exc_kwh["der"] / year_weeks, 1),
            "export_price_eur_kwh": args.export_price,
            "tariff": os.path.basename(TARIFF_PATH).replace("_{season}", "").replace(".json", ""),
            "der_export_kwh_week": round(export_year / year_weeks, 1),
            "baseline_peak_kw": round(peak_max["base"], 1),
            "scheduled_peak_kw": "" if args.skip_scheduled else round(peak_max["sched"], 1),
            "der_peak_kw": round(peak_max["der"], 1),
            "baseline_peakhour_kw": round(ph_sum["base"] / year_weeks, 1),
            "scheduled_peakhour_kw": "" if args.skip_scheduled else round(ph_sum["sched"] / year_weeks, 1),
            "der_peakhour_kw": round(ph_sum["der"] / year_weeks, 1),
            "baseline_peak_excess_kwmonths": round(peak_exc["base"], 2),
            "scheduled_peak_excess_kwmonths": "" if args.skip_scheduled else round(peak_exc["sched"], 2),
            "der_peak_excess_kwmonths": round(peak_exc["der"], 2),
            "seasons": "+".join(args.seasons),
            "assigned_trips_week": round(assigned_week, 2),
            "baseline_weekly_eur": round(baseline_weekly, 2),
            "baseline_service_level": round(baseline_service, 3),
            "scheduled_weekly_eur": "" if args.skip_scheduled else round(sched_weekly, 2),
            "scheduled_service_level": "" if args.skip_scheduled else round(sched_service, 3),
            "scheduling_savings_eur_week": round(scheduling_savings, 2),
            "der_weekly_eur": round(der_weekly, 2),
            "der_service_level": round(der_service, 3),
            "weekly_savings_eur": round(weekly_savings, 2),
            "annual_savings_eur": round(result.annual_savings_eur, 2),
            "annual_net_cashflow_eur": round(result.annual_net_cashflow_eur, 2),
            "capex_eur": round(capex.total(), 2),
            "simple_payback_years": round(result.simple_payback_years, 2) if result.simple_payback_years != float("inf") else "inf",
            "discounted_payback_years": round(result.discounted_payback_years, 2) if result.discounted_payback_years != float("inf") else "inf",
            "npv_eur": round(result.npv_eur, 2),
            "bess_replacement_pv_eur": round(result.replacement_cost_pv_eur, 2),
            "bess_life_years": round(bess_life, 1),
        })

    print("\n" + "=" * 122)
    print(f"Weeks simulated: {', '.join(args.seasons)}. Weekly figures below are the average week of the year.")
    print(
        f"{'Boats':<7}{'P_cont':>8}{'Base/wk':>10}{'Sched/wk':>10}{'Base SL':>9}{'DER/wk':>10}{'DER SL':>9}"
        f"{'Savings/wk':>12}{'Simple PB':>12}{'Disc. PB':>12}{'NPV':>14}"
    )
    print("Sched/wk = baseline with the optimizer but no PV/BESS. Savings/wk = Sched/wk - DER/wk "
          "(what PV+BESS add on top of smart charging).")
    print("P_cont = grid-import limit, scaled with the fleet (boats x charger kW)."
          "SL = service level (% of assigned trips actually completed).")
    print("A low DER/wk with a low DER SL means trips were dropped, not saved.")
    print("-" * 122)
    for r in rows:
        print(
            f"{r['num_boats']:<7}{r['contracted_power_kw']:>8.1f}{r['baseline_weekly_eur']:>10.2f}"
            f"{(r['scheduled_weekly_eur'] if r['scheduled_weekly_eur'] != '' else float('nan')):>10.2f}"
            f"{r['baseline_service_level']:>9.1%}{r['der_weekly_eur']:>10.2f}"
            f"{r['der_service_level']:>9.1%}{r['weekly_savings_eur']:>12.2f}"
            f"{str(r['simple_payback_years']):>12}"
            f"{str(r['discounted_payback_years']):>12}{r['npv_eur']:>14.2f}"
        )

    with open(args.out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    seasons_csv = str(Path(args.out_csv).with_suffix("")) + "_seasons.csv"
    with open(seasons_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=season_rows[0].keys())
        writer.writeheader()
        writer.writerows(season_rows)
    print(f"\nSaved summary to {args.out_csv}")
    print(f"Saved the weeks one by one to {seasons_csv}")