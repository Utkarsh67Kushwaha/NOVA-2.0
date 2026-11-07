"""NOVA 2.0 Persistent Notes & Voice Scratchpad Manager."""

import json
import logging
import os
from pathlib import Path
import subprocess
import threading
from typing import List, Optional

from backend.app.notes.note_model import NoteItem

logger = logging.getLogger("nova.notes.manager")

NOTES_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "notes.json"


class NoteManager:
    """Thread-safe persistent note manager for quick voice notes and scratchpad entries."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or NOTES_FILE
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.notes: List[NoteItem] = []
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Loads notes from persistent JSON file."""
        with self._lock:
            if not self.storage_path.exists():
                self.notes = []
                return

            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.notes = [NoteItem(**item) for item in data]
                logger.info("Loaded %d notes from %s", len(self.notes), self.storage_path)
            except Exception as e:
                logger.error("Failed to load notes: %s", e)
                self.notes = []

    def _save_to_disk(self) -> None:
        """Persists current notes list to disk atomically to prevent corruption."""
        temp_path = self.storage_path.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump([n.model_dump() for n in self.notes], f, indent=2, ensure_ascii=False)
            temp_path.replace(self.storage_path)
        except Exception as e:
            logger.error("Failed to save notes to disk: %s", e)
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    def create_note(self, content: str, title: Optional[str] = None) -> NoteItem:
        """Creates and stores a new note."""
        cleaned_content = content.strip()
        if not cleaned_content:
            raise ValueError("Note content cannot be empty.")

        final_title = title.strip() if title and title.strip() else None
        if not final_title:
            # Generate a short smart title from first 5 words
            words = cleaned_content.split()
            first_words = " ".join(words[:5])
            final_title = f"{first_words}..." if len(words) > 5 else first_words
            final_title = final_title.capitalize()

        with self._lock:
            item = NoteItem(
                title=final_title,
                content=cleaned_content,
            )
            # Prepend latest note to top
            self.notes.insert(0, item)
            self._save_to_disk()
            logger.info("Created new note [%s]: '%s'", item.id, item.title)
            return item

    def list_notes(self) -> List[NoteItem]:
        """Returns all saved notes, most recent first."""
        with self._lock:
            return list(self.notes)

    def get_latest_note(self) -> Optional[NoteItem]:
        """Returns the most recent note."""
        with self._lock:
            return self.notes[0] if self.notes else None

    def delete_note(self, note_id: str) -> bool:
        """Deletes a note by its ID."""
        with self._lock:
            initial_count = len(self.notes)
            self.notes = [n for n in self.notes if n.id != note_id]
            deleted = len(self.notes) < initial_count
            if deleted:
                self._save_to_disk()
                logger.info("Deleted note %s", note_id)
            return deleted

    def clear_all_notes(self) -> int:
        """Clears all saved notes."""
        with self._lock:
            count = len(self.notes)
            self.notes = []
            self._save_to_disk()
            logger.info("Cleared %d notes", count)
            return count

    def open_in_notepad(self) -> Optional[str]:
        """Exports notes to a readable text file and opens it in Windows Notepad."""
        with self._lock:
            notes_copy = list(self.notes)

        # Export to Documents/NOVA_Notes.txt
        docs_dir = Path.home() / "Documents"
        docs_dir.mkdir(parents=True, exist_ok=True)
        export_file = docs_dir / "NOVA_Notes.txt"

        lines = [
            "========================================",
            "        NOVA 2.0 SMART VOICE NOTES      ",
            "========================================",
            f"Total Notes: {len(notes_copy)}",
            "",
        ]

        if not notes_copy:
            lines.append("No notes saved yet.")
        else:
            for idx, n in enumerate(notes_copy, 1):
                lines.append(f"[{idx}] {n.title} (ID: {n.id})")
                lines.append(f"Date: {n.created_at[:19].replace('T', ' ')}")
                lines.append(f"Content: {n.content}")
                lines.append("-" * 40)

        export_file.write_text("\n".join(lines), encoding="utf-8")

        # Open in Notepad
        try:
            subprocess.Popen(["notepad.exe", str(export_file)], shell=False)
            return str(export_file)
        except Exception as e:
            logger.error("Failed to open notes in Notepad: %s", e)
            return None


# Global singleton instance
note_manager = NoteManager()
