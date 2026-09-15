"""
Helper functions for the course_partnerships API views.

Kept out of ``views.py`` so that module holds only the API views themselves,
matching the wishlist app's layout.
"""

from django.utils.translation import gettext as _
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.response import Response


def get_course_key_or_error(course_id):
    """
    Parse a course key string, without resolving it to a CourseOverview.

    Args:
        course_id (str): A course key, e.g. "course-v1:Org+Course+Run".

    Returns:
        tuple[CourseKey, None] on success, or (None, Response) carrying the
        400 response describing what was wrong with `course_id`. Callers do
        ``course_key, error = get_course_key_or_error(...); if error: return
        error``.
    """
    if not course_id:
        return None, Response({"error": _("course_id is required.")}, status=status.HTTP_400_BAD_REQUEST)

    try:
        return CourseKey.from_string(course_id), None
    except InvalidKeyError:
        return None, Response(
            {"error": _("Invalid course_id: {course_id}").format(course_id=course_id)},
            status=status.HTTP_400_BAD_REQUEST,
        )
