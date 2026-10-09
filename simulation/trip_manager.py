"""Trip management for the simulation."""

import random
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

import holidays

from models.trip import Trip


class TripManager:
    """
    Manage trip loading and daily trip assignments for boats.

    Loads route CSV files once and then assigns trips per boat and day based on
    a recreational-marina usage pattern (season + public holidays), exposing
    helpers to query trips by slot or date.
    """

    # Recreational boat usage in Madeira does not follow a Monday-Friday
    # commercial pattern (the previous version of this file did: 2 trips on
    # weekdays, 1 on Saturday, 0 on Sunday). Instead it is driven mainly by
    # season and by public/regional holidays, which fall on any weekday.
    #
    # TODO: HIGH_SEASON_MONTHS, TRIPS_HIGH_SEASON and TRIPS_LOW_SEASON are
    # provisional, based on an informal check with a Funchal boat rental
    # company (~3 trips/day currently in high season; "probabilmente 2
    # in inverno, ma non sono sicuro" - Cristian, 09 Oct 2026). Replace with
    # real operator data once the pending marina email responses arrive.
    HIGH_SEASON_MONTHS = frozenset({5, 6, 7, 8, 9, 10})  # May-October
    TRIPS_HIGH_SEASON = 3
    TRIPS_LOW_SEASON = 2

    def __init__(self, trips_directory: str = "assets/trips"):
        """
        Initialize the trip manager and load available trips from disk.

        Args:
            trips_directory: Directory containing trip CSV files
        """
        self.trips_directory = Path(trips_directory)
        self.available_trips: List[Trip] = []
        self._load_trips()
        self.daily_assignments: Dict[str, Dict[str, List[Trip]]] = {}
        # Portugal national holidays + Madeira regional holidays (subdiv "30"),
        # e.g. "Dia da Regiao Autonoma da Madeira" (1 July).
        self._holidays = holidays.Portugal(subdiv="30")
        # "Dia da Autonomia" (2 April) - Madeira regional holiday instituted by
        # unanimous vote of the Madeira Legislative Assembly on 27 Nov 2024.
        # Verified against observador.pt (27/11/2024); not yet present in the
        # holidays library's data as of v0.106, so it is added here manually.
        for year in range(2025, 2036):
            self._holidays[date(year, 4, 2)] = "Dia da Autonomia"

    def _load_trips(self):
        """
        Load all available trip CSV files into `available_trips`.

        Expects files named `route_*.csv`; only trips with at least one valid
        point are kept. Logs basic information about loaded routes.
        """
        if not self.trips_directory.exists():
            print(f"Warning: Trips directory not found: {self.trips_directory}")
            return

        csv_files = list(self.trips_directory.glob("route_*.csv"))
        for csv_file in sorted(csv_files):
            try:
                trip = Trip(str(csv_file))
                if trip.points:
                    self.available_trips.append(trip)
                    print(
                        f"  Loaded {trip.route_name}: {len(trip.points)} points, "
                        f"{trip.duration/3600:.2f}h"
                    )
            except Exception as e:
                print(f"  Warning: Failed to load {csv_file}: {e}")

        if self.available_trips:
            print(f"  Total trips loaded: {len(self.available_trips)}")
        else:
            print("  Warning: No trips loaded!")

    def _num_trips_for_date(self, current_date: datetime) -> int:
        """
        Number of trips for a given calendar day: TRIPS_HIGH_SEASON if the
        date falls in a high-season month OR is a Portugal/Madeira public
        holiday, otherwise TRIPS_LOW_SEASON. Unlike the previous weekday-based
        rule, no day of the week is ever zeroed out.
        """
        date_only = current_date.date()
        is_high_season = date_only.month in self.HIGH_SEASON_MONTHS
        is_holiday = date_only in self._holidays
        if is_high_season or is_holiday:
            return self.TRIPS_HIGH_SEASON
        return self.TRIPS_LOW_SEASON

    def assign_daily_trips(self, boat_name: str, current_date: datetime) -> List[Trip]:
        """
        Assign trips for a boat for the given day if not already assigned.

        Args:
            boat_name: Name of the boat
            current_date: Current simulation date

        Returns:
            List of trips assigned for this day (may be empty).
        """
        if not self.available_trips:
            return []

        date_str = current_date.strftime("%Y-%m-%d")

        if boat_name in self.daily_assignments:
            if date_str in self.daily_assignments[boat_name]:
                return self.daily_assignments[boat_name][date_str]

        num_trips = self._num_trips_for_date(current_date)

        assigned_trips = []
        if num_trips > 0:
            if num_trips <= len(self.available_trips):
                assigned_trips = random.sample(self.available_trips, num_trips)
            else:
                assigned_trips = random.choices(self.available_trips, k=num_trips)

        if boat_name not in self.daily_assignments:
            self.daily_assignments[boat_name] = {}
        self.daily_assignments[boat_name][date_str] = assigned_trips

        return assigned_trips

    def get_trip_for_slot(
        self, boat_name: str, current_date: datetime, slot: int
    ) -> Optional[Trip]:
        """
        Get the assigned trip for a specific time slot on a given date.

        Args:
            boat_name: Name of the boat
            current_date: Current simulation date
            slot: Time slot index (e.g. 0 = morning, 1 = afternoon).

        Returns:
            The assigned trip, or None if no trip exists for this slot.
        """
        date_str = current_date.strftime("%Y-%m-%d")

        if boat_name not in self.daily_assignments:
            return None

        if date_str not in self.daily_assignments[boat_name]:
            return None

        trips = self.daily_assignments[boat_name][date_str]
        if slot < len(trips):
            return trips[slot]

        return None

    def get_trips_for_date(self, boat_name: str, current_date: datetime) -> List[Trip]:
        """
        Get all assigned trips for a boat on a specific date.

        Args:
            boat_name: Name of the boat
            current_date: Date to get trips for

        Returns:
            List of trips assigned for this date (may be empty).
        """
        date_str = current_date.strftime("%Y-%m-%d")

        if boat_name not in self.daily_assignments:
            return []

        if date_str not in self.daily_assignments[boat_name]:
            return []

        return self.daily_assignments[boat_name][date_str]
