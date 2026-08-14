import logging

from common.djangoapps.edxmako.shortcuts import render_to_response
from django.db.models import Count, Prefetch
from django.http import Http404
from django.views.generic import View
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from xmodule.course_block import CATALOG_VISIBILITY_CATALOG_AND_ABOUT

from .models import *
from .serializers import (
    HomepageCategorySerializer,
    PartnerOrganizationMappingSerializer,
    PartnerSerializer,
)

log = logging.getLogger(__name__)


class PartnerDetailView(View):
    """
    View for Partner Details
    """

    def get(self, request, slug):
        try:
            partner = Partner.objects.get(slug=slug)
        except Exception as e:
            raise Http404

        centers = Center.objects.filter(partner=partner)
        category_ids = CourseOverview.objects.filter(enhancedcourse__partner=partner).values_list(
            "enhancedcourse__category", flat=True
        )
        categories = (
            Category.objects.filter(id__in=category_ids)
            .annotate(num_courses=Count("enhancedcourse"))
            .filter(num_courses__gt=0)
        )
        partner_courses = CourseOverview.objects.filter(enhancedcourse__partner=partner)
        course_creators = CourseCreator.objects.filter(partner=partner)
        context = {
            "partner": partner,
            "centers": centers,
            "categories": categories,
            "partner_courses": partner_courses,
            "course_creators": course_creators,
        }
        return render_to_response("course_partnerships/partner-details.html", context)


class CenterDetailView(View):
    """
    View for Center Details
    """

    def get(self, request, partner_slug, center_slug):
        try:
            partner = Partner.objects.get(slug=partner_slug)
        except Exception as e:
            raise Http404

        try:
            center = Center.objects.get(partner=partner, slug=center_slug)
        except Exception as e:
            raise Http404

        category_ids = CourseOverview.objects.filter(enhancedcourse__partner=partner).values_list(
            "enhancedcourse__category", flat=True
        )
        categories = (
            Category.objects.filter(id__in=category_ids)
            .annotate(num_courses=Count("enhancedcourse"))
            .filter(num_courses__gt=0)
        )
        context = {"partner": partner, "center": center, "categories": categories}
        return render_to_response("course_partnerships/center-details.html", context)


class PublicListAPIView(ListAPIView):
    """
    Base class for the public listing endpoints in this app.

    These endpoints are read by anonymous clients (the homepage and the mobile
    app) and each is expected to return its whole list as a bare JSON array, so
    the shared settings live here:

    - authentication is skipped entirely rather than attempted and failed;
    - anonymous access is granted explicitly, so a future change to the
      platform-wide permission default can't silently lock these down;
    - the platform-wide pagination default is disabled, which would otherwise
      cap responses at PAGE_SIZE and wrap them in a
      {count, next, previous, results} envelope that no client here expects;
    - filtering is disabled, since a subclass may return an already-evaluated
      list that a filter backend could not handle.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    pagination_class = None
    filter_backends = []


class PartnerListAPIView(PublicListAPIView):
    """
    API endpoint to retrieve partner-organization mappings.

    Each entry in the response corresponds to a unique pair of:
        - Partner (name + logo)
        - Organization (short_name)

    Only mappings marked with `show_in_mobile_app=True` are returned.

    Method:
        GET

    Example Response (200 OK):
        [
            {
                "partner_name": "Partner Name",
                "logo": "https://yourdomain.com/../partner_logo.png",
                "organization": "org1"
            },
            ...
        ]
    """

    serializer_class = PartnerOrganizationMappingSerializer
    queryset = PartnerOrganizationMapping.objects.filter(show_in_mobile_app=True)


class PartnerHomepageListAPIView(PublicListAPIView):
    """
    API endpoint to retrieve all partners, for display on the homepage
    schools-and-partners carousel. Unlike PartnerListAPIView, this is not
    filtered by `show_in_mobile_app` — it mirrors the old homepage template's
    `Partner.objects.all()` behavior, since the homepage carousel and the
    mobile app's partner list serve different purposes and audiences.

    Method:
        GET

    Example Response (200 OK):
        [
            {
                "partner_name": "Partner Name",
                "logo": "https://yourdomain.com/../partner_logo.png",
                "slug": "partner-slug"
            },
            ...
        ]
    """

    serializer_class = PartnerSerializer

    # Explicit ordering keeps the carousel stable: an unordered queryset lets
    # the database return rows in any order, which can reshuffle the logos
    # between requests.
    queryset = Partner.objects.order_by("name")


class HomepageCategoryListAPIView(PublicListAPIView):
    """
    API endpoint to retrieve the homepage course categories with their courses.

    Returns every category flagged `show_on_homepage`, each with the full list
    of courses filed under it, so the homepage can render its category tabs and
    switch between them without further requests.

    Categories left with no visible courses are omitted, so a tab never opens
    onto an empty grid.

    Method:
        GET

    Example Response (200 OK):
        [
            {
                "id": 1,
                "name": "Category Name",
                "courses": [
                    {
                        "course_id": "course-v1:Org+Course+Run",
                        "title": "Course Title",
                        "image_url": "https://yourdomain.com/../course_image.jpg",
                        "provider_name": "Provider Name",
                        "provider_logo": "https://yourdomain.com/../provider_logo.png"
                    },
                    ...
                ]
            },
            ...
        ]
    """

    serializer_class = HomepageCategorySerializer

    def get_queryset(self):
        """
        Return the homepage categories, each carrying its visible courses.

        Returns:
            list[Category]: Categories that have at least one visible course,
                each with a `visible_courses` attribute the serializer reads.
        """
        visible_courses = (
            EnhancedCourse.objects
            # select_related is a correctness guard as much as a performance
            # one: the link to CourseOverview has no database constraint, so
            # the join also discards rows pointing at courses that no longer
            # exist, which would otherwise raise when serialized.
            .select_related("course", "partner", "center")
            .filter(
                # This endpoint is public and unauthenticated, so restrict it
                # to courses that are meant to be publicly listed. The old
                # homepage template applied neither filter and would happily
                # advertise a staff-only course to anonymous visitors.
                course__visible_to_staff_only=False,
                course__catalog_visibility=CATALOG_VISIBILITY_CATALOG_AND_ABOUT,
            )
            .order_by("-course__start", "course__id")
        )

        categories = (
            Category.objects.filter(show_on_homepage=True)
            # Categories have no ordering field of their own, and an unordered
            # queryset lets the database reshuffle the tabs between requests.
            .order_by("name", "id")
            .prefetch_related(
                Prefetch("enhancedcourse_set", queryset=visible_courses, to_attr="visible_courses")
            )
        )

        # Drop empty categories here rather than with a Count annotation: the
        # count would be taken before the visibility filter above, so a
        # category holding only hidden courses would survive it and then render
        # an empty tab. The prefetched lists are already loaded, so filtering
        # in Python costs no extra queries.
        return [category for category in categories if category.visible_courses]
