"""
Request validation for the Studio schedule API.

Responses are plain dicts built in views.py, because they combine schedule rows
with section data read from the course.
"""

from django.utils.translation import gettext as _
from rest_framework import serializers

from .models import MAX_NUM_DAYS, SectionSchedule, time_errors, timezone_names


def _max_length(name):
    return SectionSchedule._meta.get_field(name).max_length


class SectionScheduleInputSerializer(serializers.Serializer):
    """One section's schedule, as sent by Studio."""

    section_id = serializers.CharField()
    start_date = serializers.DateField()
    num_days = serializers.IntegerField(min_value=1, max_value=MAX_NUM_DAYS, default=1)
    start_time = serializers.TimeField(required=False, allow_null=True, default=None)
    end_time = serializers.TimeField(required=False, allow_null=True, default=None)
    instructor = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=_max_length("instructor")
    )
    tools_required = serializers.CharField(required=False, allow_blank=True, default="", max_length=2000)
    notes = serializers.CharField(required=False, allow_blank=True, default="", max_length=5000)

    def validate(self, attrs):
        errors = time_errors(attrs["start_time"], attrs["end_time"])
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class CourseScheduleUpdateSerializer(serializers.Serializer):
    """
    A batch of changes to a course's schedule, applied in one transaction.

    ``upsert`` creates or replaces section schedules, ``remove`` unschedules
    sections, and ``timezone`` (optional) changes the course timezone.
    """

    timezone = serializers.CharField(required=False)
    upsert = SectionScheduleInputSerializer(many=True, required=False, default=list)
    remove = serializers.ListField(child=serializers.CharField(), required=False, default=list)

    def validate_timezone(self, value):
        if value not in timezone_names():
            raise serializers.ValidationError(_("{value} is not a valid timezone.").format(value=value))
        return value

    def validate(self, attrs):
        upsert_ids = [item["section_id"] for item in attrs["upsert"]]
        if len(upsert_ids) != len(set(upsert_ids)):
            raise serializers.ValidationError({"upsert": _("Each section can only appear once.")})
        if set(upsert_ids) & set(attrs["remove"]):
            raise serializers.ValidationError({"remove": _("A section cannot be both saved and removed.")})
        return attrs
