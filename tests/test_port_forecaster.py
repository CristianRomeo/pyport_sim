from datetime import datetime
from types import SimpleNamespace as NS
from forecasting.port_forecaster import PortForecaster as PF


def _stub():
    s = NS(trip_schedule=((9, 0), (13, 1), (17, 2)))
    s._departure_times = lambda ts: PF._departure_times(s, ts)
    return s


def test_window_stays_open_after_last_trip_when_fewer_trips_than_slots():
    trips = [NS(duration=3 * 3600), NS(duration=3 * 3600)]
    for hour in (17, 20, 23):
        ts = datetime(2025, 1, 13, hour, 0)
        assert PF._in_charging_window(_stub(), ts, trips, None)