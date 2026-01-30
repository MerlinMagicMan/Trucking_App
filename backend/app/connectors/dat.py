"""
DAT connector stub
Placeholder for future DAT API integration
"""
from typing import List, Dict, Any, Tuple
from datetime import datetime

from app.connectors.base import BaseConnector
from app.models.canonical import CanonicalLoad


class DatConnector(BaseConnector):
    """
    DAT load board connector stub
    Returns empty results for MVP
    Will be implemented when DAT API credentials are available
    """

    def __init__(self):
        super().__init__(name="dat")

    def search_loads(
        self,
        truck_lat: float,
        truck_lng: float,
        radius_miles: int = 250,
        equipment: str = "reefer",
        **kwargs
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Stub implementation - returns empty results
        """
        query_metadata = {
            "connector": self.name,
            "truck_location": {"lat": truck_lat, "lng": truck_lng},
            "radius_miles": radius_miles,
            "equipment": equipment,
            "total_loads_found": 0,
            "query_timestamp": datetime.utcnow().isoformat(),
            "status": "stub"
        }

        return [], query_metadata

    def normalize(self, raw_load: Dict[str, Any]) -> CanonicalLoad:
        """
        Stub implementation
        Will implement DAT-specific normalization when API is integrated
        """
        raise NotImplementedError("DAT connector is a stub - normalization not implemented")

    def health_check(self) -> Dict[str, Any]:
        """Stub health check"""
        return {
            "status": "stub",
            "connector": self.name,
            "message": "DAT connector is a stub - not yet implemented"
        }
