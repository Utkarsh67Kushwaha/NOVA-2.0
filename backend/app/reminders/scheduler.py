"""NOVA 2.0 Reminders & Alarms Background Scheduler & Windows Toast Engine."""

import os
import time
import json
import logging
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from backend.app.reminders.reminder_model import ReminderItem
from backend.app.reminders.time_parser import parse_time_expression
from backend.app.voice.tts import tts_service

logger = logging.getLogger("nova.reminders.scheduler")

REMINDERS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "reminders.json"


class ReminderScheduler:
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or REMINDERS_FILE
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.reminders: List[ReminderItem] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._load_from_disk()
        self.start()

    def start(self):
        """Starts the background monitoring thread."""
        with self._lock:
            if not self._running:
                self._running = True
                self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="NovaReminderMonitor")
                self._thread.start()
                logger.info("NOVA Reminder Scheduler thread started.")

    def stop(self):
        """Stops the monitoring thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            logger.info("NOVA Reminder Scheduler stopped.")

    def create_reminder(
        self,
        title: str,
        due_seconds: Optional[int] = None,
        time_expression: Optional[str] = None,
        due_at_iso: Optional[str] = None,
        source: str = "API",
    ) -> ReminderItem:
        """Schedules a new reminder."""
        now_ts = time.time()
        final_secs = due_seconds

        if final_secs is None and time_expression:
            parsed_secs, parsed_title, _ = parse_time_expression(f"{title} {time_expression}")
            final_secs = parsed_secs
            if parsed_title:
                title = parsed_title

        if final_secs is None:
            # Check if title itself contains time expression (e.g. "drink water in 10 seconds")
            parsed_secs, parsed_title, _ = parse_time_expression(title)
            final_secs = parsed_secs or 600
            if parsed_title:
                title = parsed_title

        target_ts = now_ts + max(1, final_secs)
        due_dt = datetime.fromtimestamp(target_ts)

        item = ReminderItem(
            title=title,
            due_timestamp=target_ts,
            due_at_iso=due_dt.isoformat(),
            status="PENDING",
            source=source,
        )

        with self._lock:
            self.reminders.append(item)
            self._save_to_disk()

        logger.info("Created reminder '%s' (ID: %s, due in %ds at %s)", item.title, item.id, final_secs, due_dt.strftime("%H:%M:%S"))
        return item

    def get_all_reminders(self) -> List[ReminderItem]:
        with self._lock:
            # Sort with pending first, then by due timestamp
            return sorted(
                list(self.reminders),
                key=lambda r: (0 if r.status == "PENDING" else 1, r.due_timestamp),
            )

    def get_active_reminders(self) -> List[ReminderItem]:
        with self._lock:
            return [r for r in self.reminders if r.status == "PENDING"]

    def cancel_reminder(self, reminder_id: str) -> bool:
        with self._lock:
            for r in self.reminders:
                if r.id == reminder_id and r.status == "PENDING":
                    r.status = "CANCELLED"
                    self._save_to_disk()
                    logger.info("Cancelled reminder '%s' (ID: %s)", r.title, r.id)
                    return True
        return False

    def delete_reminder(self, reminder_id: str) -> bool:
        with self._lock:
            initial_len = len(self.reminders)
            self.reminders = [r for r in self.reminders if r.id != reminder_id]
            if len(self.reminders) < initial_len:
                self._save_to_disk()
                logger.info("Deleted reminder ID: %s", reminder_id)
                return True
        return False

    def _monitor_loop(self):
        """Continuously checks for due reminders every second."""
        while self._running:
            try:
                now_ts = time.time()
                due_items = []
                with self._lock:
                    for r in self.reminders:
                        if r.status == "PENDING" and now_ts >= r.due_timestamp:
                            r.status = "TRIGGERED"
                            due_items.append(r)
                    if due_items:
                        self._save_to_disk()

                for item in due_items:
                    self._trigger_reminder(item)

            except Exception as e:
                logger.error("Error in reminder monitor loop: %s", e)

            time.sleep(1.0)

    def _trigger_reminder(self, item: ReminderItem):
        """Triggers Windows toast notification and TTS voice announcement."""
        logger.info("TRIGGERING REMINDER: '%s' (ID: %s)", item.title, item.id)

        # 1. Show native Windows Toast Notification
        self._show_windows_toast("NOVA Reminder Alert ⏰", item.title)

        # 2. Spoken voice notification
        try:
            spoken_msg = f"Reminder: {item.title}"
            tts_service.speak(spoken_msg, blocking=False)
        except Exception as e:
            logger.warning("Failed to speak reminder alert: %s", e)

    def _show_windows_toast(self, title: str, message: str):
        """Dispatches a native Windows 10/11 WinRT Toast Notification via PowerShell."""
        safe_title = title.replace('"', '`"').replace("'", "''")
        safe_msg = message.replace('"', '`"').replace("'", "''")

        ps_script = (
            f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; "
            f"$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02; "
            f"$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template); "
            f"$textNodes = $xml.GetElementsByTagName('text'); "
            f"$null = $textNodes.Item(0).AppendChild($xml.CreateTextNode('{safe_title}')); "
            f"$null = $textNodes.Item(1).AppendChild($xml.CreateTextNode('{safe_msg}')); "
            f"$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); "
            f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('NOVA.Assistant').Show($toast);"
        )

        try:
            subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as e:
            logger.warning("Failed to show Windows toast: %s", e)

    def _save_to_disk(self):
        try:
            data = [r.model_dump() for r in self.reminders]
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save reminders to disk: %s", e)

    def _load_from_disk(self):
        if not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.reminders = [ReminderItem(**item) for item in data]
            logger.info("Loaded %d reminders from disk.", len(self.reminders))
        except Exception as e:
            logger.error("Failed to load reminders from disk: %s", e)


# Global singleton scheduler
reminder_scheduler = ReminderScheduler()
