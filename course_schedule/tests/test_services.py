"""
Tests for the pure scheduling logic in services.py.
"""

from datetime import date, datetime, time, timezone
from unittest import TestCase
from zoneinfo import ZoneInfo

from course_schedule.services import (
    AFTER_COURSE_END,
    BEFORE_COURSE_START,
    BEFORE_RELEASE,
    DUE_BEFORE_SESSION,
    OVERLAP,
    CourseInfo,
    SectionInfo,
    SessionTimes,
    SubsectionInfo,
    compute_warnings,
    content_available_from,
    order_sessions,
    timezone_abbr,
)

IST = ZoneInfo("Asia/Kolkata")


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def codes(warnings):
    return [warning["code"] for warning in warnings]


class SessionTimesTest(TestCase):
    def test_end_date_spans_num_days(self):
        self.assertEqual(SessionTimes(date(2026, 10, 13), 2).end_date, date(2026, 10, 14))

    def test_datetimes_default_to_whole_days(self):
        session = SessionTimes(date(2026, 10, 12))
        self.assertEqual(session.start_datetime(IST), datetime(2026, 10, 12, 0, 0, tzinfo=IST))
        self.assertEqual(session.end_datetime(IST), datetime.combine(date(2026, 10, 12), time.max, tzinfo=IST))


class ComputeWarningsTest(TestCase):
    def setUp(self):
        self.sections = [
            SectionInfo("s1", "Lesson 1"),
            SectionInfo("s2", "Lesson 2"),
            SectionInfo("s3", "Lesson 3"),
        ]
        self.course = CourseInfo(start=utc(2026, 10, 1), end=utc(2026, 12, 31))
        self.evening = (time(19, 0), time(20, 30))

    def session(self, day, num_days=1):
        return SessionTimes(date(2026, 10, day), num_days, *self.evening)

    def test_back_to_back_sessions_have_no_warnings(self):
        schedules = {"s1": self.session(12), "s2": self.session(13), "s3": self.session(14)}
        warnings = compute_warnings(self.course, self.sections, schedules, IST)
        self.assertEqual(warnings, {"s1": [], "s2": [], "s3": []})

    def test_unscheduled_sections_get_no_entry(self):
        warnings = compute_warnings(self.course, self.sections, {"s1": self.session(12)}, IST)
        self.assertEqual(list(warnings), ["s1"])

    def test_multi_day_section_overlaps_the_next(self):
        schedules = {"s2": self.session(13, num_days=2), "s3": self.session(14)}
        warnings = compute_warnings(self.course, self.sections, schedules, IST)
        self.assertEqual(warnings["s2"], [{"code": OVERLAP, "params": {"section_id": "s3", "display_name": "Lesson 3"}}])
        self.assertEqual(codes(warnings["s3"]), [OVERLAP])

    def test_multi_day_section_does_not_overlap_a_different_time_on_a_middle_day(self):
        schedules = {
            "s1": SessionTimes(date(2026, 10, 12), 3, time(10, 0), time(12, 0)),
            "s2": SessionTimes(date(2026, 10, 13), 1, time(15, 0), time(16, 0)),
        }
        warnings = compute_warnings(self.course, self.sections, schedules, IST)
        self.assertEqual(warnings, {"s1": [], "s2": []})

    def test_multi_day_section_overlaps_the_same_time_on_a_middle_day(self):
        schedules = {
            "s1": SessionTimes(date(2026, 10, 12), 3, time(10, 0), time(12, 0)),
            "s2": SessionTimes(date(2026, 10, 13), 1, time(11, 0), time(13, 0)),
        }
        warnings = compute_warnings(self.course, self.sections, schedules, IST)
        self.assertEqual(codes(warnings["s1"]), [OVERLAP])
        self.assertEqual(codes(warnings["s2"]), [OVERLAP])

    def test_session_past_midnight_overlaps_the_next_days_early_session(self):
        schedules = {
            "s1": SessionTimes(date(2026, 10, 12), 1, time(22, 0), time(1, 0)),
            "s2": SessionTimes(date(2026, 10, 13), 1, time(0, 30), time(2, 0)),
        }
        warnings = compute_warnings(self.course, self.sections, schedules, IST)
        self.assertEqual(codes(warnings["s1"]), [OVERLAP])

    def test_same_day_different_times_do_not_overlap(self):
        schedules = {
            "s1": SessionTimes(date(2026, 10, 12), 1, time(9, 0), time(10, 0)),
            "s2": SessionTimes(date(2026, 10, 12), 1, time(19, 0), time(20, 0)),
        }
        warnings = compute_warnings(self.course, self.sections, schedules, IST)
        self.assertEqual(warnings, {"s1": [], "s2": []})

    def test_session_without_times_overlaps_any_session_that_day(self):
        schedules = {"s1": SessionTimes(date(2026, 10, 12)), "s2": self.session(12)}
        warnings = compute_warnings(self.course, self.sections, schedules, IST)
        self.assertEqual(codes(warnings["s1"]), [OVERLAP])

    def test_outside_course_dates(self):
        course = CourseInfo(start=utc(2026, 10, 12), end=utc(2026, 10, 20))
        schedules = {"s1": self.session(5), "s2": self.session(25)}
        warnings = compute_warnings(course, self.sections, schedules, IST)
        self.assertEqual(warnings["s1"], [{"code": BEFORE_COURSE_START, "params": {"date": "2026-10-12"}}])
        self.assertEqual(warnings["s2"], [{"code": AFTER_COURSE_END, "params": {"date": "2026-10-20"}}])

    def test_course_dates_are_optional(self):
        warnings = compute_warnings(CourseInfo(), self.sections, {"s1": self.session(5)}, IST)
        self.assertEqual(warnings["s1"], [])

    def test_before_release(self):
        sections = [SectionInfo("s1", "Lesson 1", release_date=utc(2026, 10, 20, 0, 0))]
        warnings = compute_warnings(self.course, sections, {"s1": self.session(14)}, IST)
        self.assertEqual(warnings["s1"], [{"code": BEFORE_RELEASE, "params": {"date": "2026-10-20"}}])

    def test_release_before_session_is_fine(self):
        sections = [SectionInfo("s1", "Lesson 1", release_date=utc(2026, 10, 10))]
        warnings = compute_warnings(self.course, sections, {"s1": self.session(14)}, IST)
        self.assertEqual(warnings["s1"], [])

    def test_subsection_due_before_session(self):
        sections = [
            SectionInfo(
                "s1",
                "Lesson 1",
                subsections=[
                    SubsectionInfo("Quiz 1", due=utc(2026, 10, 12)),
                    SubsectionInfo("Quiz 2", due=utc(2026, 10, 30)),
                    SubsectionInfo("Reading"),
                ],
            )
        ]
        warnings = compute_warnings(self.course, sections, {"s1": self.session(14)}, IST)
        self.assertEqual(
            warnings["s1"],
            [{"code": DUE_BEFORE_SESSION, "params": {"display_name": "Quiz 1", "date": "2026-10-12"}}],
        )

    def test_dates_are_compared_in_course_timezone(self):
        # 19:00 IST on the 14th is 13:30 UTC; a release at 14:00 UTC is after it.
        sections = [SectionInfo("s1", "Lesson 1", release_date=utc(2026, 10, 14, 14, 0))]
        warnings = compute_warnings(self.course, sections, {"s1": self.session(14)}, IST)
        self.assertEqual(codes(warnings["s1"]), [BEFORE_RELEASE])


class SessionsWithoutTimesTest(TestCase):
    """A session with no time is compared by calendar day in the course timezone."""

    def setUp(self):
        self.sections = [SectionInfo("s1", "Lesson 1"), SectionInfo("s2", "Lesson 2")]

    def test_same_day_as_course_start_is_not_before_it(self):
        # The course opens 00:00 UTC = 05:30 IST on Oct 12; a time-less Oct 12 session is fine.
        course = CourseInfo(start=utc(2026, 10, 12))
        warnings = compute_warnings(course, self.sections, {"s1": SessionTimes(date(2026, 10, 12))}, IST)
        self.assertEqual(warnings["s1"], [])

    def test_earlier_day_is_still_before_course_start(self):
        course = CourseInfo(start=utc(2026, 10, 12))
        warnings = compute_warnings(course, self.sections, {"s1": SessionTimes(date(2026, 10, 11))}, IST)
        self.assertEqual(codes(warnings["s1"]), [BEFORE_COURSE_START])

    def test_same_day_as_course_end_is_not_after_it(self):
        course = CourseInfo(end=utc(2026, 10, 20, 12, 0))
        warnings = compute_warnings(course, self.sections, {"s1": SessionTimes(date(2026, 10, 20))}, IST)
        self.assertEqual(warnings["s1"], [])

    def test_same_day_release_shows_no_note(self):
        session = SessionTimes(date(2026, 10, 12))
        self.assertIsNone(content_available_from(session, utc(2026, 10, 12), IST))
        self.assertEqual(content_available_from(session, utc(2026, 10, 13), IST), date(2026, 10, 13))

    def test_due_the_same_day_is_not_before_the_session(self):
        sections = [SectionInfo("s1", "Lesson 1", subsections=[SubsectionInfo("Quiz", due=utc(2026, 10, 12, 1, 0))])]
        warnings = compute_warnings(CourseInfo(), sections, {"s1": SessionTimes(date(2026, 10, 12))}, IST)
        self.assertEqual(warnings["s1"], [])


class OvernightSessionsTest(TestCase):
    """An end time earlier than the start time means the session ends the next day."""

    def test_ends_the_next_day(self):
        session = SessionTimes(date(2026, 10, 12), 1, time(22, 0), time(0, 30))
        self.assertTrue(session.ends_next_day)
        self.assertEqual(session.end_datetime(IST), datetime(2026, 10, 13, 0, 30, tzinfo=IST))

    def test_overlaps_an_early_session_the_next_morning(self):
        sections = [SectionInfo("s1", "Night"), SectionInfo("s2", "Morning")]
        schedules = {
            "s1": SessionTimes(date(2026, 10, 12), 1, time(22, 0), time(1, 0)),
            "s2": SessionTimes(date(2026, 10, 13), 1, time(0, 30), time(2, 0)),
        }
        warnings = compute_warnings(CourseInfo(), sections, schedules, IST)
        self.assertEqual(codes(warnings["s1"]), [OVERLAP])

    def test_past_midnight_on_the_last_day_is_after_course_end(self):
        course = CourseInfo(end=datetime(2026, 10, 13, 0, 0, tzinfo=IST))
        schedules = {"s1": SessionTimes(date(2026, 10, 12), 1, time(22, 0), time(0, 30))}
        warnings = compute_warnings(course, [SectionInfo("s1", "Night")], schedules, IST)
        self.assertEqual(codes(warnings["s1"]), [AFTER_COURSE_END])


class ContentAvailableFromTest(TestCase):
    def test_reports_release_date_in_course_timezone(self):
        session = SessionTimes(date(2026, 10, 14), 1, time(19, 0))
        # 20:00 UTC on the 14th is already the 15th in IST.
        self.assertEqual(content_available_from(session, utc(2026, 10, 14, 20, 0), IST), date(2026, 10, 15))

    def test_none_when_released(self):
        session = SessionTimes(date(2026, 10, 14), 1, time(19, 0))
        self.assertIsNone(content_available_from(session, utc(2026, 10, 1), IST))
        self.assertIsNone(content_available_from(session, None, IST))


class OrderSessionsTest(TestCase):
    def test_sorts_by_date_then_time_then_outline_order(self):
        sessions = {
            "s3": SessionTimes(date(2026, 10, 12), 1, time(9, 0)),
            "s1": SessionTimes(date(2026, 10, 13)),
            "s2": SessionTimes(date(2026, 10, 12), 1, time(9, 0)),
            "s4": SessionTimes(date(2026, 10, 12)),
        }
        self.assertEqual(order_sessions(sessions, ["s1", "s2", "s3", "s4"]), ["s4", "s2", "s3", "s1"])


class TimezoneAbbrTest(TestCase):
    def test_abbreviation(self):
        self.assertEqual(timezone_abbr(date(2026, 10, 12), time(19, 0), IST), "IST")

    def test_follows_daylight_saving(self):
        new_york = ZoneInfo("America/New_York")
        self.assertEqual(timezone_abbr(date(2026, 7, 1), None, new_york), "EDT")
        self.assertEqual(timezone_abbr(date(2026, 12, 1), None, new_york), "EST")
