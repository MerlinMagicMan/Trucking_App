"""
Truckstop connector implementation
Uses mock JSON data for MVP (will connect to real API in production)
"""
import json
import os
from typing import List, Dict, Any, Tuple
from datetime import datetime
from geopy.distance import geodesic

from app.connectors.base import BaseConnector
from app.models.canonical import CanonicalLoad, PickupDeliveryLocation


class TruckstopConnector(BaseConnector):
    """
    Truckstop load board connector
    MVP: Loads from mock JSON file
    Future: Real API integration
    """

    def __init__(self, mock_data_path: str = "app/data/mock_loads_ok_tx.json"):
        super().__init__(name="truckstop")
        self.mock_data_path = mock_data_path
        self._mock_data = None

    def _load_mock_data(self) -> List[Dict[str, Any]]:
        """Load mock data from JSON file"""
        if self._mock_data is None:
            file_path = os.path.join(os.path.dirname(__file__), "..", "data", "mock_loads_ok_tx.json")
            with open(file_path, "r") as f:
                self._mock_data = json.load(f)
        return self._mock_data

    def search_loads(
        self,
        truck_lat: float,
        truck_lng: float,
        radius_miles: int = 250,
        equipment: str = "reefer",
        **kwargs
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Search for loads within radius of truck location
        Filters mock data by distance from truck
        """
        all_loads = self._load_mock_data()
        truck_location = (truck_lat, truck_lng)

        # Filter by distance to pickup location
        filtered_loads = []
        for load in all_loads:
            pickup_location = (load["pickup"]["lat"], load["pickup"]["lng"])
            distance = geodesic(truck_location, pickup_location).miles

            if distance <= radius_miles:
                # Add deadhead distance to load data for reference
                load["deadhead_miles"] = round(distance, 1)
                filtered_loads.append(load)

        # Sort by deadhead distance (closest first)
        filtered_loads.sort(key=lambda x: x["deadhead_miles"])

        query_metadata = {
            "connector": self.name,
            "truck_location": {"lat": truck_lat, "lng": truck_lng},
            "radius_miles": radius_miles,
            "equipment": equipment,
            "total_loads_found": len(filtered_loads),
            "query_timestamp": datetime.utcnow().isoformat()
        }

        return filtered_loads, query_metadata

    def normalize(self, raw_load: Dict[str, Any]) -> CanonicalLoad:
        """
        Normalize Truckstop load data to CanonicalLoad format
        """
        # Parse datetime strings
        posted_at = datetime.fromisoformat(raw_load["posted_at"].replace("Z", "+00:00"))

        pickup_window_start = None
        pickup_window_end = None
        if raw_load["pickup"].get("window_start"):
            pickup_window_start = datetime.fromisoformat(
                raw_load["pickup"]["window_start"].replace("Z", "+00:00")
            )
        if raw_load["pickup"].get("window_end"):
            pickup_window_end = datetime.fromisoformat(
                raw_load["pickup"]["window_end"].replace("Z", "+00:00")
            )

        delivery_window_start = None
        delivery_window_end = None
        if raw_load["delivery"].get("window_start"):
            delivery_window_start = datetime.fromisoformat(
                raw_load["delivery"]["window_start"].replace("Z", "+00:00")
            )
        if raw_load["delivery"].get("window_end"):
            delivery_window_end = datetime.fromisoformat(
                raw_load["delivery"]["window_end"].replace("Z", "+00:00")
            )

        # Create canonical load
        return CanonicalLoad(
            id=f"truckstop_{raw_load['id']}",
            source="truckstop",
            external_id=raw_load["id"],
            posted_at=posted_at,
            equipment="reefer",
            pickup=PickupDeliveryLocation(
                city=raw_load["pickup"]["city"],
                state=raw_load["pickup"]["state"],
                lat=raw_load["pickup"]["lat"],
                lng=raw_load["pickup"]["lng"],
                window_start=pickup_window_start,
                window_end=pickup_window_end
            ),
            delivery=PickupDeliveryLocation(
                city=raw_load["delivery"]["city"],
                state=raw_load["delivery"]["state"],
                lat=raw_load["delivery"]["lat"],
                lng=raw_load["delivery"]["lng"],
                window_start=delivery_window_start,
                window_end=delivery_window_end
            ),
            rate_total=raw_load["rate_total"],
            miles=raw_load.get("miles"),
            notes=raw_load.get("notes")
        )

    def health_check(self) -> Dict[str, Any]:
        """Check if mock data is accessible"""
        try:
            loads = self._load_mock_data()
            return {
                "status": "ok",
                "connector": self.name,
                "message": f"Mock data loaded successfully ({len(loads)} loads)",
                "loads_available": len(loads)
            }
        except Exception as e:
            return {
                "status": "error",
                "connector": self.name,
                "message": f"Failed to load mock data: {str(e)}"
            }
