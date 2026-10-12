"""
Models for course_schedule.

If you make changes to these models, create an appropriate migration file and
check it in at the same time. To do that:

1. Go to the edx-platform dir
2. ./manage.py lms makemigrations course_schedule
3. ./manage.py lms migrate course_schedule
"""

import logging
from datetime import timedelta
from functools import lru_cache
from zoneinfo import available_timezones

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from opaque_keys.edx.django.models import CourseKeyField, UsageKeyField

log = logging.getLogger(__name__)

User = get_user_model()

MAX_NUM_DAYS = 365
FALLBACK_TIMEZONE = "UTC"


@lru_cache(maxsize=1)
def timezone_names():
    """
    Every IANA timezone name the server knows, e.g. "Asia/Kolkata".

    Cached: zoneinfo.available_timezones() walks the whole tzdata directory.
    """
    return frozenset(available_timezones())


def validate_timezone(value):
    """Reject anything that is not an IANA timezone name."""
    if value not in timezone_names():
        raise ValidationError(_("{value} is not a valid timezone.").format(value=value))


def default_timezone():
    """
    COURSE_SCHEDULE_DEFAULT_TIMEZONE, or UTC if that setting isn't a real timezone.

    A typo in the setting would otherwise make every request fail when it
    builds the ZoneInfo, so it's logged and replaced instead.
    """
    name = getattr(settings, "COURSE_SCHEDULE_DEFAULT_TIMEZONE", "Asia/Kolkata")
    if name not in timezone_names():
        log.error("COURSE_SCHEDULE_DEFAULT_TIMEZONE=%r is not a valid timezone; using %s.", name, FALLBACK_TIMEZONE)
        return FALLBACK_TIMEZONE
    return name


def time_errors(start_time, end_time):
    """
    Problems with a session's times, as ``{field: message}``; empty when valid.

    Shared by the model and the API serializer. An end time earlier than the
    start time is allowed: the session runs past midnight into the next day.
    """
    if end_time and not start_time:
        return {"start_time": _("Set a start time before an end time.")}
    if start_time and end_time and end_time == start_time:
        return {"end_time": _("End time can't be the same as the start time.")}
    return {}


class CourseScheduleSettings(TimeStampedModel):
    """
    Per-course schedule settings.

    Open edX has no per-course timezone, so the schedule keeps its own: every
    section's date and times are wall-clock values in this timezone, and that
    is how learners see them too (no conversion to the viewer's timezone).

    A course without a row uses COURSE_SCHEDULE_DEFAULT_TIMEZONE.
    """

    course_id = CourseKeyField(max_length=255, unique=True)
    timezone = models.CharField(max_length=64, default=default_timezone, validators=[validate_timezone])

    class Meta:
        verbose_name = _("course schedule settings")
        verbose_name_plural = _("course schedule settings")

    def __str__(self):
        return f"{self.course_id} ({self.timezone})"


class SectionSchedule(TimeStampedModel):
    """
    When one section (chapter) of a course is taught, and by whom.

    Informational only: it never changes the section's release date or any
    due date. ``start_date`` and the times are wall-clock values in the course
    timezone (see CourseScheduleSettings). A section can span several days via
    ``num_days``; the times apply to each of those days. An ``end_time`` before
    ``start_time`` means the session ends after midnight, on the next day.

    The title shown to learners is the section's own display name, read from
    the course at request time, so it follows renames.
    """

    course_id = CourseKeyField(max_length=255, db_index=True)
    section_id = UsageKeyField(max_length=255, unique=True)

    start_date = models.DateField()
    num_days = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(MAX_NUM_DAYS)]
    )
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    instructor = models.CharField(max_length=255, blank=True, default="")
    tools_required = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")

    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = _("section schedule")
        verbose_name_plural = _("section schedules")

    def __str__(self):
        return f"{self.section_id} on {self.start_date}"

    @property
    def end_date(self):
        return self.start_date + timedelta(days=self.num_days - 1)

    def clean(self):
        super().clean()
        errors = time_errors(self.start_time, self.end_time)
        if errors:
            raise ValidationError(errors)
