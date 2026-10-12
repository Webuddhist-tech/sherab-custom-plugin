"""
Tests for the learner schedule API (views_lms.py). Run under LMS test settings.
"""

from datetime import date, datetime, time, timezone

from django.urls import reverse
from rest_framework.test import APIClient

from cms.djangoapps.contentstore.outlines import update_outline_from_modulestore
from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.tests.factories import UserFactory
from course_schedule.models import SectionSchedule
from openedx.core.djangoapps.course_date_signals.handlers import extract_dates
from xmodule.course_metadata_utils import DEFAULT_START_DATE
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import BlockFactory, CourseFactory


class LearnerCourseScheduleViewTest(ModuleStoreTestCase):
    """GET api/course-schedule/v1/<course_id>/"""

    def setUp(self):
        super().setUp()
        self.course = CourseFactory.create(
            start=datetime(2026, 10, 1, tzinfo=timezone.utc),
            end=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )
        self.lesson1 = self.add_section("Lesson 1")
        self.lesson2 = self.add_section("Lesson 2", start=datetime(2026, 10, 20, tzinfo=timezone.utc))
        self.staff_only = self.add_section("Draft lesson", visible_to_staff_only=True)
        self.publish()

        self.schedule(self.lesson1, date(2026, 10, 14), start_time=time(19, 0), end_time=time(20, 30))
        self.schedule(self.lesson2, date(2026, 10, 13), instructor="Ani Pema")
        self.schedule(self.staff_only, date(2026, 10, 15))

        self.learner = UserFactory()
        CourseEnrollment.enroll(self.learner, self.course.id)
        self.url = reverse("course_schedule:learner-course-schedule", kwargs={"course_id": str(self.course.id)})
        self.client = APIClient()
        self.client.force_authenticate(self.learner)

    def publish(self):
        """What a Studio publish does for the LMS: rebuild the outline and the release dates."""
        update_outline_from_modulestore(self.course.id)
        extract_dates(None, self.course.id)

    def add_section(self, name, **fields):
        section = BlockFactory(parent=self.course, category="chapter", display_name=name, **fields)
        # learning_sequences drops sections without subsections, as the course outline does.
        BlockFactory(parent=section, category="sequential", display_name=f"{name} reading")
        return section

    def schedule(self, section, start_date, **fields):
        SectionSchedule.objects.create(
            course_id=self.course.id, section_id=section.location, start_date=start_date, **fields
        )

    def test_lists_visible_sessions_sorted_by_date(self):
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.data["enabled"] is True
        assert response.data["timezone"] == "Asia/Kolkata"
        assert [s["title"] for s in response.data["sessions"]] == ["Lesson 2", "Lesson 1"]

        lesson2, lesson1 = response.data["sessions"]
        assert lesson1["start_time"] == "19:00"
        assert lesson1["end_time"] == "20:30"
        assert lesson1["timezone_abbr"] == "IST"
        assert lesson1["content_available_from"] is None
        assert lesson2["instructor"] == "Ani Pema"
        assert lesson2["content_available_from"] == "2026-10-20"

    def test_unscheduled_release_date_is_not_shown_as_2030(self):
        unscheduled = self.add_section("Not yet scheduled", start=DEFAULT_START_DATE)
        self.publish()
        self.schedule(unscheduled, date(2026, 10, 16))

        response = self.client.get(self.url)
        session = next(s for s in response.data["sessions"] if s["title"] == "Not yet scheduled")
        assert session["content_available_from"] is None

    def test_title_follows_section_renames(self):
        self.lesson1.display_name = "Lesson 1: Basics"
        self.store.update_item(self.lesson1, self.user.id)
        self.publish()
        titles = [s["title"] for s in self.client.get(self.url).data["sessions"]]
        assert "Lesson 1: Basics" in titles

    def test_staff_see_staff_only_sections(self):
        self.client.force_authenticate(self.user)  # global staff, not enrolled
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert "Draft lesson" in [s["title"] for s in response.data["sessions"]]

    def test_not_enrolled_is_rejected(self):
        self.client.force_authenticate(UserFactory())
        assert self.client.get(self.url).status_code == 401

    def test_anonymous_is_rejected(self):
        self.client.force_authenticate(None)
        assert self.client.get(self.url).status_code == 401

    def test_self_paced_course_is_disabled(self):
        self.course.self_paced = True
        self.update_course(self.course, self.user.id)
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.data["enabled"] is False
        assert response.data["sessions"] == []
