"""Natural Language Time & Duration Parser for NOVA Reminders (English & Hinglish)."""

import re
from datetime import datetime, timedelta
from typing import Tuple, Optional


def parse_time_expression(text: str) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Parses a reminder query to extract:
    1. due_seconds: integer seconds from now, or None
    2. clean_title: the task to remind about, or None
    3. time_str: the recognized time expression string
    """
    cleaned = text.strip()
    lowered = cleaned.lower()

    # 1. Colloquial Hindi phrases without leading digits:
    # "aadha ghanta baad" / "aadhe ghante me" -> 30 mins
    m_half = re.search(r'(?:aadha|aadhe)\s+ghant(?:a|e)\s*(?:baad|me|mein)?', lowered)
    if m_half:
        secs = 30 * 60
        title = re.sub(re.escape(m_half.group(0)), '', cleaned, flags=re.IGNORECASE).strip()
        title = clean_reminder_title(title, cleaned)
        return secs, title, "aadha ghanta"

    # "ek ghanta baad" / "ek ghante me" -> 60 mins
    m_one_hr = re.search(r'ek\s+ghant(?:a|e)\s*(?:baad|me|mein)?', lowered)
    if m_one_hr:
        secs = 60 * 60
        title = re.sub(re.escape(m_one_hr.group(0)), '', cleaned, flags=re.IGNORECASE).strip()
        title = clean_reminder_title(title, cleaned)
        return secs, title, "1 ghanta"

    # "derh ghanta baad" (1.5 hours) -> 90 mins
    m_one_half = re.search(r'(?:dedh|derh)\s+ghant(?:a|e)\s*(?:baad|me|mein)?', lowered)
    if m_one_half:
        secs = 90 * 60
        title = re.sub(re.escape(m_one_half.group(0)), '', cleaned, flags=re.IGNORECASE).strip()
        title = clean_reminder_title(title, cleaned)
        return secs, title, "1.5 ghante"

    # 2. Check relative seconds: "10 seconds", "10 second baad", "10s", "in 10 sec"
    m_sec = re.search(r'(?:in\s+)?(\d+)\s*(?:seconds?|secs?|second|sec)(?:\s*(?:baad|me|mein))?', lowered)
    if m_sec:
        secs = int(m_sec.group(1))
        title = re.sub(re.escape(m_sec.group(0)), '', cleaned, flags=re.IGNORECASE).strip()
        title = clean_reminder_title(title, cleaned)
        return secs, title, m_sec.group(0)

    # 3. Check relative minutes: "5 minutes", "5 minute baad", "5 mins", "in 15 min"
    m_min = re.search(r'(?:in\s+)?(\d+)\s*(?:minutes?|mins?|minute|min)(?:\s*(?:baad|me|mein))?', lowered)
    if m_min:
        mins = int(m_min.group(1))
        secs = mins * 60
        title = re.sub(re.escape(m_min.group(0)), '', cleaned, flags=re.IGNORECASE).strip()
        title = clean_reminder_title(title, cleaned)
        return secs, title, m_min.group(0)

    # 4. Check relative hours with numbers: "2 hours", "1 ghanta baad", "2 ghante baad", "in 3 hrs"
    m_hr = re.search(r'(?:in\s+)?(\d+)\s*(?:hours?|hrs?|ghanta|ghante)(?:\s*(?:baad|me|mein))?', lowered)
    if m_hr:
        hrs = int(m_hr.group(1))
        secs = hrs * 3600
        title = re.sub(re.escape(m_hr.group(0)), '', cleaned, flags=re.IGNORECASE).strip()
        title = clean_reminder_title(title, cleaned)
        return secs, title, m_hr.group(0)

    # 5. Check absolute clock time: "at 5:30 pm", "at 17:00", "5:30 baje", "5 baje"
    m_clock = re.search(r'(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|baje)?', lowered)
    if m_clock and (m_clock.group(2) or m_clock.group(3)):
        hour = int(m_clock.group(1))
        minute = int(m_clock.group(2)) if m_clock.group(2) else 0
        ampm = (m_clock.group(3) or "").lower()

        now = datetime.now()
        # Handle 12-hour AM/PM
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        elif ampm == "baje":
            # If specified "shaam ko 5 baje" or "raat ko" -> pm
            if "shaam" in lowered or "raat" in lowered or "dopehar" in lowered:
                if hour < 12:
                    hour += 12
            else:
                # If current hour is past that hour today, assume PM or next cycle
                if hour < now.hour and hour < 12:
                    hour += 12

        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target_time <= now:
            # If target time is earlier today, schedule for next day
            target_time += timedelta(days=1)

        diff_seconds = int((target_time - now).total_seconds())
        title = re.sub(r'(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm|baje)?', '', cleaned, flags=re.IGNORECASE).strip()
        title = clean_reminder_title(title, cleaned)
        return diff_seconds, title, target_time.strftime("%I:%M %p")

    # Fallback default: if user just says "remind me to call mom", default to 10 minutes
    clean_fallback = clean_reminder_title(cleaned, cleaned)
    return 600, clean_fallback or "Quick Reminder", "10 minutes"


def clean_reminder_title(raw_title: str, original_full_text: str) -> str:
    """Cleans up leading and trailing boilerplate reminder words from the task title."""
    cleaned = raw_title.strip()
    
    # Strip common leading patterns
    leading_patterns = [
        r'^(?:hey\s+nova|nova|please)?\s*',
        r'^(?:remind\s+me\s+to|remind\s+me|reminder\s+for|set\s+a\s+reminder\s+to|set\s+reminder\s+to|set\s+reminder|reminder\s+set\s+karo|reminder\s+lagao|mujhe\s+yaad\s+dilao\s+ki|yaad\s+dilana)\s*',
        r'^(?:in\s+|at\s+)',
    ]
    for pat in leading_patterns:
        cleaned = re.sub(pat, '', cleaned, flags=re.IGNORECASE).strip()

    # Strip common trailing patterns
    trailing_patterns = [
        r'(?:ka\s+reminder\s+lagao|ka\s+reminder|reminder\s+lagao|reminder\s+set\s+karo|karna\s+hai|karo|please|hai|pe\s+jana\s+hai)\s*$',
    ]
    for pat in trailing_patterns:
        cleaned = re.sub(pat, '', cleaned, flags=re.IGNORECASE).strip()

    # Clean leftover punctuation or extra spaces
    cleaned = re.sub(r'^[,\-:\s]+|[,\-:\s]+$', '', cleaned).strip()

    # If stripped empty, fallback to short original
    if not cleaned:
        cleaned = re.sub(r'^(?:hey\s+nova|nova)\s*', '', original_full_text, flags=re.IGNORECASE).strip()
    
    return cleaned.capitalize() if cleaned else "Reminder"
