"""
Helper functions for the course_partnerships API views.

Kept out of ``views.py`` so that module holds only the API views themselves,
matching the wishlist app's layout.
"""

from common.djangoapps.student.models import CourseEnrollment
from django.utils.translation import gettext as _
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from organizations.models import OrganizationCourse
from rest_framework import status
from rest_framework.response import Response

from .models import EnhancedCourse, Partner, PartnerOrganizationMapping


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


def course_not_found(course_id):
    """
    Return the 404 response for a course that doesn't exist, or that the
    caller may not see. One response for both, so hidden courses can't be
    discovered by probing.
    """
    return Response(
        {"error": _("Course not found: {course_id}").format(course_id=course_id)},
        status=status.HTTP_404_NOT_FOUND,
    )


def get_course_overview_or_error(course_id):
    """
    Parse a course key string and load its CourseOverview.

    Returns:
        tuple[CourseOverview, None] on success, or (None, Response) with the
        400 response for a malformed key or the 404 for an unknown course.
    """
    course_key, error = get_course_key_or_error(course_id)
    if error:
        return None, error

    try:
        return CourseOverview.get_from_id(course_key), None
    except (CourseOverview.DoesNotExist, IOError):
        # IOError: a stale or broken CourseOverview row the modulestore can no
        # longer load, which to a caller is the same as no such course.
        return None, course_not_found(course_id)


def get_organization_partner_ids(course_ids):
    """
    Map courses to the school their organization belongs to.

    This is the one place that decides which school owns a course through its
    organization. A course's organizations are tried in the order they were
    linked to it, skipping deactivated links, and the first one mapped to a
    school wins; for an organization mapped to several schools, the earliest
    mapping wins.

    Args:
        course_ids (iterable of CourseKey or str): The courses to look up.

    Returns:
        dict[str, int]: Partner id by course id string, for the courses that
            resolve to a school. Courses that don't are left out.
    """
    course_ids = [str(course_id) for course_id in course_ids]
    links = list(
        OrganizationCourse.objects.filter(course_id__in=course_ids, active=True)
        .order_by("id")
        .values_list("course_id", "organization_id")
    )

    partner_by_org = {}
    mappings = (
        PartnerOrganizationMapping.objects.filter(organization_id__in={org_id for _, org_id in links})
        .order_by("id")
        .values_list("organization_id", "partner_id")
    )
    for org_id, partner_id in mappings:
        partner_by_org.setdefault(org_id, partner_id)

    partner_by_course = {}
    for course_id, org_id in links:
        if course_id not in partner_by_course and org_id in partner_by_org:
            partner_by_course[course_id] = partner_by_org[org_id]
    return partner_by_course


def get_course_partner(course_key):
    """
    Return the school (Partner) a course belongs to, or None.

    Uses the course's EnhancedCourse.partner when set. That is filled in on
    publish, but stays empty for courses published before their organization
    was mapped to a school, so fall back to the organization mapping
    (get_organization_partner_ids), without saving it.

    Args:
        course_key (CourseKey): The course to look up.

    Returns:
        Partner or None
    """
    enhanced_course = EnhancedCourse.objects.select_related("partner").filter(course_id=course_key).first()
    if enhanced_course and enhanced_course.partner:
        return enhanced_course.partner

    partner_id = get_organization_partner_ids([course_key]).get(str(course_key))
    return Partner.objects.filter(id=partner_id).first() if partner_id else None


def get_partner_course_keys(partner):
    """
    Return the keys of every course that get_course_partner() resolves to
    this school: its own courses, plus courses without a school of their own
    whose organization maps to it.

    Args:
        partner (Partner): The school.

    Returns:
        list[CourseKey]
    """
    own_keys = list(EnhancedCourse.objects.filter(partner=partner).values_list("course_id", flat=True))

    org_ids = partner.organization_mappings.values_list("organization_id", flat=True)
    candidates = {}
    for course_id in OrganizationCourse.objects.filter(organization_id__in=org_ids, active=True).values_list(
        "course_id", flat=True
    ):
        try:
            candidates[course_id] = CourseKey.from_string(course_id)
        except InvalidKeyError:
            continue
    # Courses with a school of their own belong to that school, not this one.
    for course_key in EnhancedCourse.objects.filter(
        course_id__in=list(candidates.values()), partner__isnull=False
    ).values_list("course_id", flat=True):
        candidates.pop(str(course_key), None)

    partner_by_course = get_organization_partner_ids(candidates)
    org_keys = [key for course_id, key in candidates.items() if partner_by_course.get(course_id) == partner.id]
    return own_keys + org_keys


def get_donation_partner(user, course_overview):
    """
    Return the school whose donation card this user should see on this
    course's home page, or None when no card should show.

    The card shows only when the course's school has the card turned on and
    hasn't excluded this course, the course hasn't ended, and the user is
    actively enrolled in it.

    Args:
        user (User): The requesting user.
        course_overview (CourseOverview): The course whose home page it is.

    Returns:
        Partner or None
    """
    course_key = course_overview.id
    if course_overview.has_ended():
        return None
    # An active enrollment is the gate, not catalog visibility: learners in an
    # invite-only course hidden from the catalog still get the card.
    if not CourseEnrollment.is_enrolled(user, course_key):
        return None

    partner = get_course_partner(course_key)
    if not partner or not partner.donation_enabled or not partner.donation_url:
        return None
    if partner.donation_excluded_courses.filter(id=course_key).exists():
        return None
    return partner
