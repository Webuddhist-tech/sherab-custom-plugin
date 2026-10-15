"""
Production Pluggable Django App settings for course_schedule.
"""


def plugin_settings(settings):
    """
    Injects production settings into the Django settings object.

    Both values can be overridden from Tutor via the ``configuration_plugin``
    LMS/CMS settings patches; this only makes sure the attributes exist.
    """
    if not hasattr(settings, "COURSE_SCHEDULE_ENABLED"):
        settings.COURSE_SCHEDULE_ENABLED = True
    if not hasattr(settings, "COURSE_SCHEDULE_DEFAULT_TIMEZONE"):
        settings.COURSE_SCHEDULE_DEFAULT_TIMEZONE = "Asia/Kolkata"
