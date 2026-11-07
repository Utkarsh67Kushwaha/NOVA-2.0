"""NOVA 2.0 Smart Voice Notes & Scratchpad Data Models."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class NoteItem(BaseModel):
    """Represents a single persistent desktop note."""

    id: str = Field(default_factory=lambda: f"note_{uuid.uuid4().hex[:8]}")
    title: str = Field(default="Quick Note")
    content: str = Field(..., description="The note content or body text")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())


class NoteCreate(BaseModel):
    """Schema for creating a new note via API or Tool."""

    content: str = Field(..., description="Note text content", min_length=1)
    title: Optional[str] = Field(default=None, description="Optional note title")
