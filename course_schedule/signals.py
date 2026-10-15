"""
Keep schedules in step with the course: drop them when their section or course is deleted.
"""

from django.dispatch import receiver
from openedx_events.content_authoring.data import XBlockData
from openedx_events.content_authoring.signals import XBLOCK_DELETED
from xmodule.modulestore.django import SignalHandler

from .helpers import normalize_usage_key
from .models import CourseScheduleSettings, SectionSchedule


@receiver(XBLOCK_DELETED)
def delete_section_schedule(**kwargs):
    """Remove the schedule of a section deleted in Studio."""
    xblock_info = kwargs.get("xblock_info")
    if not isinstance(xblock_info, XBlockData) or xblock_info.block_type != "chapter":
        return
    SectionSchedule.objects.filter(section_id=normalize_usage_key(xblock_info.usage_key)).delete()


@receiver(SignalHandler.course_deleted)
def delete_course_schedule(sender, course_key, **kwargs):  # pylint: disable=unused-argument
    """Remove every schedule row of a deleted course."""
    SectionSchedule.objects.filter(course_id=course_key).delete()
    CourseScheduleSettings.objects.filter(course_id=course_key).delete()
