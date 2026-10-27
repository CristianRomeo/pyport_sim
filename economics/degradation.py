from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence, Tuple


# Approximate Li-ion cycle-life curve: (equivalent_full_cycles, remaining_SOH)
# Placeholder — TODO: replace with cell-specific data once the BESS vendor/model is known
DEFAULT_CYCLE_LIFE_CURVE: Tuple[Tuple[float, float], ...] = (
    (0, 1.00),
    (500, 0.95),
    (1000, 0.90),
    (2000, 0.85),
    (3000, 0.80),
    (4000, 0.70),
)

DEFAULT_EOL_SOH_THRESHOLD = 0.80


@dataclass
class DegradationResult:
    total_charge_kwh: float
    total_discharge_kwh: float
    equivalent_full_cycles: float
    estimated_soh: float
    remaining_cycles_to_eol: float


def _integrate_power_kwh(rows: Sequence[Tuple[str, float]]) -> float:
    """Trapezoidal integration of power (kW) samples over time -> energy (kWh).

    rows: sequence of (iso_timestamp, power_kw), assumed already sorted by timestamp.
    """
    if len(rows) < 2:
        return 0.0

    total_kwh = 0.0
    prev_ts = datetime.fromisoformat(rows[0][0])
    prev_power = rows[0][1]

    for ts_str, power in rows[1:]:
        ts = datetime.fromisoformat(ts_str)
        dt_hours = (ts - prev_ts).total_seconds() / 3600.0
        avg_power = (prev_power + power) / 2.0
        total_kwh += avg_power * dt_hours
        prev_ts, prev_power = ts, power

    return total_kwh


def _soh_from_cycles(cycles: float, curve: Sequence[Tuple[float, float]]) -> float:
    """Linear interpolation of SOH from the cycle-life curve."""
    points = sorted(curve, key=lambda p: p[0])

    if cycles <= points[0][0]:
        return points[0][1]
    if cycles >= points[-1][0]:
        return points[-1][1]

    for (c0, soh0), (c1, soh1) in zip(points, points[1:]):
        if c0 <= cycles <= c1:
            frac = (cycles - c0) / (c1 - c0)
            return soh0 + frac * (soh1 - soh0)

    return points[-1][1]  # unreachable, defensive fallback


def _cycles_at_soh(target_soh: float, curve: Sequence[Tuple[float, float]]) -> float:
    """Inverse lookup: cycles at which SOH first drops to target_soh."""
    points = sorted(curve, key=lambda p: p[0])

    for (c0, soh0), (c1, soh1) in zip(points, points[1:]):
        if soh0 >= target_soh >= soh1:
            if soh0 == soh1:
                return c1
            frac = (soh0 - target_soh) / (soh0 - soh1)
            return c0 + frac * (c1 - c0)

    return points[-1][0]  # curve never reaches target -> last known point


def estimate_bess_degradation(
    db_manager,
    source_name: str,
    capacity_kwh: float,
    eol_soh_threshold: float = DEFAULT_EOL_SOH_THRESHOLD,
    cycle_life_curve: Optional[Sequence[Tuple[float, float]]] = None,
) -> DegradationResult:
    curve = cycle_life_curve or DEFAULT_CYCLE_LIFE_CURVE

    source_row = db_manager.get_source(source_name=source_name)
    if source_row is None:
        raise ValueError(f"No such BESS source logged: {source_name!r}")
    source_id = source_row["source_id"]

    charge_metric_id = db_manager.get_metric_id("bess_charge")
    discharge_metric_id = db_manager.get_metric_id("bess_discharge")

    charge_rows = db_manager.get_records("measurements", source_id=source_id, metric_id=charge_metric_id)
    discharge_rows = db_manager.get_records("measurements", source_id=source_id, metric_id=discharge_metric_id)

    charge_series = [(r["timestamp"], float(r["value"])) for r in charge_rows]
    discharge_series = [(r["timestamp"], float(r["value"])) for r in discharge_rows]

    total_charge_kwh = _integrate_power_kwh(charge_series)
    total_discharge_kwh = _integrate_power_kwh(discharge_series)

    equivalent_full_cycles = total_discharge_kwh / capacity_kwh if capacity_kwh > 0 else 0.0
    estimated_soh = _soh_from_cycles(equivalent_full_cycles, curve)
    cycles_at_eol = _cycles_at_soh(eol_soh_threshold, curve)
    remaining_cycles_to_eol = max(0.0, cycles_at_eol - equivalent_full_cycles)

    return DegradationResult(
        total_charge_kwh=total_charge_kwh,
        total_discharge_kwh=total_discharge_kwh,
        equivalent_full_cycles=equivalent_full_cycles,
        estimated_soh=estimated_soh,
        remaining_cycles_to_eol=remaining_cycles_to_eol,
    )


def bess_life_years_from_run(
    db_manager,
    source_name: str,
    capacity_kwh: float,
    days_simulated: int = 7,
    calendar_life_years: float = 15.0,
    eol_soh_threshold: float = DEFAULT_EOL_SOH_THRESHOLD,
    cycle_life_curve: Optional[Sequence[Tuple[float, float]]] = None,
) -> float:
    """
    Battery life (years) derived from the simulated cycling.

    The equivalent full cycles of the simulated period are scaled to a year
    (x 365 / days_simulated) and divided into the cycles the battery can do
    before reaching end of life (80% health by default). The result is capped
    by `calendar_life_years`, because a battery also ages with time even when
    it is hardly used.

    NOTE: PyPort logs bess_charge / bess_discharge under the PORT source
    (e.g. "Funchal"), not under the battery source, so pass the port name.

    Args:
        db_manager: DatabaseManager of a completed DER run.
        source_name: Source that carries bess_charge / bess_discharge.
        capacity_kwh: Nominal battery capacity (kWh).
        days_simulated: Length of the simulated period (days).
        calendar_life_years: Upper limit on the life, from time-ageing.

    Returns:
        Expected years until replacement.
    """
    result = estimate_bess_degradation(
        db_manager,
        source_name,
        capacity_kwh,
        eol_soh_threshold=eol_soh_threshold,
        cycle_life_curve=cycle_life_curve,
    )
    if result.equivalent_full_cycles <= 0 or days_simulated <= 0:
        return calendar_life_years
    cycles_per_year = result.equivalent_full_cycles * 365.0 / days_simulated
    cycles_to_eol = result.equivalent_full_cycles + result.remaining_cycles_to_eol
    return min(cycles_to_eol / cycles_per_year, calendar_life_years)


def bess_life_years_from_weeks(
    db_managers_and_weeks: Sequence[Tuple[object, float]],
    source_name: str,
    capacity_kwh: float,
    calendar_life_years: float = 15.0,
    eol_soh_threshold: float = DEFAULT_EOL_SOH_THRESHOLD,
    cycle_life_curve: Optional[Sequence[Tuple[float, float]]] = None,
) -> float:
    """
    Battery life (years) from several representative weeks (one per season).

    Each simulated week gives its equivalent full cycles. A week stands for
    `weeks` weeks of the year, so the yearly cycles are
    sum(cycles of the week x weeks it represents). The life is the cycles
    the battery can do before end of life divided by the yearly cycles,
    capped by `calendar_life_years`.

    Args:
        db_managers_and_weeks: [(DatabaseManager of a DER run, weeks of the
            year that run represents), ...].
        source_name: Source carrying bess_charge / bess_discharge (the port
            name, e.g. "Funchal").
        capacity_kwh: Nominal battery capacity (kWh).
    """
    cycles_per_year = 0.0
    cycles_to_eol = None
    for db_manager, weeks in db_managers_and_weeks:
        result = estimate_bess_degradation(
            db_manager,
            source_name,
            capacity_kwh,
            eol_soh_threshold=eol_soh_threshold,
            cycle_life_curve=cycle_life_curve,
        )
        cycles_per_year += result.equivalent_full_cycles * weeks
        cycles_to_eol = result.equivalent_full_cycles + result.remaining_cycles_to_eol
    if cycles_per_year <= 0 or cycles_to_eol is None:
        return calendar_life_years
    return min(cycles_to_eol / cycles_per_year, calendar_life_years)