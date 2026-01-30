"""
Base connector interface
All load board connectors must implement this interface
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
from app.models.canonical import CanonicalLoad


class BaseConnector(ABC):
    """
    Abstract base class for load board connectors
    Enforces consistent interface for all data sources
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def search_loads(
        self,
        truck_lat: float,
        truck_lng: float,
        radius_miles: int = 250,
        equipment: str = "reefer",
        **kwargs
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Search for loads near truck location

        Args:
            truck_lat: Truck's current latitude
            truck_lng: Truck's current longitude
            radius_miles: Search radius in miles
            equipment: Equipment type (default: reefer)
            **kwargs: Additional connector-specific parameters

        Returns:
            Tuple of (raw_loads_list, query_metadata_dict)
        """
        pass

    @abstractmethod
    def normalize(self, raw_load: Dict[str, Any]) -> CanonicalLoad:
        """
        Normalize vendor-specific load data to CanonicalLoad format

        Args:
            raw_load: Raw load data from connector

        Returns:
            CanonicalLoad instance
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Check connector health and availability

        Returns:
            Dict with status, message, and metadata
        """
        pass

    def fetch_and_normalize(
        self,
        truck_lat: float,
        truck_lng: float,
        radius_miles: int = 250,
        **kwargs
    ) -> Tuple[List[CanonicalLoad], Dict[str, Any]]:
        """
        Convenience method: search and normalize in one call

        Returns:
            Tuple of (normalized_loads, query_metadata)
        """
        raw_loads, query_metadata = self.search_loads(
            truck_lat, truck_lng, radius_miles, **kwargs
        )
        normalized_loads = [self.normalize(load) for load in raw_loads]
        return normalized_loads, query_metadata
