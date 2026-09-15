"""
Wishlist views.

JSON API (mounted under the app namespace, see urls.py):
    GET     api/wishlist/           -> list the caller's wishlisted courses
    POST    api/wishlist/           -> add a course to the wishlist
    DELETE  api/wishlist/<course_id>/  -> remove a course from the wishlist
    GET     api/wishlist/status/    -> check which of a set of courses are wishlisted

Auth: JWT (sent by the catalog MFE) or session. Every endpoint requires an
authenticated user -- there is no such thing as an anonymous wishlist.

WishListChangeView and wishlist_view below predate this API and are kept
as-is for backward compatibility with the existing LMS nav link; new
frontend work should use the JSON endpoints above instead.
"""

import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.utils.translation import gettext as _
from django.views.generic import View
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.djangoapps.edxmako.shortcuts import render_to_response
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

from .helpers import get_course_or_error
from .models import Wishlist
from .serializers import WishlistItemSerializer

log = logging.getLogger(__name__)

AUTHENTICATION_CLASSES = (JwtAuthentication, SessionAuthentication)

# Caps how many course keys one status check can carry, so a caller can't
# force an unbounded IN(...) query.
MAX_STATUS_COURSE_IDS = 100


class WishlistListCreateView(APIView):
    """List the caller's wishlisted courses, or add one."""

    authentication_classes = AUTHENTICATION_CLASSES
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        wishlist_items = (
            Wishlist.objects.filter(user=request.user)
            .select_related("course")
            .order_by("-created")
        )
        serializer = WishlistItemSerializer(wishlist_items, many=True)
        return Response(serializer.data)

    def post(self, request):
        course, error = get_course_or_error(request.data.get("course_id"))
        if error:
            return error

        _wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, course=course)
        return Response(
            {"course_id": str(course.id), "wishlisted": True, "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class WishlistDetailView(APIView):
    """Remove one course from the caller's wishlist."""

    authentication_classes = AUTHENTICATION_CLASSES
    permission_classes = (IsAuthenticated,)

    def delete(self, request, course_id):
        course, error = get_course_or_error(course_id)
        if error:
            return error

        deleted_count, _unused = Wishlist.objects.filter(user=request.user, course=course).delete()
        if not deleted_count:
            return Response({"error": _("Course is not in your wishlist.")}, status=status.HTTP_404_NOT_FOUND)

        return Response(status=status.HTTP_204_NO_CONTENT)


class WishlistStatusView(APIView):
    """Bulk-check which of a set of courses are on the caller's wishlist."""

    authentication_classes = AUTHENTICATION_CLASSES
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        course_ids = [
            course_id.strip()
            for course_id in request.query_params.get("course_ids", "").split(",")
            if course_id.strip()
        ]

        if not course_ids:
            return Response({"error": _("course_ids is required.")}, status=status.HTTP_400_BAD_REQUEST)

        if len(course_ids) > MAX_STATUS_COURSE_IDS:
            return Response(
                {"error": _("Too many course_ids (max {max_ids}).").format(max_ids=MAX_STATUS_COURSE_IDS)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Parsed directly rather than through get_course_or_error: a status
        # check only needs each course_id's key shape, not its CourseOverview
        # (a Wishlist row can only ever reference a real course), so this
        # avoids a CourseOverview/modulestore lookup per course_id.
        course_keys_by_id = {}
        for course_id in course_ids:
            try:
                course_keys_by_id[course_id] = CourseKey.from_string(course_id)
            except InvalidKeyError:
                # An unresolvable course_id just can't be wishlisted, so it's
                # reported as False rather than failing the whole batch --
                # unlike add/remove, a status check has no side effect worth
                # guarding.
                continue

        wishlisted = set(
            Wishlist.objects.filter(
                user=request.user, course_id__in=course_keys_by_id.values()
            ).values_list("course_id", flat=True)
        )

        return Response({
            course_id: course_keys_by_id.get(course_id) in wishlisted
            for course_id in course_ids
        })


class WishListChangeView(View):
    """
    Legacy add/remove endpoint. Kept for backward compatibility -- prefer
    WishlistListCreateView / WishlistDetailView for new work, which return
    JSON instead of a plain-text sentence.
    """

    def post(self, request):
        # Get the user
        user = request.user

        # Ensure the user is authenticated
        if not user.is_authenticated:
            return HttpResponseForbidden()

        action = request.POST.get("wishlist_action")
        if action not in ("add", "remove"):
            return HttpResponseBadRequest(_("Invalid wishlist_action."))

        if "course_id" not in request.POST:
            return HttpResponseBadRequest(_("Course id not specified"))

        try:
            course_key = CourseKey.from_string(request.POST.get("course_id"))
            course = CourseOverview.get_from_id(course_key)
        except Exception:
            log.warning(
                "User %s tried to %s with invalid course id: %s",
                user.username,
                action,
                request.POST.get("course_id"),
            )
            return HttpResponseBadRequest(_("Invalid course id"))

        if action == "add":
            wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, course=course)

            if created:
                response_msg = _("Course {} added to your wishlist.".format(course.display_name))
            else:
                response_msg = _("Course {} is already in your wishlist.".format(course.display_name))
        else:
            Wishlist.objects.filter(user=request.user, course=course).delete()
            response_msg = _("Course {} removed from your wishlist.".format(course.display_name))

        return HttpResponse(response_msg)


@login_required
def wishlist_view(request):
    # Fetch all wishlisted courses for the logged-in user
    wishlisted_courses = Wishlist.objects.filter(user=request.user).select_related("course")

    context = {
        "wishlisted_courses": wishlisted_courses,
    }

    return render_to_response("wishlist/wishlist.html", context)
