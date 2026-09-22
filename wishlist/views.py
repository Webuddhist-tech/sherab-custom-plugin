"""
Wishlist views.

JSON API (mounted under the app namespace, see urls.py):
    GET     api/wishlist/           -> list the caller's wishlisted courses
    POST    api/wishlist/           -> add a course to the wishlist
    DELETE  api/wishlist/<course_id>/  -> remove a course from the wishlist
    GET     api/wishlist/status/    -> check which of a set of courses are wishlisted

Auth: JWT (sent by the catalog MFE) or session. Every endpoint requires an
authenticated user -- there is no such thing as an anonymous wishlist.
"""

from django.utils.translation import gettext as _
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .helpers import get_course_or_error
from .models import Wishlist
from .serializers import WishlistItemSerializer

AUTHENTICATION_CLASSES = (JwtAuthentication, SessionAuthentication)

# Caps how many course keys one status check can carry, so a caller can't
# force an unbounded IN(...) query.
MAX_STATUS_COURSE_IDS = 100


class WishlistPagination(PageNumberPagination):
    """Show five saved courses per page, matching the learner dashboard."""

    page_size = 5


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
        paginator = WishlistPagination()
        page = paginator.paginate_queryset(wishlist_items, request, view=self)
        serializer = WishlistItemSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

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
