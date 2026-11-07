"""
NOVA Safe Tools Framework - WhatsApp & Desktop Messaging Automation Tool
Dispatches WhatsApp messages via native Windows URI protocol (whatsapp://send)
with automatic fallback to Chrome Web WhatsApp.
"""

from __future__ import annotations

import logging
import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional
import subprocess

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
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        raw_msg = str(kwargs.get("message", "")).strip()
        raw_phone = str(kwargs.get("phone", "")).strip()

        if not raw_msg:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="Message text cannot be empty.",
                error="Empty message parameter",
            )

        # Normalize phone number (strip spaces, dashes, parentheses)
        clean_phone = re.sub(r"[^\d+]", "", raw_phone)
        if clean_phone and len(clean_phone) == 10 and not clean_phone.startswith("+"):
            # Default to India +91 if 10-digit number is provided without country code
            clean_phone = f"91{clean_phone}"

        encoded_msg = urllib.parse.quote(raw_msg)

        # 1. Try Windows native whatsapp:// URI protocol
        if clean_phone:
            uri = f"whatsapp://send?phone={clean_phone}&text={encoded_msg}"
            web_url = f"https://web.whatsapp.com/send?phone={clean_phone}&text={encoded_msg}"
        else:
            uri = f"whatsapp://send?text={encoded_msg}"
            web_url = f"https://web.whatsapp.com/send?text={encoded_msg}"

        launched = False
        try:
            # Try launching via Windows shell start command
            os.startfile(uri)
            launched = True
            target_str = f"to {clean_phone}" if clean_phone else ""
            output_msg = f"Opening WhatsApp {target_str} with message: \"{raw_msg}\"."
        except Exception as exc:
            logger.info("Native WhatsApp client not registered, falling back to Web WhatsApp: %s", exc)
            # Fallback to Chrome / system default browser
            try:
                import webbrowser
                webbrowser.open(web_url)
                launched = True
                target_str = f"to {clean_phone}" if clean_phone else ""
                output_msg = f"Opening Web WhatsApp {target_str} with message: \"{raw_msg}\"."
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
                "message": raw_msg,
                "launched": launched,
            },
            verification=VerificationResult(
                verified=True,
                method="whatsapp_uri_dispatch",
                details="WhatsApp message draft opened successfully.",
            ),
        )
