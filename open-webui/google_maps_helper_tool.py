"""
title: Google Maps Helper Tool
author: Developer
description: Queries a secure local proxy backend to fetch places with clean navigation links and directions.
version: 1.3.0
"""

import httpx
from typing import Generator, Callable
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        BACKEND_API_KEY: str = Field(
            default="this_is_a_secure_token",
            description="The secret token used to authenticate requests with your FastAPI backend proxy."
        )

    def __init__(self):
        self.backend_url = "http://host.docker.internal:8000"
        # instantiate the default valves
        self.valves = self.Valves()

    async def search_places(self, query: str, limit: int = 3) -> str:
        """
        Search for restaurants, cafes, attractions, hotels, or any points of interest.
        Only use this tool to locate places or answer "where" questions.
        CRITICAL: Pass the user's requested location exactly as written. Do not append "near me" if the user has already specified a city, district, or address in their prompt.
        :param query: The search query (e.g., 'Sushi in Bandung' or 'coffee shops near me').
        :param limit: The maximum number of places to return (default is 3). Pass the exact count if the user requested a specific number of places (e.g., if the user asks for 5 places, limit should be 5).
        :return: Markdown details and interactive map images for matched places.
        """
        try:
            # defensive guard for empty queries
            if not query or len(query.strip()) < 2:
                return "Please provide a valid search query of at least 2 characters."

            warning_msg = ""
            try:
                original_limit = int(limit)
                safe_limit = max(1, min(original_limit, 5))
                
                # if the user (or llm) requested more than 5, generate the notice
                if original_limit > 5:
                    warning_msg = (
                        "NOTICE TO ASSISTANT: The user requested more than 5 results, but we have capped the output at 5 to prevent the response from getting too long. "
                        "You MUST begin your final response by stating this exact limit notice to the user in a friendly way.\n\n"
                    )
            except (ValueError, TypeError):
                safe_limit = 3

            url = f"{self.backend_url}/api/search"
            params = {"query": query}
            
            headers = {"X-API-Key": self.valves.BACKEND_API_KEY}

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, headers=headers, timeout=15.0)
                if response.status_code != 200:
                    return f"Error from maps backend: {response.text}"

                data = response.json()
                results = data.get("results", [])

                if not results:
                    return f"No results found for '{query}'."

                markdown_out = f"{warning_msg}### Found places matching '{query}':\n\n"

                for i, place in enumerate(results[:safe_limit], 1):
                    name = place.get("name")
                    address = place.get("address")
                    static_url = place.get("static_map_url")
                    direct_url = place.get("direct_map_url")

                    markdown_out += f"**{i}. {name}**\n"
                    markdown_out += f"📍 *{address}*\n\n"
                    
                    if static_url:
                        markdown_out += f"![Map of {name}]({static_url})\n\n"
                    
                    markdown_out += f"🔗 **[Open on Google Maps]({direct_url})**\n\n"
                    markdown_out += "---\n\n"

                return markdown_out

        except Exception as e:
            return f"An error occurred while calling the maps service: {str(e)}"

    async def get_directions(self, origin: str, destination: str) -> str:
        """
        Calculate travel route, distance, and duration between two specific locations.
        CRITICAL: Only call this tool if the user explicitly asks for routes, distance, or directions, AND provides BOTH a starting point and a destination. Do not guess parameters.
        :param origin: The starting place name or address exactly as provided by the user. Do NOT attempt to guess, expand, or resolve the street address yourself.
        :param destination: The destination place name or address exactly as provided by the user. Do NOT attempt to guess, expand, or resolve the street address yourself.
        :return: Markdown details showing estimated distance, time, and navigation URL.
        """
        if (
            not origin
            or not destination
            or len(origin.strip()) < 2
            or len(destination.strip()) < 2
        ):
            return "Unable to compute directions. Please provide both a valid starting point and a destination."

        try:
            url = f"{self.backend_url}/api/directions"
            params = {"origin": origin, "destination": destination}
            
            headers = {"X-API-Key": self.valves.BACKEND_API_KEY}

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, headers=headers, timeout=15.0)
                if response.status_code != 200:
                    return f"Error from directions backend: {response.text}"

                data = response.json()

                dist = data.get("distance", "Unknown")
                dur = data.get("duration", "Unknown")
                static_url = data.get("static_map_url")
                directions_url = data.get("directions_url")

                markdown_out = f"### Routing Details:\n\n"
                markdown_out += f"* **Start Address:** {data.get('origin', origin)}\n"
                markdown_out += (
                    f"* **End Address:** {data.get('destination', destination)}\n"
                )
                markdown_out += f"* **Estimated Distance:** {dist}\n"
                markdown_out += f"* **Estimated Duration:** {dur}\n\n"
                markdown_out += f"[View Route on Google Maps]({directions_url})\n\n"

                if static_url:
                    markdown_out += f"![Route Map]({static_url})\n\n"

                markdown_out += f"[View Route on Google Maps]({directions_url})\n\n"

                markdown_out += (
                    "\n\n*SYSTEM NOTE TO ASSISTANT: You MUST present the markdown route map image (![Route Map](...)) "
                    "and the bold [View Route on Google Maps] link verbatim in your final reply. "
                    "Do not summarize, do not shorten, and do not omit them under any circumstances.*"
                )

                return markdown_out

        except Exception as e:
            return f"An error occurred while computing directions: {str(e)}"
