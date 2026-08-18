"""
Models for course_partnerships

If you make changes to this model, be sure to create an appropriate migration
file and check it in at the same time as your model changes. To do that,

1. Go to the edx-platform dir
2. ./manage.py lms makemigrations --settings=production
3. ./manage.py lms migrate --settings=production
"""

from ckeditor.fields import RichTextField
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from organizations.models import Organization

from .validators import validate_bannner_extension
from .storage import PartnerLogoStorage, CenterLogoStorage, CourseCreatorStorage


class Partner(TimeStampedModel):
    """
    Model for store schools and partners details
    """

    name = models.CharField(
        max_length=255,
        db_index=True,
    )
    slug = models.SlugField(
        max_length=255,
        db_index=True,
    )
    logo = models.ImageField(
        "logo",
        upload_to="logos/",
        storage=PartnerLogoStorage(),
        help_text=_(
            "Upload only image file with .png, .jpeg, .jpg extension. Recommended image size: W 240px * H 340px"
        ),
        validators=[validate_bannner_extension],
    )
    banner = models.ImageField(
        "Banner",
        blank=True,
        null=True,
        upload_to="banners/",
        storage=PartnerLogoStorage(),
        help_text=_("Upload only image file with .png, .jpeg, .jpg extension."),
        validators=[validate_bannner_extension],
    )
    content = RichTextField("Description", null=True, blank=True)
    activate_school_admin = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        app_label = "course_partnerships"
        verbose_name = "Schools and Partners"
        verbose_name_plural = "Schools and Partners"


class Center(TimeStampedModel):
    """
    Model for store Center details
    """

    partner = models.ForeignKey(Partner, db_index=True, on_delete=models.CASCADE)
    name = models.CharField(
        max_length=255,
        db_index=True,
    )
    slug = models.SlugField(
        max_length=255,
        db_index=True,
    )
    logo = models.ImageField(
        "logo",
        upload_to="logos/",
        storage=CenterLogoStorage(),
        help_text=_(
            "Upload only image file with .png, .jpeg, .jpg extension. Recommended image size: W 240px * H 340px"
        ),
        validators=[validate_bannner_extension],
    )
    banner = models.ImageField(
        "Banner",
        blank=True,
        null=True,
        upload_to="banners/",
        storage=CenterLogoStorage(),
        help_text=_("Upload only image file with .png, .jpeg, .jpg extension."),
        validators=[validate_bannner_extension],
    )
    content = RichTextField("Description", null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        app_label = "course_partnerships"
        verbose_name = "Centers"
        verbose_name_plural = "Centers"


class Category(TimeStampedModel):
    """
    Model for store course categories details
    """

    name = models.CharField(max_length=100)
    partner = models.ForeignKey(Partner, null=True, blank=True, db_index=True, on_delete=models.CASCADE)
    show_on_homepage = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        app_label = "course_partnerships"
        verbose_name = "Course Categories"
        verbose_name_plural = "Course Categories"


class EnhancedCourse(TimeStampedModel):
    """
    Model for store course releted extra details
    """

    course = models.OneToOneField(
        CourseOverview,
        db_constraint=False,
        db_index=True,
        on_delete=models.CASCADE,
    )
    partner = models.ForeignKey(Partner, null=True, blank=True, db_index=True, on_delete=models.SET(""))
    center = models.ForeignKey(Center, null=True, blank=True, db_index=True, on_delete=models.SET(""))
    category = models.ForeignKey(Category, null=True, blank=True, db_index=True, on_delete=models.SET(""))

    class Meta:
        app_label = "course_partnerships"

    def __str__(self):
        return f"{self.course_id}"

    @classmethod
    def create_or_update(cls, course_id):
        """
        Create or update course detailss.
        """
        course, created = cls.objects.get_or_create(course_id=course_id)
        course.save()


class HeroCourse(TimeStampedModel):
    """
    A course featured in the homepage hero's pair of floating cards.

    Signed-in visitors see their own most recently enrolled courses there, so
    these curated picks are what a signed-out visitor sees instead — and what
    fills a leftover slot for a signed-in visitor who has not enrolled in two
    courses yet.
    """

    course = models.OneToOneField(
        CourseOverview,
        db_constraint=False,
        db_index=True,
        on_delete=models.CASCADE,
        help_text=_("Course to feature in the homepage hero."),
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text=_("Lower numbers are shown first. Only the first two active picks are used."),
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_("Uncheck to retire a pick without deleting it."),
    )
    # A date, not a checkbox, so the badge retires itself. Independent of
    # is_active: that controls curation, this controls the badge.
    new_until = models.DateField(
        null=True,
        blank=True,
        help_text=_(
            "Show a 'New course' badge until this date. Leave blank for none. "
            "Independent of 'is active'."
        ),
    )

    def __str__(self):
        return f"{self.course_id}"

    class Meta:
        app_label = "course_partnerships"
        # id breaks ties between picks sharing the same order.
        ordering = ("order", "id")
        verbose_name = "Homepage Hero Course"
        verbose_name_plural = "Homepage Hero Courses"


class PartnerOrganizationMapping(TimeStampedModel):
    """
    Mapping model between Partners and Organizations.

    Each record represents a unique relationship between a Partner and an Organization.
    This mapping is useful for defining which organizations a partner is associated with,
    and whether that relationship should be displayed in the mobile app.

    Fields:
        partner (ForeignKey): Reference to the Partner.
        organization (ForeignKey): Reference to the Organization.
        show_in_mobile_app (Boolean): If True, this mapping will be shown in the mobile app.
        display_name (CharField): Optional override for the partner's name in the UI.
    """

    partner = models.ForeignKey(
        Partner,
        on_delete=models.CASCADE,
        related_name="organization_mappings",
        help_text="The partner associated with the organization.",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="partner_mappings",
        help_text="The organization linked to the partner.",
    )
    show_in_mobile_app = models.BooleanField(
        default=False,
        help_text="Controls whether this partner-organization mapping is shown in the mobile app.",
    )
    display_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Custom name to display for the partner in this specific mapping.",
    )

    def __str__(self):
        return f"{self.partner.name} ↔ {self.organization.short_name}"

    class Meta:
        unique_together = ("partner", "organization")
        verbose_name = "Partner-Organization Mapping"
        verbose_name_plural = "Partner-Organization Mappings"


class CourseCreator(TimeStampedModel):
    """
    Model for storing course creator information.

    This model captures details about course creators/instructors including
    their profile picture, name, title, experience, and biography.
    """

    partner = models.ForeignKey(
        Partner,
        on_delete=models.CASCADE,
        db_index=True,
        related_name="course_creators",
        help_text=_("School/Partner this course creator is associated with"),
    )
    name = models.CharField(
        max_length=255,
        db_index=True,
        help_text=_("Full name of the course creator"),
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=_("Professional title or designation (e.g., Professor, Senior Instructor)"),
    )
    experience = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text=_("Years of experience (e.g., 5)"),
    )
    bio = models.TextField(
        "Biography",
        max_length=2000,
        blank=True,
        null=True,
        help_text=_("Detailed biography of the course creator (max 2000 characters)"),
    )
    profile_picture = models.ImageField(
        "Profile Picture",
        upload_to="profile_pictures/",
        storage=CourseCreatorStorage(),
        blank=True,
        null=True,
        help_text=_("Upload only image file with .png, .jpeg, .jpg extension."),
        validators=[validate_bannner_extension],
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Course Creator"
        verbose_name_plural = "Course Creators"
