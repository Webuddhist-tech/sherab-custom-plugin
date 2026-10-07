"""
    Manage signal handlers here
"""

import logging

from django.dispatch import receiver
from django.db.models.signals import post_save
from xmodule.modulestore.django import SignalHandler

from ..helpers import get_course_partner
from ..models import EnhancedCourse

log = logging.getLogger(__name__)


@receiver(SignalHandler.course_published)
def course_publish_signal_handler(sender, course_key, **kwargs):
    """
    Receives course publishing signal and creates/updates EnhancedCourse with partner
    """
    course, created = EnhancedCourse.objects.get_or_create(course_id=course_key)

    # Try to auto-assign partner based on organization
    if not course.partner:
        try:
            # The course has no partner yet, so this resolves it through its organization.
            partner = get_course_partner(course_key)
            if partner:
                course.partner = partner
                course.save()
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.warning("Could not auto-assign partner to course %s: %s", course_key, e)


@receiver(SignalHandler.course_deleted)
def _listen_for_course_delete(sender, course_key, **kwargs):  # pylint: disable=unused-argument
    """
    Catches the signal that a course has been deleted from Studio and
    invalidates the corresponding Course cache entry if one exists.
    """
    EnhancedCourse.objects.filter(course_id=course_key).delete()
