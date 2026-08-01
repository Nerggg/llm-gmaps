import httpx
from typing import Dict, Any, Optional
from backend.config import settings

class GoogleMapsService:
    def __init__(self):
        # use the private server-side key for backend rest requests
        self.api_key = settings.GOOGLE_MAPS_SERVER_KEY
        self.places_endpoint = "https://places.googleapis.com/v1/places:searchText"
        self.routes_endpoint = "https://routes.googleapis.com/directions/v2:computeRoutes"

    async def search_places(self, query: str) -> Dict[str, Any]:
        """
        Queries Google Places API (New) via POST using a field mask.
        """
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            # limit what data google returns to keep costs low and optimize speed.
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location"
        }
        
        payload = {
            "textQuery": query
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(self.places_endpoint, headers=headers, json=payload, timeout=10.0)
            response.raise_for_status()
            return response.json()

    async def get_directions_info(self, origin: str, destination: str) -> Optional[Dict[str, Any]]:
        """
        Queries Google Routes API (New) to calculate precise travel details.
        """
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters"
        }
        
        payload = {
            "origin": {
                "address": origin
            },
            "destination": {
                "address": destination
            },
            "travelMode": "DRIVE"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(self.routes_endpoint, headers=headers, json=payload, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            
            if data.get("routes") and len(data["routes"]) > 0:
                route = data["routes"][0]
                
                meters = route.get("distanceMeters", 0)
                km = round(meters / 1000.0, 1)
                distance_str = f"{km} km"
                
                duration_str = route.get("duration", "0s")
                try:
                    seconds = int(duration_str.rstrip('s'))
                    minutes = seconds // 60
                    time_str = f"{minutes} mins"
                except ValueError:
                    time_str = "Unknown"
                
                return {
                    "distance": distance_str,
                    "duration": time_str
                }
            return None

google_maps_service = GoogleMapsService()
