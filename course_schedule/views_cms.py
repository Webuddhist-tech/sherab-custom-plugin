"""
Studio (CMS) API for course section schedules, used by the course outline.

    GET  api/course-schedule/v1/studio/<course_id>/  -> every section with its schedule and warnings
    PUT  api/course-schedule/v1/studio/<course_id>/  -> save a batch of changes, returns the same as GET
    GET  api/course-schedule/v1/studio/timezones/    -> the timezone names the API accepts

Course authors only. Schedules exist only for instructor-paced courses, so a
self-paced course can be read but not changed.
"""

from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils.translation import gettext as _
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from opaque_keys.edx.keys import UsageKey
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.djangoapps.student.auth import has_course_author_access
from course_partnerships.helpers import get_course_key_or_error
from xmodule.modulestore.django import modulestore

from .helpers import (
    course_date,
    course_timezone_name,
    feature_enabled,
    normalize_usage_key,
    serialize_schedule,
    session_times,
)
from .models import CourseScheduleSettings, SectionSchedule, timezone_names
from .serializers import CourseScheduleUpdateSerializer
from .services import CourseInfo, SectionInfo, SubsectionInfo, compute_warnings


def load_studio_course(course_key):
    """
    Read the course and its sections, in outline order, from the modulestore.

    Returns ``(course_block, [SectionInfo])``, or ``(None, None)`` if the course
    doesn't exist. Sections and subsections are "direct only" in Open edX, so
    the draft and published structure are the same.
    """
    course = modulestore().get_course(course_key, depth=2)
    if course is None:
        return None, None

    sections = []
    for chapter in course.get_children():
        if chapter.category != "chapter":
            continue
        sections.append(
            SectionInfo(
                section_id=str(normalize_usage_key(chapter.location)),
                display_name=chapter.display_name_with_default,
                release_date=course_date(chapter.start),
                subsections=[
                    SubsectionInfo(display_name=child.display_name_with_default, due=child.due)
                    for child in chapter.get_children()
                ],
            )
        )
    return course, sections


class StudioCourseScheduleView(APIView):
    """Read and edit a course's section schedule from the Studio course outline."""

    authentication_classes = (JwtAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticated,)

    def _check_author(self, request, course_id):
        """Return ``(course_key, None)``, or ``(None, Response)`` on a bad id or missing permission."""
        course_key, error = get_course_key_or_error(course_id)
        if error:
            return None, error
        if not has_course_author_access(request.user, course_key):
            return None, Response(
                {"error": _("You do not have permission to edit this course.")},
                status=status.HTTP_403_FORBIDDEN,
            )
        return course_key, None

    def _payload(self, course_key, course, sections):
        tz_name = course_timezone_name(course_key)
        tz = ZoneInfo(tz_name)
        section_ids = {section.section_id for section in sections}
        rows = {
            str(normalize_usage_key(row.section_id)): row
            for row in SectionSchedule.objects.filter(course_id=course_key)
        }
        # Rows for deleted sections are normally removed by signals.py; skip any that slipped through.
        rows = {section_id: row for section_id, row in rows.items() if section_id in section_ids}

        course_info = CourseInfo(start=course_date(course.start), end=course.end)
        warnings = compute_warnings(
            course_info, sections, {section_id: session_times(row) for section_id, row in rows.items()}, tz
        )

        return {
            "enabled": feature_enabled(),
            "self_paced": bool(course.self_paced),
            "course": {
                "start": course_info.start.isoformat() if course_info.start else None,
                "end": course_info.end.isoformat() if course_info.end else None,
            },
            "timezone": tz_name,
            "sections": [
                {
                    "section_id": section.section_id,
                    "display_name": section.display_name,
                    "release_date": section.release_date.isoformat() if section.release_date else None,
                    "schedule": serialize_schedule(rows[section.section_id], tz)
                    if section.section_id in rows
                    else None,
                    "warnings": warnings.get(section.section_id, []),
                }
                for section in sections
            ],
            "scheduled_count": len(rows),
            "total_count": len(sections),
        }

    def get(self, request, course_id):
        course_key, error = self._check_author(request, course_id)
        if error:
            return error
        course, sections = load_studio_course(course_key)
        if course is None:
            return Response({"error": _("Course not found.")}, status=status.HTTP_404_NOT_FOUND)
        return Response(self._payload(course_key, course, sections))

    def put(self, request, course_id):
        course_key, error = self._check_author(request, course_id)
        if error:
            return error
        course, sections = load_studio_course(course_key)
        if course is None:
            return Response({"error": _("Course not found.")}, status=status.HTTP_404_NOT_FOUND)
        if not feature_enabled():
            return Response({"error": _("Course schedules are turned off.")}, status=status.HTTP_400_BAD_REQUEST)
        if course.self_paced:
            return Response(
                {"error": _("Schedules are only available for instructor-paced courses.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CourseScheduleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        section_ids = {section.section_id for section in sections}
        # Only saving an unknown section is an error. Removing one is ignored: it
        # was most likely deleted by someone else after this editor loaded, and
        # failing would throw away the rest of the batch.
        unknown = [item["section_id"] for item in data["upsert"] if item["section_id"] not in section_ids]
        if unknown:
            return Response(
                {"error": _("These sections are not part of this course."), "section_ids": unknown},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            if "timezone" in data:
                CourseScheduleSettings.objects.update_or_create(
                    course_id=course_key, defaults={"timezone": data["timezone"]}
                )
            for item in data["upsert"]:
                fields = {key: value for key, value in item.items() if key != "section_id"}
                SectionSchedule.objects.update_or_create(
                    section_id=UsageKey.from_string(item["section_id"]),
                    defaults={**fields, "course_id": course_key, "updated_by": request.user},
                )
            # One query drops the removed sections plus any rows left over from
            # deleted sections. Stored ids are already normalized (see above and signals.py).
            keep = [UsageKey.from_string(section_id) for section_id in section_ids - set(data["remove"])]
            SectionSchedule.objects.filter(course_id=course_key).exclude(section_id__in=keep).delete()

        return Response(self._payload(course_key, course, sections))


class StudioTimezonesView(APIView):
    """
    The timezone names the Studio API accepts, for the full schedule editor's select.

    Separate from the schedule itself, which every section badge loads, so the
    ~600 names are only fetched when the editor needs them.
    """

    authentication_classes = (JwtAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response({"timezones": sorted(timezone_names())})
