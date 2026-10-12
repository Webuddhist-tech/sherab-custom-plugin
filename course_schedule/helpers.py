"""
Helpers shared by the Studio (views_cms.py) and learner (views_lms.py) APIs.
"""

from django.conf import settings
from xmodule.course_metadata_utils import DEFAULT_START_DATE

from .models import CourseScheduleSettings, default_timezone, timezone_names
from .services import SessionTimes, timezone_abbr

TIME_FORMAT = "%H:%M"


def feature_enabled():
    return bool(getattr(settings, "COURSE_SCHEDULE_ENABLED", True))


def course_date(value):
    """
    A course or section date, or None when it is still Open edX's placeholder.

    An unset start date is stored as 2030-01-01 (DEFAULT_START_DATE; Studio
    shows it as "Unscheduled"). Treating it as a real date would flag every
    session as "before the course starts" or tell learners their content is
    available from 1 January 2030.
    """
    if not value or value == DEFAULT_START_DATE:
        return None
    return value


def normalize_usage_key(usage_key):
    """
    Strip branch and version info so keys from Studio and from the LMS compare equal.
    """
    if hasattr(usage_key, "for_branch"):
        usage_key = usage_key.for_branch(None)
    if hasattr(usage_key, "version_agnostic"):
        usage_key = usage_key.version_agnostic()
    return usage_key


def course_timezone_name(course_key):
    """The course's timezone name; the default if unset or no longer a known timezone."""
    row = CourseScheduleSettings.objects.filter(course_id=course_key).first()
    if row and row.timezone in timezone_names():
        return row.timezone
    return default_timezone()


def session_times(schedule):
    return SessionTimes(schedule.start_date, schedule.num_days, schedule.start_time, schedule.end_time)


def format_time(value):
    return value.strftime(TIME_FORMAT) if value else None


def serialize_schedule(schedule, tz):
    return {
        "start_date": schedule.start_date.isoformat(),
        "end_date": schedule.end_date.isoformat(),
        "num_days": schedule.num_days,
        "start_time": format_time(schedule.start_time),
        "end_time": format_time(schedule.end_time),
        "timezone_abbr": timezone_abbr(schedule.start_date, schedule.start_time, tz),
        "instructor": schedule.instructor,
        "tools_required": schedule.tools_required,
        "notes": schedule.notes,
    }
