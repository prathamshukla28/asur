"""A small, stdlib-only iCalendar (RFC 5545) writer - local export, never sync.

This closes the "stdlib ICS writer" obligation flagged in ``DEFERRED.md`` for the
Weekly Tracker planner (WT-G8) and the Life Mentor habit schedule (LM-G54). It
*writes a file you import yourself* into whatever calendar you use; it makes no
network call, signs in to nothing, and links no account (ASUR-LOCAL-01). It is
the honest opposite of "calendar sync": your data stays local and you stay in
control of what, if anything, you import.

Scope is deliberately the subset both callers need: all-day events (`VALUE=DATE`),
an optional exclusive end date for multi-day spans, an optional `RRULE` for
recurring items (daily habits), a summary and a description. Text is escaped and
lines are folded per RFC 5545, so the output imports cleanly into Apple Calendar,
Google Calendar and Outlook. Output is deterministic given a fixed ``dtstamp``,
so it round-trips in tests (ASUR-VERSION-01/HONEST-01).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone

__all__ = ["CalendarEvent", "build_calendar", "make_uid"]

_PRODID = "-//ASUR//Life Mentor + Weekly Tracker//EN"


@dataclass(frozen=True)
class CalendarEvent:
    """One all-day calendar event.

    ``start`` is the first day; ``end`` is the EXCLUSIVE last day (RFC 5545 all-day
    DTEND is exclusive) - leave it ``None`` for a single-day event. ``rrule`` is a
    bare recurrence rule body such as ``"FREQ=DAILY"`` (no ``RRULE:`` prefix).
    """

    uid: str
    summary: str
    start: date
    end: date | None = None
    description: str | None = None
    rrule: str | None = None


def make_uid(*parts: str) -> str:
    """A stable, content-derived UID (so re-exporting the same item is idempotent).

    Deterministic: the same parts always produce the same UID, so importing an
    updated file updates the same calendar entry instead of duplicating it.
    """
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{digest}@asur.local"


def _escape(text: str) -> str:
    # RFC 5545 s3.3.11: escape backslash, semicolon, comma, and newlines.
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    # RFC 5545 s3.1: fold lines longer than 75 octets; continuations start with a
    # single space. We fold on octet boundaries of the UTF-8 encoding.
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    chunks = [raw[0:75]]
    rest = raw[75:]
    while rest:
        chunks.append(rest[:74])
        rest = rest[74:]
    return "\r\n ".join(chunk.decode("utf-8", "ignore") for chunk in chunks)


def _date(day: date) -> str:
    return day.strftime("%Y%m%d")


def build_calendar(
    events: list[CalendarEvent],
    *,
    cal_name: str,
    dtstamp: datetime | None = None,
) -> str:
    """Render *events* as a single RFC 5545 VCALENDAR string (CRLF line endings).

    ``dtstamp`` stamps every VEVENT's DTSTAMP; pass a fixed value for a
    reproducible file (the default is the current UTC time). No network, no files
    written here - the caller decides where (if anywhere) the text goes.
    """
    stamp = (dtstamp or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stamp_text = stamp.strftime("%Y%m%dT%H%M%SZ")

    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{_PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        _fold(f"X-WR-CALNAME:{_escape(cal_name)}"),
    ]
    for ev in events:
        lines.append("BEGIN:VEVENT")
        lines.append(_fold(f"UID:{ev.uid}"))
        lines.append(f"DTSTAMP:{stamp_text}")
        lines.append(f"DTSTART;VALUE=DATE:{_date(ev.start)}")
        if ev.end is not None:
            lines.append(f"DTEND;VALUE=DATE:{_date(ev.end)}")
        lines.append(_fold(f"SUMMARY:{_escape(ev.summary)}"))
        if ev.description:
            lines.append(_fold(f"DESCRIPTION:{_escape(ev.description)}"))
        if ev.rrule:
            lines.append(f"RRULE:{ev.rrule}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
