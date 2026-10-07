"""
Tests for the donation card and donation click API endpoints.
"""

from datetime import timedelta
from unittest import mock

from common.djangoapps.student.tests.factories import CourseEnrollmentFactory, UserFactory
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory
from organizations.models import Organization, OrganizationCourse
from rest_framework.test import APIClient

from course_partnerships.models import DonationClick, PartnerOrganizationMapping
from course_partnerships.views import DonationClickThrottle

from .utils import DONATION_URL, assign_partner, make_partner


class DonationAPITestCase(TestCase):
    """
    An enrolled learner in a course whose school has the donation card on.
    """

    def setUp(self):
        super().setUp()
        # The click throttle counts in the cache; start every test from zero.
        cache.clear()
        self.partner = make_partner(
            donation_heading="Support our monastery",
            donation_message="<p>Your donation helps us offer these teachings <b>freely to all</b>.</p>",
            donation_button_label="Donate now",
        )
        self.course = CourseOverviewFactory()
        assign_partner(self.course, self.partner)
        self.user = UserFactory()
        CourseEnrollmentFactory(user=self.user, course_id=self.course.id)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def card_url(self, course_id=None):
        return reverse("course_partnerships:course-donation", kwargs={"course_id": str(course_id or self.course.id)})

    def click_url(self, course_id=None):
        return reverse(
            "course_partnerships:course-donation-click", kwargs={"course_id": str(course_id or self.course.id)}
        )


class DonationCardAPIViewTest(DonationAPITestCase):
    """
    Tests for GET /api/courses/<course_id>/donation/
    """

    def test_enrolled_learner_gets_card(self):
        response = self.client.get(self.card_url())

        assert response.status_code == 200
        assert response.data == {
            "enabled": True,
            "show_heading": True,
            "heading": "Support our monastery",
            "message_html": "<p>Your donation helps us offer these teachings <b>freely to all</b>.</p>",
            "button_label": "Donate now",
            "url": DONATION_URL,
            "partner_name": "Sera Jey Monastery",
        }

    def test_blank_texts_are_returned_empty_for_client_defaults(self):
        self.partner.donation_heading = ""
        self.partner.donation_message = None
        self.partner.donation_button_label = ""
        self.partner.save()

        data = self.client.get(self.card_url()).data

        assert data["enabled"] is True
        assert data["heading"] == ""
        assert data["message_html"] is None
        assert data["button_label"] == ""

    def test_heading_turned_off(self):
        self.partner.donation_show_heading = False
        self.partner.save()

        data = self.client.get(self.card_url()).data

        assert data["enabled"] is True
        assert data["show_heading"] is False
        # Kept, so turning the heading back on restores it.
        assert data["heading"] == "Support our monastery"

    def test_message_is_sanitized(self):
        self.partner.donation_message = '<p>Give</p><script>alert("x")</script><a href="javascript:alert(1)">x</a>'
        self.partner.save()

        message_html = self.client.get(self.card_url()).data["message_html"]

        assert "<p>Give</p>" in message_html
        assert "<script" not in message_html
        assert "javascript:" not in message_html

    def test_not_enrolled(self):
        self.client.force_authenticate(UserFactory())

        assert self.client.get(self.card_url()).data == {"enabled": False}

    def test_inactive_enrollment(self):
        user = UserFactory()
        CourseEnrollmentFactory(user=user, course_id=self.course.id, is_active=False)
        self.client.force_authenticate(user)

        assert self.client.get(self.card_url()).data == {"enabled": False}

    def test_school_turned_card_off(self):
        self.partner.donation_enabled = False
        self.partner.save()

        assert self.client.get(self.card_url()).data == {"enabled": False}

    def test_course_excluded(self):
        self.partner.donation_excluded_courses.add(self.course)

        assert self.client.get(self.card_url()).data == {"enabled": False}

    def test_course_ended(self):
        self.course.end = timezone.now() - timedelta(days=1)
        self.course.save()

        assert self.client.get(self.card_url()).data == {"enabled": False}

    def test_course_ending_later(self):
        self.course.end = timezone.now() + timedelta(days=30)
        self.course.save()

        assert self.client.get(self.card_url()).data["enabled"] is True

    def test_course_without_school(self):
        course = CourseOverviewFactory()
        CourseEnrollmentFactory(user=self.user, course_id=course.id)

        assert self.client.get(self.card_url(course.id)).data == {"enabled": False}

    def test_inactive_organization_link_is_ignored(self):
        course = CourseOverviewFactory(org="SeraJey")
        organization = Organization.objects.create(name="Sera Jey", short_name="SeraJey")
        OrganizationCourse.objects.create(organization=organization, course_id=str(course.id), active=False)
        PartnerOrganizationMapping.objects.create(partner=self.partner, organization=organization)
        CourseEnrollmentFactory(user=self.user, course_id=course.id)

        assert self.client.get(self.card_url(course.id)).data == {"enabled": False}

    def test_school_found_through_organization_mapping(self):
        # No EnhancedCourse.partner: the course was published before its
        # organization was mapped to the school.
        course = CourseOverviewFactory(org="SeraJey")
        organization = Organization.objects.create(name="Sera Jey", short_name="SeraJey")
        OrganizationCourse.objects.create(organization=organization, course_id=str(course.id))
        PartnerOrganizationMapping.objects.create(partner=self.partner, organization=organization)
        CourseEnrollmentFactory(user=self.user, course_id=course.id)

        assert self.client.get(self.card_url(course.id)).data["partner_name"] == "Sera Jey Monastery"

    def test_signed_out(self):
        self.client.force_authenticate(None)

        assert self.client.get(self.card_url()).status_code == 401

    def test_invalid_course_id(self):
        assert self.client.get(self.card_url("not-a-course")).status_code == 400

    def test_unknown_course(self):
        assert self.client.get(self.card_url("course-v1:Nobody+Nothing+Never")).status_code == 404


class DonationClickAPIViewTest(DonationAPITestCase):
    """
    Tests for POST /api/courses/<course_id>/donation/click/
    """

    def test_click_is_recorded(self):
        response = self.client.post(self.click_url())

        assert response.status_code == 201
        click = DonationClick.objects.get()
        assert click.partner == self.partner
        assert click.course_id == self.course.id
        assert click.user == self.user

    def test_every_click_is_recorded(self):
        self.client.post(self.click_url())
        self.client.post(self.click_url())

        assert DonationClick.objects.count() == 2

    def test_no_card_no_click(self):
        self.partner.donation_excluded_courses.add(self.course)

        response = self.client.post(self.click_url())

        assert response.status_code == 404
        assert not DonationClick.objects.exists()

    def test_not_enrolled(self):
        self.client.force_authenticate(UserFactory())

        assert self.client.post(self.click_url()).status_code == 404
        assert not DonationClick.objects.exists()

    def test_signed_out(self):
        self.client.force_authenticate(None)

        assert self.client.post(self.click_url()).status_code == 401
        assert not DonationClick.objects.exists()

    # The LMS test settings use a cache that stores nothing; the throttle needs a real one.
    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_clicks_are_rate_limited(self):
        with mock.patch.object(DonationClickThrottle, "rate", "2/minute"):
            statuses = [self.client.post(self.click_url()).status_code for _ in range(3)]

        assert statuses == [201, 201, 429]
        assert DonationClick.objects.count() == 2

    def test_get_not_allowed(self):
        assert self.client.get(self.click_url()).status_code == 405
