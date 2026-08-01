import time
import re
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import urllib.parse

from backend.services.google_maps import google_maps_service
from backend.config import settings

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="HeyPico Maps Proxy API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TTLCache:
    def __init__(self, ttl_seconds: int = 1800):
        self.ttl = ttl_seconds
        self.cache = {}

    def get(self, key: str):
        if key in self.cache:
            value, expiry = self.cache[key]
            if time.time() < expiry:
                return value
            del self.cache[key]
        return None

    def set(self, key: str, value):
        self.cache[key] = (value, time.time() + self.ttl)

search_cache = TTLCache()

def sanitize_input(text: str) -> str:
    """
    Sanitizes queries, strips out redundant conversational phrases like 'near me',
    and removes dangerous characters to ensure clean search strings.
    """
    clean = re.sub(r"\bnear\s+me\b", "", text, flags=re.IGNORECASE)
    
    clean = re.sub(r"[^\w\s\-\,\.]", "", clean)
    
    clean = re.sub(r"\s+", " ", clean)
    
    return clean.strip()[:100]

@app.get("/api/search")
@limiter.limit("15/minute")
async def search_places(request: Request, query: str = Query(..., min_length=2)):
    sanitized_query = sanitize_input(query)
    
    cached_response = search_cache.get(sanitized_query)
    if cached_response:
        return {**cached_response, "source": "cache"}
    
    try:
        raw_data = await google_maps_service.search_places(sanitized_query)
        
        # results are returned in a "places" list
        places = raw_data.get("places", [])
        formatted_results = []
        
        for place in places[:5]:  # process top 5 locations
            place_id = place.get("id")
            name = place.get("displayName", {}).get("text", "Unknown Name")
            address = place.get("formattedAddress", "")
            lat = place.get("location", {}).get("latitude")
            lng = place.get("location", {}).get("longitude")
            
            # formulate the google maps embed and direct urls
            static_url = f"https://maps.googleapis.com/maps/api/staticmap?center={lat},{lng}&zoom=15&size=500x300&markers=color:red%7C{lat},{lng}&key={settings.GOOGLE_MAPS_CLIENT_KEY}"
            embed_url = f"https://www.google.com/maps/embed/v1/place?key={settings.GOOGLE_MAPS_CLIENT_KEY}&q=place_id:{place_id}"
            view_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}&query_place_id={place_id}"
            
            formatted_results.append({
                "place_id": place_id,
                "name": name,
                "address": address,
                "coordinates": {"lat": lat, "lng": lng},
                "static_map_url": static_url,
                "embed_map_url": embed_url,
                "direct_map_url": view_url
            })
            
        payload = {"query": sanitized_query, "results": formatted_results}
        search_cache.set(sanitized_query, payload)
        
        return {**payload, "source": "live_api"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query location services: {str(e)}")


@app.get("/api/directions")
@limiter.limit("15/minute")
async def get_directions(
    request: Request, 
    origin: str = Query(..., min_length=2), 
    destination: str = Query(..., min_length=2)
):
    sanitized_origin = sanitize_input(origin)
    sanitized_dest = sanitize_input(destination)
    
    try:
        info = await google_maps_service.get_directions_info(sanitized_origin, sanitized_dest)
        
        safe_origin = urllib.parse.quote(sanitized_origin)
        safe_dest = urllib.parse.quote(sanitized_dest)
        
        directions_url = f"https://www.google.com/maps/dir/?api=1&origin={safe_origin}&destination={safe_dest}"
        
        if info:
            return {
                "origin": sanitized_origin,
                "destination": sanitized_dest,
                "distance": info["distance"],
                "duration": info["duration"],
                "directions_url": directions_url
            }
            
        return {
            "origin": sanitized_origin,
            "destination": sanitized_dest,
            "distance": "Unknown",
            "duration": "Unknown",
            "directions_url": directions_url
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch directions: {str(e)}")
