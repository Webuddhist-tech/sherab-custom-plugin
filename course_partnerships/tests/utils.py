"""
Shared helpers for the course_partnerships tests.
"""

from course_partnerships.models import EnhancedCourse, Partner

DONATION_URL = "https://example.org/donate"


def make_partner(name="Sera Jey Monastery", slug="sera-jey", **kwargs):
    """
    Create a school with the donation card turned on, unless overridden.

    The logo is left empty so tests never touch the S3 storage backend.
    """
    fields = {
        "logo": "",
        "donation_enabled": True,
        "donation_url": DONATION_URL,
    }
    fields.update(kwargs)
    return Partner.objects.create(name=name, slug=slug, **fields)


def assign_partner(course_overview, partner):
    """
    File a course under a school, as the course publish handler does.
    """
    return EnhancedCourse.objects.create(course=course_overview, partner=partner)
