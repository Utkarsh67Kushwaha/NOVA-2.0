from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field
import uuid


class ReminderItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    due_timestamp: float
    due_at_iso: str
    created_at_iso: str = Field(default_factory=lambda: datetime.now().isoformat())
    status: Literal["PENDING", "TRIGGERED", "CANCELLED"] = "PENDING"
    repeat: Literal["NONE", "DAILY"] = "NONE"
    source: str = "SYSTEM"


class ReminderCreate(BaseModel):
    title: str
    due_seconds: Optional[int] = None
    time_expression: Optional[str] = None
    due_at_iso: Optional[str] = None
    repeat: Optional[Literal["NONE", "DAILY"]] = "NONE"
