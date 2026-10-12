"""
Studio (CMS) URL routes for course section schedules.

Mounted at the site root (REGEX "^") via the plugin config in apps.py, so the
absolute path is ``/api/course-schedule/v1/studio/<course_id>/`` on the Studio host.
"""

from django.conf import settings
from django.urls import re_path

from .views_cms import StudioCourseScheduleView, StudioTimezonesView

app_name = "course_schedule"

urlpatterns = [
    # Before the course pattern, which would otherwise try to read "timezones" as a course id.
    re_path(r"^api/course-schedule/v1/studio/timezones/$", StudioTimezonesView.as_view(), name="studio-timezones"),
    re_path(
        rf"^api/course-schedule/v1/studio/{settings.COURSE_ID_PATTERN}/$",
        StudioCourseScheduleView.as_view(),
        name="studio-course-schedule",
    ),
]
