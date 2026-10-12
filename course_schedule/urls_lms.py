"""
LMS URL routes for course section schedules.

Mounted at the site root (REGEX "^") via the plugin config in apps.py, so the
absolute path is ``/api/course-schedule/v1/<course_id>/`` on the LMS host.
"""

from django.conf import settings
from django.urls import re_path

from .views_lms import LearnerCourseScheduleView

app_name = "course_schedule"

urlpatterns = [
    re_path(
        rf"^api/course-schedule/v1/{settings.COURSE_ID_PATTERN}/$",
        LearnerCourseScheduleView.as_view(),
        name="learner-course-schedule",
    ),
]
