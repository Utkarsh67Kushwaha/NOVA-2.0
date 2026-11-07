"""
NOVA Safe Tools Framework - WhatsApp & Desktop Messaging Automation Tool
Dispatches WhatsApp messages via native Windows URI protocol (whatsapp://send)
with automatic fallback to Chrome Web WhatsApp and contact recipient detection.
"""

from __future__ import annotations

import logging
import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional
import webbrowser

from backend.app.tools.base import (
    BaseTool,
    RiskLevel,
    ToolParamSchema,
    ToolResult,
    VerificationResult,
)

logger = logging.getLogger("nova.tools.messaging")


class WhatsAppTool(BaseTool):
    """Dispatches WhatsApp messages to a contact or phone number via Windows WhatsApp or Web fallback."""

    def __init__(self):
        super().__init__(
            name="whatsapp_tool",
            description="Send or draft a WhatsApp message to a phone number or contact.",
            category="communication",
            risk_level=RiskLevel.LOW_RISK,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="message",
                type="string",
                description="Message text to send.",
                required=True,
            ),
            ToolParamSchema(
                name="phone",
                type="string",
                description="Recipient phone number (digits only, e.g. '9876543210'). Optional.",
                required=False,
                default="",
            ),
            ToolParamSchema(
                name="contact_name",
                type="string",
                description="Recipient contact name (e.g. 'Rahul', 'Priya'). Optional.",
                required=False,
                default="",
            ),
        ]

    def _normalize_phone(self, raw_phone: str) -> str:
        """Strips non-digits and formats Indian numbers to 91XXXXXXXXXX."""
        digits = re.sub(r"[^\d]", "", raw_phone)
        if not digits:
            return ""

        # If 11 digits starting with 0 (e.g. 09876543210), strip the leading 0
        if len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]

        # If 10 digits without country code, default to India (+91)
        if len(digits) == 10:
            return f"91{digits}"

        return digits

    def execute(self, **kwargs: Any) -> ToolResult:
        raw_msg = str(kwargs.get("message", "")).strip()
        raw_phone = str(kwargs.get("phone", "")).strip()
        contact_name = str(kwargs.get("contact_name", "")).strip()

        # If letters were passed in phone (e.g. phone="Rahul"), extract as contact_name
        if raw_phone and not any(char.isdigit() for char in raw_phone):
            if not contact_name:
                contact_name = raw_phone.capitalize()
            raw_phone = ""

        if not raw_msg:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="Message text cannot be empty.",
                error="Empty message parameter",
            )

        clean_phone = self._normalize_phone(raw_phone) if raw_phone else ""
        encoded_msg = urllib.parse.quote(raw_msg, safe="")

        # Construct URIs
        if clean_phone:
            uri = f"whatsapp://send?phone={clean_phone}&text={encoded_msg}"
            web_url = f"https://web.whatsapp.com/send?phone={clean_phone}&text={encoded_msg}"
            target_desc = f"number {clean_phone}"
        elif contact_name:
            uri = f"whatsapp://send?text={encoded_msg}"
            web_url = f"https://web.whatsapp.com/send?text={encoded_msg}"
            target_desc = f"contact '{contact_name}'"
        else:
            uri = f"whatsapp://send?text={encoded_msg}"
            web_url = f"https://web.whatsapp.com/send?text={encoded_msg}"
            target_desc = "WhatsApp"

        launched = False
        launch_mode = "native_app"

        try:
            # 1. Try Windows native whatsapp:// protocol if supported on OS
            if hasattr(os, "startfile"):
                os.startfile(uri)
                launched = True
            else:
                # Linux/macOS or headless test environment fallback
                webbrowser.open(web_url)
                launched = True
                launch_mode = "web_browser"

            if contact_name and not clean_phone:
                output_msg = (
                    f"WhatsApp khol diya gaya hai message: \"{raw_msg}\" ke sath. "
                    f"Kripya {contact_name} ko chat list se select karke send karein."
                )
            else:
                output_msg = f"Opening WhatsApp for {target_desc} with message: \"{raw_msg}\"."

        except Exception as exc:
            logger.info("Native WhatsApp launch failed, falling back to Web WhatsApp: %s", exc)
            try:
                webbrowser.open(web_url)
                launched = True
                launch_mode = "web_browser"
                output_msg = f"Opening Web WhatsApp for {target_desc} with message: \"{raw_msg}\"."
            except Exception as w_err:
                logger.error("Failed to open Web WhatsApp: %s", w_err)
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    output="Failed to launch WhatsApp or Web WhatsApp.",
                    error=str(w_err),
                )

        return ToolResult(
            tool_name=self.name,
            success=True,
            output=output_msg,
            data={
                "phone": clean_phone,
                "contact_name": contact_name,
                "message": raw_msg,
                "launched": launched,
                "mode": launch_mode,
            },
            verification=VerificationResult(
                verified=True,
                method=f"whatsapp_{launch_mode}_dispatch",
                details=f"WhatsApp draft triggered for {target_desc}.",
            ),
        )
