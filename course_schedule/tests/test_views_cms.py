"""
Tests for the Studio schedule API (views_cms.py). Run under CMS test settings.
"""

from datetime import date, datetime, timezone

from django.test import override_settings
from django.urls import reverse
from openedx_events.tests.utils import OpenEdxEventsTestMixin
from rest_framework.test import APIClient

from common.djangoapps.student.tests.factories import UserFactory
from course_schedule.models import CourseScheduleSettings, SectionSchedule
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import BlockFactory, CourseFactory


class StudioCourseScheduleViewTest(OpenEdxEventsTestMixin, ModuleStoreTestCase):
    """GET and PUT api/course-schedule/v1/studio/<course_id>/"""

    # Events are off in tests unless listed; signals.py listens for this one.
    ENABLED_OPENEDX_EVENTS = ["org.openedx.content_authoring.xblock.deleted.v1"]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.start_events_isolation()

    def setUp(self):
        super().setUp()
        self.course = CourseFactory.create(
            start=datetime(2026, 10, 1, tzinfo=timezone.utc),
            end=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )
        self.lesson1 = BlockFactory(parent=self.course, category="chapter", display_name="Lesson 1")
        self.lesson2 = BlockFactory(parent=self.course, category="chapter", display_name="Lesson 2")
        BlockFactory(
            parent=self.lesson2,
            category="sequential",
            display_name="Quiz 2",
            due=datetime(2026, 10, 12, tzinfo=timezone.utc),
        )
        self.url = reverse("course_schedule:studio-course-schedule", kwargs={"course_id": str(self.course.id)})
        self.client = APIClient()
        self.client.force_authenticate(self.user)  # ModuleStoreTestCase's user is global staff

    def section_id(self, block):
        return str(block.location)

    def put(self, data):
        return self.client.put(self.url, data, format="json")

    def test_get_lists_sections_in_outline_order(self):
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.data["self_paced"] is False
        assert response.data["timezone"] == "Asia/Kolkata"
        assert "timezones" not in response.data  # fetched separately, only by the full editor
        assert [s["display_name"] for s in response.data["sections"]] == ["Lesson 1", "Lesson 2"]
        assert all(s["schedule"] is None for s in response.data["sections"])
        assert (response.data["scheduled_count"], response.data["total_count"]) == (0, 2)

    def test_non_author_is_forbidden(self):
        self.client.force_authenticate(UserFactory())
        assert self.client.get(self.url).status_code == 403
        assert self.put({"upsert": []}).status_code == 403

    def test_anonymous_is_rejected(self):
        self.client.force_authenticate(None)
        assert self.client.get(self.url).status_code == 401

    def test_put_upserts_and_returns_warnings(self):
        response = self.put(
            {
                "timezone": "Asia/Kathmandu",
                "upsert": [
                    {
                        "section_id": self.section_id(self.lesson1),
                        "start_date": "2026-10-13",
                        "num_days": 2,
                        "start_time": "19:00",
                        "end_time": "20:30",
                        "instructor": "Geshe Tenzin",
                        "tools_required": "Workbook",
                        "notes": "Bring a cushion 🧘",
                    },
                    {"section_id": self.section_id(self.lesson2), "start_date": "2026-10-14"},
                ],
            }
        )
        assert response.status_code == 200, response.data
        lesson1, lesson2 = response.data["sections"]
        assert lesson1["schedule"] == {
            "start_date": "2026-10-13",
            "end_date": "2026-10-14",
            "num_days": 2,
            "start_time": "19:00",
            "end_time": "20:30",
            "timezone_abbr": "+0545",
            "instructor": "Geshe Tenzin",
            "tools_required": "Workbook",
            "notes": "Bring a cushion 🧘",
        }
        assert [w["code"] for w in lesson1["warnings"]] == ["overlap"]
        assert [w["code"] for w in lesson2["warnings"]] == ["overlap", "due_before_session"]
        assert response.data["timezone"] == "Asia/Kathmandu"
        assert response.data["scheduled_count"] == 2
        assert SectionSchedule.objects.get(section_id=self.lesson1.location).updated_by == self.user

    def test_put_updates_existing_and_removes(self):
        self.put({"upsert": [{"section_id": self.section_id(self.lesson1), "start_date": "2026-10-12"}]})
        self.put({"upsert": [{"section_id": self.section_id(self.lesson1), "start_date": "2026-10-20"}]})
        assert SectionSchedule.objects.get(section_id=self.lesson1.location).start_date == date(2026, 10, 20)

        response = self.put({"remove": [self.section_id(self.lesson1)]})
        assert response.status_code == 200
        assert not SectionSchedule.objects.exists()

    def test_timezone_is_unchanged_when_omitted(self):
        CourseScheduleSettings.objects.create(course_id=self.course.id, timezone="Europe/Paris")
        response = self.put({"upsert": []})
        assert response.data["timezone"] == "Europe/Paris"

    def test_rejects_sections_from_another_course(self):
        other_course = CourseFactory.create()
        other_section = BlockFactory(parent=other_course, category="chapter")
        response = self.put({"upsert": [{"section_id": str(other_section.location), "start_date": "2026-10-12"}]})
        assert response.status_code == 400
        assert not SectionSchedule.objects.exists()

    def test_rejects_invalid_input(self):
        section_id = self.section_id(self.lesson1)
        bad_requests = [
            {"timezone": "Mars/Olympus"},
            {"upsert": [{"section_id": section_id, "start_date": "2026-10-12", "start_time": "19:00", "end_time": "19:00"}]},
            {"upsert": [{"section_id": section_id, "start_date": "2026-10-12", "end_time": "19:00"}]},
            {"upsert": [{"section_id": section_id, "start_date": "2026-10-12", "num_days": 0}]},
            {"upsert": [{"section_id": section_id, "start_date": "2026-10-12"}], "remove": [section_id]},
        ]
        for data in bad_requests:
            assert self.put(data).status_code == 400, data
        assert not SectionSchedule.objects.exists()

    def test_accepts_sessions_that_end_after_midnight(self):
        response = self.put(
            {"upsert": [{
                "section_id": self.section_id(self.lesson1),
                "start_date": "2026-10-12",
                "start_time": "22:00",
                "end_time": "00:30",
            }]}
        )
        assert response.status_code == 200, response.data
        assert response.data["sections"][0]["schedule"]["end_time"] == "00:30"

    def test_ignores_removing_a_section_that_no_longer_exists(self):
        self.put({"upsert": [{"section_id": self.section_id(self.lesson1), "start_date": "2026-10-12"}]})
        deleted_section_id = self.section_id(self.lesson1).replace(self.lesson1.location.block_id, "deleted")
        response = self.put({
            "upsert": [{"section_id": self.section_id(self.lesson2), "start_date": "2026-10-13"}],
            "remove": [deleted_section_id, self.section_id(self.lesson1)],
        })
        assert response.status_code == 200, response.data
        assert [s["schedule"] is not None for s in response.data["sections"]] == [False, True]

    @override_settings(COURSE_SCHEDULE_DEFAULT_TIMEZONE="Asia/Kolkatta")
    def test_falls_back_to_utc_when_the_default_timezone_is_misspelled(self):
        response = self.client.get(self.url)
        assert response.status_code == 200
        assert response.data["timezone"] == "UTC"

    def test_timezones_endpoint(self):
        response = self.client.get(reverse("course_schedule:studio-timezones"))
        assert response.status_code == 200
        assert "Asia/Kolkata" in response.data["timezones"]
        assert response.data["timezones"] == sorted(response.data["timezones"])

    def test_self_paced_course_is_read_only(self):
        self.course.self_paced = True
        self.update_course(self.course, self.user.id)
        assert self.client.get(self.url).data["self_paced"] is True
        response = self.put({"upsert": [{"section_id": self.section_id(self.lesson1), "start_date": "2026-10-12"}]})
        assert response.status_code == 400

    def test_deleting_a_section_deletes_its_schedule(self):
        self.put({"upsert": [{"section_id": self.section_id(self.lesson1), "start_date": "2026-10-12"}]})
        # The modulestore sends the delete event once the database transaction commits.
        with self.captureOnCommitCallbacks(execute=True):
            self.store.delete_item(self.lesson1.location, self.user.id)
        assert not SectionSchedule.objects.exists()
        assert self.client.get(self.url).data["total_count"] == 1
