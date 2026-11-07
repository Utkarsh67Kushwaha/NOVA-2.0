"""
NOVA Safe Tools Framework - Live Weather & Environmental Intelligence Tool
Queries live real-time weather, temperature, humidity, and atmospheric conditions
using lightweight, zero-key JSON endpoints with graceful offline fallback.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
import httpx

from backend.app.tools.base import (
    BaseTool,
    RiskLevel,
    ToolParamSchema,
    ToolResult,
    VerificationResult,
)

logger = logging.getLogger("nova.tools.weather")


class WeatherTool(BaseTool):
    """Provides live, real-time weather and temperature reports for any city or current location."""

    def __init__(self):
        super().__init__(
            name="weather_tool",
            description="Get real-time live weather, temperature, and forecast for any city or auto-detected location.",
            category="desktop",
            risk_level=RiskLevel.READ_ONLY,
        )

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

    def execute(self, **kwargs: Any) -> ToolResult:
        city = str(kwargs.get("city", "")).strip()

        # Clean city name if colloquial phrasing was passed (e.g. "delhi ka", "in mumbai")
        city = re.sub(r"\b(?:in|me|ka|ki|weather|mausam|temperature|forecast)\b", "", city, flags=re.IGNORECASE).strip()

        url = f"https://wttr.in/{city}?format=j1" if city else "https://wttr.in/?format=j1"

        try:
            with httpx.Client(timeout=4.0) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    curr = data.get("current_condition", [{}])[0]
                    area_info = data.get("nearest_area", [{}])[0]

                    loc_name = area_info.get("areaName", [{}])[0].get("value", city or "Aapke shehar")
                    temp_c = curr.get("temp_C", "--")
                    feels_like_c = curr.get("FeelsLikeC", temp_c)
                    condition = curr.get("weatherDesc", [{}])[0].get("value", "Clear")
                    humidity = curr.get("humidity", "--")
                    wind_speed = curr.get("windspeedKmph", "--")

                    # Human-like conversational response in Hindi/English
                    output_msg = (
                        f"{loc_name} me abhi taapman {temp_c}°C hai (feels like {feels_like_c}°C) aur mausam {condition} hai. "
                        f"Humidity {humidity}% aur hawa ki gati {wind_speed} km/h hai."
                    )

                    return ToolResult(
                        tool_name=self.name,
                        success=True,
                        output=output_msg,
                        data={
                            "city": loc_name,
                            "temp_c": temp_c,
                            "feels_like_c": feels_like_c,
                            "condition": condition,
                            "humidity": humidity,
                            "wind_speed_kmph": wind_speed,
                        },
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
            fallback_city = city or "Aapke shehar"
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
