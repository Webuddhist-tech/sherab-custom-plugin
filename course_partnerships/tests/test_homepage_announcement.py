"""Visibility rules for the Catalog homepage announcement."""

from datetime import datetime, timezone

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from course_partnerships.models import (
    HomepageAnnouncement,
    homepage_announcement_dismissal_session_id,
    homepage_announcement_is_active,
)


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

    def test_tone_defaults_to_info(self):
        announcement = HomepageAnnouncement(message="Notice")
        self.assertEqual(announcement.tone, "info")


class _Session(dict):
    def __init__(self, session_key=None, **values):
        super().__init__(**values)
        self.session_key = session_key


class _User:
    def __init__(self, is_authenticated):
        self.is_authenticated = is_authenticated


class _Request:
    def __init__(self, user, session):
        self.user = user
        self.session = session


class HomepageAnnouncementDismissalSessionTest(SimpleTestCase):
    def test_signed_out_has_no_id(self):
        request = _Request(_User(False), _Session("login", _auth_user_id="1"))
        self.assertIsNone(homepage_announcement_dismissal_session_id(request))

    def test_login_without_a_session_has_no_id(self):
        request = _Request(_User(True), _Session(None, _auth_user_id="1"))
        self.assertIsNone(homepage_announcement_dismissal_session_id(request))

    def test_same_login_keeps_the_same_id(self):
        session = _Session("login", _auth_user_id="7")
        user = _User(True)
        first = homepage_announcement_dismissal_session_id(_Request(user, session))
        second = homepage_announcement_dismissal_session_id(_Request(user, session))
        self.assertEqual(first, second)
        self.assertTrue(first)

    def test_next_login_gets_a_different_id(self):
        first_session = _Session("login-a", _auth_user_id="7")
        second_session = _Session("login-b", _auth_user_id="7")
        user = _User(True)
        first = homepage_announcement_dismissal_session_id(_Request(user, first_session))
        second = homepage_announcement_dismissal_session_id(_Request(user, second_session))
        self.assertNotEqual(first, second)
