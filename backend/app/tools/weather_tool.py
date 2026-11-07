"""
NOVA Safe Tools Framework - Live Weather & Environmental Intelligence Tool
Queries live real-time weather, temperature, humidity, and atmospheric conditions
using lightweight, zero-key JSON endpoints with graceful offline fallback and in-memory TTL caching.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx

from backend.app.tools.base import (
    BaseTool,
    RiskLevel,
    ToolParamSchema,
    ToolResult,
    VerificationResult,
)

logger = logging.getLogger("nova.tools.weather")

WEATHER_DESC_MAP: Dict[str, str] = {
    "Sunny": "dhoop khili hui (Sunny)",
    "Clear": "mausam saaf (Clear)",
    "Partly cloudy": "halka badal chhaya hua (Partly cloudy)",
    "Cloudy": "badal chhaya hua (Cloudy)",
    "Overcast": "ghana badal (Overcast)",
    "Mist": "halka kohra (Mist)",
    "Fog": "kohra (Fog)",
    "Light rain": "halki barish (Light rain)",
    "Moderate rain": "barish (Moderate rain)",
    "Heavy rain": "tez barish (Heavy rain)",
    "Patchy rain possible": "halki barish ki sambhavna (Patchy rain)",
    "Thundery outbreaks possible": "toofan aur garaj ki sambhavna (Thunderstorm)",
    "Light snow": "halki barafbaari (Light snow)",
    "Heavy snow": "tez barafbaari (Heavy snow)",
}


class WeatherTool(BaseTool):
    """Provides live, real-time weather and temperature reports for any city or current location."""

    def __init__(self, cache_ttl_seconds: int = 600):
        super().__init__(
            name="weather_tool",
            description="Get real-time live weather, temperature, and forecast for any city or auto-detected location.",
            category="desktop",
            risk_level=RiskLevel.READ_ONLY,
        )
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: Dict[str, Tuple[float, Dict[str, Any], str]] = {}
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=httpx.Timeout(connect=2.5, read=4.0, write=2.0, pool=2.0),
                headers={"User-Agent": "NOVA-Voice-Assistant/2.0"},
                follow_redirects=True,
            )
        return self._client

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="city",
                type="string",
                description="City name (e.g. 'Delhi', 'Mumbai', 'London', 'New York'). Omit for current location.",
                required=False,
                default="",
            )
        ]

    def _clean_city(self, raw_city: str) -> str:
        city = raw_city.strip()
        # Remove colloquial words
        city = re.sub(
            r"\b(?:in|me|ka|ki|weather|mausam|temperature|taapman|forecast|today|aaj|check|batao|bataiye)\b",
            "",
            city,
            flags=re.IGNORECASE,
        ).strip()
        city = re.sub(r"\s+", " ", city)
        return city

    def execute(self, **kwargs: Any) -> ToolResult:
        raw_city = str(kwargs.get("city", "")).strip()
        city = self._clean_city(raw_city)
        cache_key = city.lower()

        now = time.time()
        # Check in-memory cache
        if cache_key in self._cache:
            timestamp, data, output_msg = self._cache[cache_key]
            if now - timestamp < self.cache_ttl_seconds:
                logger.info(
                    "Serving weather for '%s' from cache (age=%.1fs)",
                    city or "current_location",
                    now - timestamp,
                )
                cached_data = dict(data)
                cached_data["cached"] = True
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    output=output_msg,
                    data=cached_data,
                    verification=VerificationResult(
                        verified=True,
                        method="in_memory_cache",
                        details=f"Weather report served from local cache (age {int(now - timestamp)}s).",
                    ),
                )

        # wttr.in URL: format=j1 provides clean JSON
        # replace spaces with + for multi-word cities (e.g. "new york" -> "new+york")
        url_city = city.replace(" ", "+") if city else ""
        url = f"https://wttr.in/{url_city}?format=j1" if url_city else "https://wttr.in/?format=j1"

        try:
            client = self._get_client()
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                curr_list = data.get("current_condition", [])
                curr = curr_list[0] if curr_list else {}
                area_list = data.get("nearest_area", [])
                area_info = area_list[0] if area_list else {}

                loc_name = ""
                area_name_list = area_info.get("areaName", [])
                if area_name_list and isinstance(area_name_list, list):
                    loc_name = area_name_list[0].get("value", "")
                if not loc_name:
                    loc_name = city.title() if city else "Aapke shehar"

                temp_c = curr.get("temp_C", "--")
                feels_like_c = curr.get("FeelsLikeC", temp_c)
                raw_desc = "Clear"
                weather_desc_list = curr.get("weatherDesc", [])
                if weather_desc_list and isinstance(weather_desc_list, list):
                    raw_desc = weather_desc_list[0].get("value", "Clear")

                # Natural Hindi descriptor
                condition_hindi = WEATHER_DESC_MAP.get(raw_desc, raw_desc)
                humidity = curr.get("humidity", "--")
                wind_speed = curr.get("windspeedKmph", "--")

                output_msg = (
                    f"{loc_name} me abhi taapman {temp_c}°C hai (feels like {feels_like_c}°C) aur mausam {condition_hindi} hai. "
                    f"Humidity {humidity}% aur hawa ki gati {wind_speed} km/h hai."
                )

                result_data = {
                    "city": loc_name,
                    "temp_c": temp_c,
                    "feels_like_c": feels_like_c,
                    "condition": raw_desc,
                    "condition_desc": condition_hindi,
                    "humidity": humidity,
                    "wind_speed_kmph": wind_speed,
                    "cached": False,
                }

                # Save to cache
                self._cache[cache_key] = (now, result_data, output_msg)

                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    output=output_msg,
                    data=result_data,
                    verification=VerificationResult(
                        verified=True,
                        method="live_wttr_query",
                        details="Live weather report fetched successfully.",
                    ),
                )
            else:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    output=f"Weather service returned status {resp.status_code}.",
                    error=f"HTTP {resp.status_code}",
                )
        except Exception as exc:
            logger.warning("Weather fetch failed: %s", exc)
            fallback_city = city.title() if city else "Aapke shehar"
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=f"{fallback_city} ka live weather fetch karte waqt network issue aaya. Kripya internet connection check karein.",
                data={"city": fallback_city, "offline": True},
                verification=VerificationResult(
                    verified=False,
                    method="weather_offline_fallback",
                    details=str(exc),
                ),
            )
