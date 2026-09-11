"""
Helper functions for the wishlist API views.

Kept out of ``views.py`` so that module holds only the API views themselves,
matching the ai_course_creator app's layout.
"""

from django.utils.translation import gettext as _
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.response import Response

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview


def get_course_or_error(course_id):
    """
    Resolve a course key string to its CourseOverview.

    Args:
        course_id (str): A course key, e.g. "course-v1:Org+Course+Run".

    Returns:
        tuple[CourseOverview, None] on success, or (None, Response) carrying
        the 4xx error response describing what was wrong with `course_id`.
        Callers do ``course, error = get_course_or_error(...); if error:
        return error``.
    """
    if not course_id:
        return None, Response({"error": _("course_id is required.")}, status=status.HTTP_400_BAD_REQUEST)

    try:
        course_key = CourseKey.from_string(course_id)
        course = CourseOverview.get_from_id(course_key)
    except InvalidKeyError:
        return None, Response(
            {"error": _("Invalid course_id: {course_id}").format(course_id=course_id)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except CourseOverview.DoesNotExist:
        return None, Response(
            {"error": _("Course not found: {course_id}").format(course_id=course_id)},
            status=status.HTTP_404_NOT_FOUND,
        )

    return course, None
