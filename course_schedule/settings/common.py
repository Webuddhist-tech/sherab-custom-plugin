"""
Common Pluggable Django App settings for course_schedule.
"""


def plugin_settings(settings):
    """
    Injects Course Schedule settings into the Django settings object.
    """
    # Master on/off switch. When False, the Studio controls are hidden and the
    # learner API reports the schedule as disabled.
    settings.COURSE_SCHEDULE_ENABLED = getattr(settings, "COURSE_SCHEDULE_ENABLED", True)

    # IANA timezone a course's schedule uses until its creator picks another.
    settings.COURSE_SCHEDULE_DEFAULT_TIMEZONE = getattr(
        settings, "COURSE_SCHEDULE_DEFAULT_TIMEZONE", "Asia/Kolkata"
    )
