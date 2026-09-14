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

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview


def get_course_key_or_error(course_id):
    """
    Parse a course key string, without resolving it to a CourseOverview.

    Split out from get_course_or_error below for callers that only need to
    validate the key's shape (e.g. to use it as a filter value) and would
    otherwise pay for a CourseOverview lookup they don't need on the common
    path.

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
    course_key, error = get_course_key_or_error(course_id)
    if error:
        return None, error

    try:
        course = CourseOverview.get_from_id(course_key)
    except CourseOverview.DoesNotExist:
        return None, Response(
            {"error": _("Course not found: {course_id}").format(course_id=course_id)},
            status=status.HTTP_404_NOT_FOUND,
        )
    except IOError:
        # get_from_id also raises this if the course can't be loaded from the
        # modulestore (e.g. a stale or broken CourseOverview row) — from a
        # caller's perspective that's indistinguishable from not existing.
        return None, Response(
            {"error": _("Course not found: {course_id}").format(course_id=course_id)},
            status=status.HTTP_404_NOT_FOUND,
        )

    return course, None
