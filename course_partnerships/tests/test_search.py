"""Tests for the Discover organization-label response extension."""

from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase

from course_partnerships.search import register_organization_display_names
from course_partnerships.views import OrganizationDisplayNamesView


class OrganizationDisplayNamesSearchTest(SimpleTestCase):
    """Ensure the search extension preserves raw filter values."""

    @patch("course_partnerships.search.get_organization_names")
    @patch("search.views.course_discovery_search")
    def test_adds_display_names_without_changing_aggregation_terms(self, search, get_organization_names):
        search.return_value = {
            "aggs": {
                "org": {
                    "terms": {"Khyentse_Foundation": 8},
                },
            },
        }
        get_organization_names.return_value = {
            "Khyentse_Foundation": "Khyentse Foundation",
        }

        with patch("search.views._sherab_organization_display_names_registered", False, create=True):
            register_organization_display_names()

            from search import views as search_views
            results = search_views.course_discovery_search()

        self.assertEqual(results["aggs"]["org"]["terms"], {"Khyentse_Foundation": 8})
        self.assertEqual(
            results["organization_display_names"],
            {"Khyentse_Foundation": "Khyentse Foundation"},
        )
        get_organization_names.assert_called_once_with({"Khyentse_Foundation"})

    @patch("openedx.core.djangoapps.content.course_overviews.models.CourseOverview")
    @patch("course_partnerships.search.get_organization_names")
    @patch("search.views.course_discovery_search")
    def test_adds_per_course_display_name(self, search, get_organization_names, course_overview):
        course_id = "course-v1:Khyentse_Foundation+Demo+2026"
        overridden_id = "course-v1:Khyentse_Foundation+Other+2026"
        search.return_value = {
            "aggs": {"org": {"terms": {"Khyentse_Foundation": 2}}},
            "results": [
                {"id": course_id, "data": {"org": "Khyentse_Foundation"}},
                {"id": overridden_id, "data": {"org": "Khyentse_Foundation"}},
            ],
        }
        get_organization_names.return_value = {"Khyentse_Foundation": "Khyentse Foundation"}
        named = Mock(org="Khyentse_Foundation", display_org_with_default="Khyentse_Foundation")
        named.id = course_id
        overridden = Mock(org="Khyentse_Foundation", display_org_with_default="Course Specific")
        overridden.id = overridden_id
        course_overview.objects.filter.return_value = [named, overridden]

        with patch("search.views._sherab_organization_display_names_registered", False, create=True):
            register_organization_display_names()
            from search import views as search_views
            results = search_views.course_discovery_search()

        self.assertEqual(
            results["results"][0]["data"]["organization_display_name"],
            "Khyentse Foundation",
        )
        self.assertEqual(
            results["results"][1]["data"]["organization_display_name"],
            "Course Specific",
        )
        self.assertEqual(results["aggs"]["org"]["terms"], {"Khyentse_Foundation": 2})


class OrganizationDisplayNamesViewTest(SimpleTestCase):
    """Studio receives full names keyed by the short name it already stores."""

    @patch("course_partnerships.views.get_organizations")
    def test_returns_names_by_short_name(self, get_organizations):
        get_organizations.return_value = [
            {"short_name": "Khyentse_Foundation", "name": "Khyentse Foundation"},
            {"short_name": "blank", "name": ""},
        ]
        request = RequestFactory().get("/organizations/display-names")
        request.user = Mock(is_authenticated=True)

        response = OrganizationDisplayNamesView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {"Khyentse_Foundation": "Khyentse Foundation"},
        )
