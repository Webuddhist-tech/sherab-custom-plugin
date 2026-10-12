"""
Pure scheduling logic: warnings, release notes and ordering.

Nothing here touches the modulestore, the database or edx-platform, so it can
be unit-tested on its own. The views gather course data into the small
dataclasses below and call these functions.

Auto-filling and shifting dates is done by the authoring MFE
(``src/course-schedule/utils.ts``) so the creator can preview it; the result
is saved through the Studio API like any other edit.

All dates and times are wall-clock values in the course timezone. Datetimes
from the course (release dates, due dates, course start/end) are timezone-aware
and are compared after attaching the course timezone to the session's
wall-clock values.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional


@dataclass
class SessionTimes:
    """The scheduling part of one section's schedule."""

    start_date: date
    num_days: int = 1
    start_time: Optional[time] = None
    end_time: Optional[time] = None

    @property
    def end_date(self):
        return self.start_date + timedelta(days=self.num_days - 1)

    @property
    def ends_next_day(self):
        """True for a session that runs past midnight, e.g. 22:00-00:30."""
        return bool(self.start_time and self.end_time and self.end_time < self.start_time)

    def start_datetime(self, tz):
        """When the session starts; the start of its first day if it has no start time."""
        return datetime.combine(self.start_date, self.start_time or time.min, tzinfo=tz)

    def end_datetime(self, tz):
        """When the session ends; the end of its last day if it has no end time."""
        end_date = self.end_date + timedelta(days=1) if self.ends_next_day else self.end_date
        return datetime.combine(end_date, self.end_time or time.max, tzinfo=tz)

    def starts_before(self, moment, tz):
        """
        Whether the session starts before ``moment`` (an aware datetime).

        Without a start time only the session's date is known, so it's compared
        by calendar day in the course timezone: a session on Oct 12 doesn't
        "start before" a course that opens at 05:30 on Oct 12.
        """
        if self.start_time:
            return self.start_datetime(tz) < moment
        return self.start_date < moment.astimezone(tz).date()

    def starts_after(self, moment, tz):
        """Whether the session starts after ``moment``; by calendar day if it has no start time."""
        if self.start_time:
            return self.start_datetime(tz) > moment
        return self.start_date > moment.astimezone(tz).date()

    def ends_after(self, moment, tz):
        """Whether the session ends after ``moment``; by calendar day if it has no end time."""
        if self.end_time:
            return self.end_datetime(tz) > moment
        return self.end_date > moment.astimezone(tz).date()


@dataclass
class SubsectionInfo:
    display_name: str
    due: Optional[datetime] = None


@dataclass
class SectionInfo:
    """What the warnings need to know about one section of the course."""

    section_id: str
    display_name: str
    release_date: Optional[datetime] = None
    subsections: List[SubsectionInfo] = field(default_factory=list)


@dataclass
class CourseInfo:
    start: Optional[datetime] = None
    end: Optional[datetime] = None


# --------------------------------------------------------------------------- #
# Warnings
# --------------------------------------------------------------------------- #
OVERLAP = "overlap"
BEFORE_COURSE_START = "before_course_start"
AFTER_COURSE_END = "after_course_end"
BEFORE_RELEASE = "before_release"
DUE_BEFORE_SESSION = "due_before_session"


def _warning(code, **params):
    return {"code": code, "params": params}


def content_available_from(session, release_date, tz):
    """
    The release date to show next to a session, or None.

    A session scheduled before its content is released still happens; the
    learner just can't open the content yet, so they are told when they can.
    """
    if release_date and session.starts_before(release_date, tz):
        return release_date.astimezone(tz).date()
    return None


def compute_warnings(course, ordered_sections, schedules, tz):
    """
    Return ``{section_id: [warning, ...]}`` for every scheduled section.

    Warnings never block saving; Studio shows them so the creator can decide.
    Each warning is ``{"code": ..., "params": {...}}`` and the MFE turns it
    into a translated message. Dates in params are ISO strings in the course
    timezone.
    """
    warnings = {}
    scheduled = [s for s in ordered_sections if s.section_id in schedules]

    for section in scheduled:
        session = schedules[section.section_id]
        start = session.start_datetime(tz)
        end = session.end_datetime(tz)
        items = []

        for other in scheduled:
            if other.section_id == section.section_id:
                continue
            other_session = schedules[other.section_id]
            if start < other_session.end_datetime(tz) and other_session.start_datetime(tz) < end:
                items.append(_warning(OVERLAP, section_id=other.section_id, display_name=other.display_name))

        if course.start and session.starts_before(course.start, tz):
            items.append(_warning(BEFORE_COURSE_START, date=course.start.astimezone(tz).date().isoformat()))
        if course.end and session.ends_after(course.end, tz):
            items.append(_warning(AFTER_COURSE_END, date=course.end.astimezone(tz).date().isoformat()))

        available = content_available_from(session, section.release_date, tz)
        if available:
            items.append(_warning(BEFORE_RELEASE, date=available.isoformat()))

        for subsection in section.subsections:
            if subsection.due and session.starts_after(subsection.due, tz):
                items.append(
                    _warning(
                        DUE_BEFORE_SESSION,
                        display_name=subsection.display_name,
                        date=subsection.due.astimezone(tz).date().isoformat(),
                    )
                )

        warnings[section.section_id] = items
    return warnings


def timezone_abbr(session_date, session_time, tz):
    """Short timezone name for a session, e.g. "IST"; DST-aware for the session's date."""
    return datetime.combine(session_date, session_time or time(12), tzinfo=tz).tzname()


def order_sessions(sessions_by_section: Dict[str, SessionTimes], ordered_section_ids):
    """Section ids sorted by date, then start time, then position in the outline."""
    position = {sid: index for index, sid in enumerate(ordered_section_ids)}
    return sorted(
        sessions_by_section,
        key=lambda sid: (
            sessions_by_section[sid].start_date,
            sessions_by_section[sid].start_time or time.min,
            position.get(sid, len(position)),
        ),
    )
