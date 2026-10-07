"""
Tests for working out which school (Partner) owns a course.
"""

from django.test import TestCase
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory
from organizations.models import Organization, OrganizationCourse

from course_partnerships.helpers import get_course_partner, get_organization_partner_ids, get_partner_course_keys
from course_partnerships.models import EnhancedCourse, PartnerOrganizationMapping
from course_partnerships.signals.handlers import course_publish_signal_handler

from .utils import assign_partner, make_partner


class CoursePartnerTest(TestCase):
    """
    Tests for get_course_partner() and the organization fallback it shares
    with the admin, the publish handler and assign_course_partners.
    """

    def setUp(self):
        super().setUp()
        self.palpung = make_partner(name="Palpung", slug="palpung")
        self.drepung = make_partner(name="Drepung", slug="drepung")
        self.palpung_org = self.make_org("PalpungFrance")
        self.drepung_org = self.make_org("Drepung")
        PartnerOrganizationMapping.objects.create(partner=self.palpung, organization=self.palpung_org)
        PartnerOrganizationMapping.objects.create(partner=self.drepung, organization=self.drepung_org)

    @staticmethod
    def make_org(short_name):
        return Organization.objects.create(name=short_name, short_name=short_name)

    @staticmethod
    def link(course, organization, active=True):
        return OrganizationCourse.objects.create(organization=organization, course_id=str(course.id), active=active)

    def test_own_partner_wins(self):
        course = CourseOverviewFactory()
        assign_partner(course, self.drepung)
        self.link(course, self.palpung_org)

        assert get_course_partner(course.id) == self.drepung

    def test_organization_fallback(self):
        course = CourseOverviewFactory()
        self.link(course, self.palpung_org)

        assert get_course_partner(course.id) == self.palpung

    def test_first_linked_organization_wins(self):
        course = CourseOverviewFactory()
        self.link(course, self.drepung_org)
        self.link(course, self.palpung_org)

        assert get_course_partner(course.id) == self.drepung

    def test_unmapped_organization_is_skipped(self):
        course = CourseOverviewFactory()
        self.link(course, self.make_org("Unmapped"))
        self.link(course, self.palpung_org)

        assert get_course_partner(course.id) == self.palpung

    def test_inactive_link_is_skipped(self):
        course = CourseOverviewFactory()
        self.link(course, self.drepung_org, active=False)
        self.link(course, self.palpung_org)

        assert get_course_partner(course.id) == self.palpung

    def test_earliest_mapping_wins_for_shared_organization(self):
        PartnerOrganizationMapping.objects.create(partner=self.drepung, organization=self.palpung_org)
        course = CourseOverviewFactory()
        self.link(course, self.palpung_org)

        assert get_organization_partner_ids([course.id]) == {str(course.id): self.palpung.id}

    def test_no_school(self):
        assert get_course_partner(CourseOverviewFactory().id) is None

    def test_partner_course_keys_match_get_course_partner(self):
        own = CourseOverviewFactory()
        assign_partner(own, self.palpung)
        through_org = CourseOverviewFactory()
        self.link(through_org, self.palpung_org)
        # Linked to both schools' organizations, but owned by Drepung (linked first).
        shared = CourseOverviewFactory()
        self.link(shared, self.drepung_org)
        self.link(shared, self.palpung_org)
        # Linked to Palpung's organization, but has its own school.
        claimed = CourseOverviewFactory()
        assign_partner(claimed, self.drepung)
        self.link(claimed, self.palpung_org)
        inactive = CourseOverviewFactory()
        self.link(inactive, self.palpung_org, active=False)

        palpung_keys = set(get_partner_course_keys(self.palpung))

        assert palpung_keys == {own.id, through_org.id}
        assert shared.id in get_partner_course_keys(self.drepung)
        for course in (own, through_org, shared, claimed, inactive):
            assert (course.id in palpung_keys) == (get_course_partner(course.id) == self.palpung)

    def test_publish_handler_assigns_school_through_organization(self):
        course = CourseOverviewFactory()
        self.link(course, self.drepung_org, active=False)
        self.link(course, self.palpung_org)

        course_publish_signal_handler(sender=None, course_key=course.id)

        assert EnhancedCourse.objects.get(course_id=course.id).partner == self.palpung
