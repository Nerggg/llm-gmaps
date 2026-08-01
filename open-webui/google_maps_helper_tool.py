"""
title: Google Maps Helper Tool
author: Developer
description: Queries a secure local proxy backend to fetch places with clean navigation links and directions.
version: 1.2.0
"""

import httpx
from typing import Generator, Callable


class Tools:
    def __init__(self):
        self.backend_url = "http://host.docker.internal:8000"

    async def search_places(self, query: str) -> str:
        """
        Search for restaurants, cafes, attractions, hotels, or any points of interest.
        Only use this tool to locate places or answer "where" questions.
        CRITICAL: Pass the user's requested location exactly as written. Do not append "near me" if the user has already specified a city, district, or address in their prompt.
        :param query: The search query (e.g., 'Sushi in Bandung' or 'coffee shops near me').
        :return: Markdown details and interactive map iframes for matched places.
        """
        try:
            # Defensive guard for empty queries
            if not query or len(query.strip()) < 2:
                return "Please provide a valid search query of at least 2 characters."

            url = f"{self.backend_url}/api/search"
            params = {"query": query}

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=15.0)
                if response.status_code != 200:
                    return f"Error from maps backend: {response.text}"

                data = response.json()
                results = data.get("results", [])

                if not results:
                    return f"No results found for '{query}'."

                markdown_out = f"### Found places matching '{query}':\n\n"

                for i, place in enumerate(results[:3], 1):
                    name = place.get("name")
                    address = place.get("address")
                    direct_url = place.get("direct_map_url")

                    markdown_out += f"**{i}. {name}**\n"
                    markdown_out += f"📍 *{address}*\n\n"
                    markdown_out += f"🔗 **[Open on Google Maps]({direct_url})**\n\n"
                    markdown_out += "---\n\n"

                return markdown_out

        except Exception as e:
            return f"An error occurred while calling the maps service: {str(e)}"

    async def get_directions(self, origin: str, destination: str) -> str:
        """
        Calculate travel route, distance, and duration between two specific locations.
        CRITICAL: Only call this tool if the user explicitly asks for routes, distance, or directions, AND provides BOTH a starting point and a destination. Do not guess parameters.
        :param origin: The exact starting address or place name.
        :param destination: The exact destination address or place name.
        :return: Markdown details showing estimated distance, time, and navigation URL.
        """
        # Defensive check to prevent small models from calling with empty strings
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

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=15.0)
                if response.status_code != 200:
                    return f"Error from directions backend: {response.text}"

                data = response.json()

                dist = data.get("distance", "Unknown")
                dur = data.get("duration", "Unknown")
                directions_url = data.get("directions_url")

                markdown_out = f"### 🚗 Routing Details:\n\n"
                markdown_out += f"* **Start Address:** {data.get('origin', origin)}\n"
                markdown_out += (
                    f"* **End Address:** {data.get('destination', destination)}\n"
                )
                markdown_out += f"* **Estimated Distance:** {dist}\n"
                markdown_out += f"* **Estimated Duration:** {dur}\n\n"
                markdown_out += f"👉 [View Route on Google Maps]({directions_url})\n\n"

                return markdown_out

        except Exception as e:
            return f"An error occurred while computing directions: {str(e)}"
