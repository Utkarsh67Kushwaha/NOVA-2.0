"""NOVA 2.0 Notes Package."""

from backend.app.notes.note_model import NoteItem, NoteCreate
from backend.app.notes.note_manager import note_manager, NoteManager

__all__ = ["NoteItem", "NoteCreate", "note_manager", "NoteManager"]
