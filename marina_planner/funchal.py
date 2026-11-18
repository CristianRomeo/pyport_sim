"""Funchal case study: usage pattern of the boats and the simulation engine that uses it.

PyPort Sim assigns the daily trips with a weekday rule (two trips Monday to Friday, one on
Saturday, none on Sunday). The use of recreational boats in Madeira depends instead on the
season and on public holidays, so this module replaces the rule through the two extension
points of PyPort Sim: TripManager._num_trips_for_date and SimulationEngine.trip_manager_class.
"""
from datetime import date, datetime

import holidays

import _pyport  # noqa: F401
from simulation import SimulationEngine
from simulation.trip_manager import TripManager

# Departure times (hour UTC, slot) of the three daily trips of the case study.
FUNCHAL_TRIP_SCHEDULE = ((9, 0), (13, 1), (17, 2))


class FunchalTripManager(TripManager):
    """Trips per day from the season and from Portuguese and Madeira public holidays.

    HIGH_SEASON_MONTHS, TRIPS_HIGH_SEASON and TRIPS_LOW_SEASON are provisional, based on an
    informal check with a Funchal boat rental company (about 3 trips a day in the high season,
    probably 2 in winter, not confirmed). Replace them with operator data when available.
    """

    HIGH_SEASON_MONTHS = frozenset({5, 6, 7, 8, 9, 10})  # May-October
    TRIPS_HIGH_SEASON = 3
    TRIPS_LOW_SEASON = 2

    def __init__(self, trips_directory: str = "assets/trips"):
        super().__init__(trips_directory)
        # Portugal national holidays + Madeira regional holidays (subdivision "30"),
        # e.g. "Dia da Regiao Autonoma da Madeira" (1 July).
        self._holidays = holidays.Portugal(subdiv="30")
        # "Dia da Autonomia" (2 April), Madeira regional holiday instituted by unanimous vote of
        # the Madeira Legislative Assembly on 27 November 2024 (observador.pt, 27/11/2024); it is
        # not in the data of the holidays library as of v0.106, so it is added here.
        for year in range(2025, 2036):
            self._holidays[date(year, 4, 2)] = "Dia da Autonomia"

    def _num_trips_for_date(self, current_date: datetime) -> int:
        """TRIPS_HIGH_SEASON in a high-season month or on a public holiday, else TRIPS_LOW_SEASON."""
        day = current_date.date()
        if day.month in self.HIGH_SEASON_MONTHS or day in self._holidays:
            return self.TRIPS_HIGH_SEASON
        return self.TRIPS_LOW_SEASON


class FunchalEngine(SimulationEngine):
    """SimulationEngine with the Funchal usage pattern. Use FUNCHAL_TRIP_SCHEDULE in Settings."""

    trip_manager_class = FunchalTripManager
