"""
Seasonal (EEM Period I-IV) tariff selection - built OUTSIDE Port/models/port.py.

Why this exists:
Port._load_tariff() / Port.get_tariff_price() only understand a FLAT
day-of-week + time-of-day JSON (assets/tariff/default_tariff.json). There is
no concept of EEM's four calendar-quarter tariff periods (Period I: Jan-Mar,
Period II: Apr-Jun, Period III: Jul-Sep, Period IV: Oct-Dec - source: ERSE
Regulamento 2/2025, Art. 41), each with its own peak/full/normal-off-peak/
super-off-peak EUR/kWh prices (GRD-01/02/03 in the inventory).

Rather than editing models/port.py to add season-awareness (which would
touch PyPort's own core), this module picks WHICH of four pre-generated,
already-flat tariff JSON files to pass as `Port(tariff_path=...)`, before
Port is even instantiated. Port itself never needs to know seasons exist.

Usage:
    from datetime import date
    from economics.tariff_seasonal import get_seasonal_tariff_path

    tariff_path = get_seasonal_tariff_path(date(2026, 7, 15), tariff_dir="economics/tariff_profiles")
    port = Port(name="Funchal", contracted_power=80, lat=32.64542, lon=-16.90841,
                tariff_path=tariff_path)
"""

from datetime import date
from pathlib import Path
from typing import Dict


# Calendar-quarter definition, resolved 24/09/2026 (Research Log, "Period
# I/II/III/IV definition"). Source: ERSE Regulamento 2/2025, Art. 36
# (mainland) / Art. 41 (Autonomous Regions).
EEM_PERIODS = {
    "I": (1, 3),    # 1 Jan - 31 Mar
    "II": (4, 6),   # 1 Apr - 30 Jun
    "III": (7, 9),  # 1 Jul - 30 Sep
    "IV": (10, 12), # 1 Oct - 31 Dec
}


def get_eem_period(d: date) -> str:
    """Return the EEM tariff period ('I'|'II'|'III'|'IV') for a given date, by calendar quarter."""
    for period, (start_month, end_month) in EEM_PERIODS.items():
        if start_month <= d.month <= end_month:
            return period
    raise ValueError(f"Could not resolve an EEM period for date {d!r}")


def get_seasonal_tariff_path(d: date, tariff_dir: str = "economics/tariff_profiles") -> str:
    """
    Return the path to the pre-generated tariff JSON matching d's EEM period.

    Expects files named tariff_period_I.json, tariff_period_II.json, etc.,
    in `tariff_dir` (see generate_tariff_json below to build them).

    Args:
        d: The simulation's start date (or any date within the scenario).
        tariff_dir: Directory containing the four period JSON files.

    Returns:
        Path string suitable for Port(tariff_path=...).
    """
    period = get_eem_period(d)
    path = Path(tariff_dir) / f"tariff_period_{period}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Expected seasonal tariff file not found: {path}. "
            "Run generate_tariff_json() for all four periods first."
        )
    return str(path)


def generate_tariff_json(
    period_prices: Dict[str, float],
    time_bands: Dict[str, list],
    out_path: str,
    currency: str = "EUR",
) -> None:
    """
    Build one PyPort-format flat tariff JSON (same schema as
    assets/tariff/default_tariff.json) for a single EEM period.

    Args:
        period_prices: {"peak": ..., "full": ..., "normal_off_peak": ...,
            "super_off_peak": ...} in EUR/kWh for this period (GRD-01/02/03).
            TODO: fill with the confirmed MT vs BTE figures once it's
            resolved which billing class applies to the marina (Research
            Log, "Still open: whether the marina is billed on MT or BTE").
            time_bands: {"peak": [("HH:MM","HH:MM"), ...], "full": [...],
            "normal_off_peak": [...], "super_off_peak": [...]} - the
            official EEM time bands. 
            TODO: these differ between "winter"
            and "summer" halves of the year per the official EEM cycle
            (Research Log, GRD-01/02/03) - the exact switch-over dates are
            not yet confirmed, so for now this generates ONE set of bands;
            call it twice (winter/summer) once those dates are confirmed,
            or extend this function to take two band sets.
            out_path: Where to write the JSON file (e.g.
            "economics/tariff_profiles/tariff_period_I.json").
            currency: Currency code, stored for documentation only (PyPort's
            Port.get_tariff_price does not read it).
    """
    import json

    def price_for(hhmm: str) -> float:
        for band_name, ranges in time_bands.items():
            for start, end in ranges:
                if start <= hhmm < end:
                    return period_prices[band_name]
        return period_prices.get("normal_off_peak", 0.0)

    day_names = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]
    tariff = {}
    for weekday in range(7):
        pricing = {}
        for hour in range(24):
            for minute in (0, 15, 30, 45):
                hhmm = f"{hour:02d}:{minute:02d}"
                pricing[hhmm] = round(price_for(hhmm), 4)
        tariff[str(weekday)] = {"day_name": day_names[weekday], "pricing": pricing}

    payload = {
        "name": "Economic layer - seasonal tariff",
        "description": "Generated by economics/tariff_seasonal.py from EEM Period prices/bands",
        "currency": currency,
        "unit": "kWh",
        "tariff": tariff,
    }

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
