"""Visibility rules for the Catalog homepage announcement."""

from datetime import datetime, timezone

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from course_partnerships.models import HomepageAnnouncement, homepage_announcement_is_active


NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)
EARLIER = datetime(2026, 10, 7, 11, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 10, 7, 13, 0, tzinfo=timezone.utc)


class HomepageAnnouncementActiveTest(SimpleTestCase):
    def test_enabled_with_no_window_is_active(self):
        self.assertTrue(homepage_announcement_is_active(True, None, None, NOW))

    def test_disabled_is_inactive_inside_the_window(self):
        self.assertFalse(homepage_announcement_is_active(False, EARLIER, LATER, NOW))

    def test_before_start_is_inactive(self):
        self.assertFalse(homepage_announcement_is_active(True, LATER, None, NOW))

    def test_at_end_is_inactive(self):
        self.assertFalse(homepage_announcement_is_active(True, None, NOW, NOW))

    def test_inside_window_is_active(self):
        self.assertTrue(homepage_announcement_is_active(True, EARLIER, LATER, NOW))

    def test_end_must_be_after_start(self):
        announcement = HomepageAnnouncement(message="Notice", enabled=True, start_at=LATER, end_at=EARLIER)
        with self.assertRaises(ValidationError):
            announcement.clean()
