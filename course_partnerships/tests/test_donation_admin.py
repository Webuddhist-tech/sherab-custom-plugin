"""
Tests for the donation settings and donation click report in Django admin.
"""

import csv
import io

from common.djangoapps.student.tests.factories import TEST_PASSWORD, UserFactory
from django.contrib.admin import site
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.test import RequestFactory, TestCase
from django.urls import reverse
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory
from organizations.models import Organization, OrganizationCourse

from course_partnerships.admin import DonationClickAdmin, PartnerAdmin
from course_partnerships.models import DonationClick, Partner, PartnerOrganizationMapping

from .utils import assign_partner, make_partner

CHANGELIST_URL = "admin:course_partnerships_donationclick_changelist"


class DonationClickReportTest(TestCase):
    """
    Tests for the donation click report.
    """

    def setUp(self):
        super().setUp()
        self.partner = make_partner()
        self.other_partner = make_partner(name="Drepung", slug="drepung")
        self.course = CourseOverviewFactory()
        self.other_course = CourseOverviewFactory()
        self.learner = UserFactory()
        self.other_learner = UserFactory()

        # Sera Jey course: 3 clicks from 2 learners. Drepung course: 1 click.
        for user in (self.learner, self.learner, self.other_learner):
            DonationClick.objects.create(partner=self.partner, course_id=self.course.id, user=user)
        DonationClick.objects.create(partner=self.other_partner, course_id=self.other_course.id, user=self.learner)

        self.admin_user = UserFactory(is_staff=True, is_superuser=True)
        self.login(self.admin_user)

    def login(self, user):
        # force_login's session cookie is rejected by the LMS safe-sessions middleware.
        assert self.client.login(username=user.username, password=TEST_PASSWORD)

    def test_summary(self):
        summary = list(DonationClickAdmin.summarize(DonationClick.objects.all()))

        assert summary == [
            {
                "partner__name": "Drepung",
                "course_id": self.other_course.id,
                "total_clicks": 1,
                "unique_learners": 1,
            },
            {
                "partner__name": "Sera Jey Monastery",
                "course_id": self.course.id,
                "total_clicks": 3,
                "unique_learners": 2,
            },
        ]

    def test_report_page_shows_filtered_summary(self):
        response = self.client.get(reverse(CHANGELIST_URL), {"partner__id__exact": self.partner.id})

        assert response.status_code == 200
        summary = list(response.context_data["donation_summary"])
        assert len(summary) == 1
        assert summary[0]["total_clicks"] == 3
        assert summary[0]["unique_learners"] == 2
        self.assertContains(response, "Unique learners")

    def test_report_is_read_only(self):
        assert self.client.get(reverse("admin:course_partnerships_donationclick_add")).status_code == 403
        click = DonationClick.objects.first()
        delete_url = reverse("admin:course_partnerships_donationclick_delete", args=[click.id])
        assert self.client.post(delete_url, {"post": "yes"}).status_code == 403
        assert DonationClick.objects.count() == 4

    def test_report_staff_only(self):
        self.login(UserFactory())

        response = self.client.get(reverse(CHANGELIST_URL))

        assert response.status_code == 302
        assert "login" in response["Location"]

    def run_action(self, action):
        response = self.client.post(
            reverse(CHANGELIST_URL),
            {"action": action, ACTION_CHECKBOX_NAME: list(DonationClick.objects.values_list("id", flat=True))},
        )
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        return list(csv.reader(io.StringIO(response.content.decode())))

    def test_export_summary_csv(self):
        rows = self.run_action("export_summary_csv")

        assert rows == [
            ["School", "Course", "Total clicks", "Unique learners"],
            ["Drepung", str(self.other_course.id), "1", "1"],
            ["Sera Jey Monastery", str(self.course.id), "3", "2"],
        ]

    def test_export_clicks_csv(self):
        rows = self.run_action("export_clicks_csv")

        assert rows[0] == ["Clicked at", "School", "Course", "Learner"]
        assert len(rows) == 5
        assert [self.learner.username, self.learner.username, self.other_learner.username] == [
            row[3] for row in rows[1:] if row[1] == "Sera Jey Monastery"
        ]


class PartnerAdminExcludedCoursesTest(TestCase):
    """
    The excluded-courses picker lists only the school's own courses.
    """

    def test_partner_courses(self):
        partner = make_partner()
        other_partner = make_partner(name="Drepung", slug="drepung")

        own_course = CourseOverviewFactory()
        assign_partner(own_course, partner)

        # Belongs to the school through its organization mapping only.
        org_course = CourseOverviewFactory(org="SeraJey")
        organization = Organization.objects.create(name="Sera Jey", short_name="SeraJey")
        OrganizationCourse.objects.create(organization=organization, course_id=str(org_course.id))
        PartnerOrganizationMapping.objects.create(partner=partner, organization=organization)

        other_course = CourseOverviewFactory()
        assign_partner(other_course, other_partner)
        CourseOverviewFactory()  # No school at all.

        courses = set(PartnerAdmin.partner_courses(partner))

        assert courses == {own_course, org_course}

    def test_unsaved_partner_has_no_courses(self):
        CourseOverviewFactory()

        assert not PartnerAdmin.partner_courses(None).exists()

    def test_already_excluded_course_stays_selectable(self):
        partner = make_partner()
        moved_course = CourseOverviewFactory()
        assign_partner(moved_course, make_partner(name="Drepung", slug="drepung"))
        # Excluded while it still belonged to this school.
        partner.donation_excluded_courses.add(moved_course)

        assert moved_course in PartnerAdmin.partner_courses(partner)

    def test_fieldsets_show_every_field(self):
        admin_user = UserFactory(is_staff=True, is_superuser=True)
        request = RequestFactory().get("/")
        request.user = admin_user
        partner_admin = PartnerAdmin(Partner, site)

        shown = {field for _, options in partner_admin.get_fieldsets(request) for field in options["fields"]}

        editable = {
            field.name
            for field in Partner._meta.get_fields()
            if getattr(field, "editable", False) and not field.auto_created
        }
        assert editable <= shown
        assert "donation_enabled" in dict(partner_admin.get_fieldsets(request))["Donation card"]["fields"]

    def test_change_form_lists_only_own_courses(self):
        partner = make_partner()
        own_course = CourseOverviewFactory()
        assign_partner(own_course, partner)
        other_course = CourseOverviewFactory()
        admin_user = UserFactory(is_staff=True, is_superuser=True)
        assert self.client.login(username=admin_user.username, password=TEST_PASSWORD)

        response = self.client.get(reverse("admin:course_partnerships_partner_change", args=[partner.id]))

        assert response.status_code == 200
        queryset = response.context_data["adminform"].form.fields["donation_excluded_courses"].queryset
        assert set(queryset) == {own_course}
        assert other_course not in queryset
