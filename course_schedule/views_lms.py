"""
LMS API for course section schedules, used by the learner Dates tab.

    GET  api/course-schedule/v1/<course_id>/  -> the sessions this learner can see

Returns ``enabled: false`` (and no sessions) for self-paced courses or when the
feature is turned off.
"""

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.djangoapps.student.models import CourseEnrollment
from lms.djangoapps.course_home_api.utils import get_course_or_403
from lms.djangoapps.courseware.access import has_access
from lms.djangoapps.courseware.masquerade import setup_masquerade
from openedx.core.djangoapps.content.learning_sequences.api import get_user_course_outline_details
from openedx.core.djangoapps.content.learning_sequences.data import ObjectDoesNotExist as OutlineDoesNotExist
from openedx.core.lib.api.authentication import BearerAuthenticationAllowInactiveUser

from course_partnerships.helpers import get_course_key_or_error

from .helpers import (
    course_date,
    course_timezone_name,
    feature_enabled,
    normalize_usage_key,
    serialize_schedule,
    session_times,
)
from .models import SectionSchedule
from .services import content_available_from, order_sessions

log = logging.getLogger(__name__)


class LearnerCourseScheduleView(APIView):
    """
    The section schedule a learner sees on the Dates tab.

    Access mirrors the platform's Dates tab (DatesTabView): enrolled learners
    and course staff, with staff masquerade supported. A session is listed
    only if its section appears in the learner's own course outline, so
    staff-only, hidden and content-group-restricted sections never leak.
    Sessions are returned in the course timezone, sorted by date and time.
    """

    # Same as DatesTabView; Bearer is what the mobile apps send.
    authentication_classes = (
        JwtAuthentication,
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (IsAuthenticated,)

    def get(self, request, course_id):
        course_key, error = get_course_key_or_error(course_id)
        if error:
            return error

        # Learners check the schedule before the course starts, so allow that.
        course = get_course_or_403(
            request.user, "load", course_key, check_if_enrolled=False, allow_not_started_courses=True
        )
        is_staff = bool(has_access(request.user, "staff", course_key))
        _masquerade, request.user = setup_masquerade(
            request, course_key, staff_access=is_staff, reset_masquerade_data=True
        )
        if not CourseEnrollment.is_enrolled(request.user, course_key) and not is_staff:
            return Response("User not enrolled.", status=status.HTTP_401_UNAUTHORIZED)

        tz_name = course_timezone_name(course_key)
        disabled = {"enabled": False, "timezone": tz_name, "sessions": []}
        if not feature_enabled() or course.self_paced:
            return Response(disabled)

        try:
            details = get_user_course_outline_details(course_key, request.user, datetime.now(timezone.utc))
        except OutlineDoesNotExist:
            # The outline is built when the course is first published.
            log.warning("No learning_sequences outline for %s; returning no sessions.", course_key)
            return Response({"enabled": True, "timezone": tz_name, "sessions": []})
        visible_sections = [
            section for section in details.outline.sections if not section.visibility.hide_from_toc
        ]
        titles = {str(normalize_usage_key(section.usage_key)): section.title for section in visible_sections}
        # course_date() drops the 2030-01-01 placeholder of an unset ("Unscheduled") release date.
        release_dates = {
            str(normalize_usage_key(key)): course_date(item.effective_start or item.start)
            for key, item in details.schedule.sections.items()
        }

        rows = {
            str(normalize_usage_key(row.section_id)): row
            for row in SectionSchedule.objects.filter(course_id=course_key)
        }
        rows = {section_id: row for section_id, row in rows.items() if section_id in titles}

        tz = ZoneInfo(tz_name)
        sessions = []
        for section_id in order_sessions({sid: session_times(row) for sid, row in rows.items()}, list(titles)):
            row = rows[section_id]
            available = content_available_from(session_times(row), release_dates.get(section_id), tz)
            sessions.append(
                {
                    "section_id": section_id,
                    "title": titles[section_id],
                    **serialize_schedule(row, tz),
                    "content_available_from": available.isoformat() if available else None,
                }
            )

        return Response({"enabled": True, "timezone": tz_name, "sessions": sessions})
