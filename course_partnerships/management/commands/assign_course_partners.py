from django.core.management.base import BaseCommand

from course_partnerships.helpers import get_course_partner
from course_partnerships.models import EnhancedCourse


class Command(BaseCommand):
    """
    Command to auto-assign partners to courses based on organization mappings.

    Example usage:
        ./manage.py assign_course_partners
    """
    help = "Auto-assign partners to courses based on organization mappings"

    def handle(self, *args, **options):
        courses_updated = 0

        # Get all EnhancedCourses without partners
        courses = EnhancedCourse.objects.filter(partner__isnull=True)

        for enhanced_course in courses:
            try:
                # The course has no partner, so this resolves it through its organization.
                partner = get_course_partner(enhanced_course.course_id)

                if partner:
                    enhanced_course.partner = partner
                    enhanced_course.save()
                    courses_updated += 1
                    self.stdout.write(self.style.SUCCESS(f"Assigned {partner.name} to {enhanced_course.course_id}"))
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.stdout.write(self.style.ERROR(f"Error processing {enhanced_course.course_id}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Successfully updated {courses_updated} courses"))
