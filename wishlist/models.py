"""
Models for Wishlist

If you make changes to this model, be sure to create an appropriate migration
file and check it in at the same time as your model changes. To do that,

1. Go to the edx-platform dir
2. ./manage.py lms makemigrations --settings=production 
3. ./manage.py lms migrate --settings=production
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview


class Wishlist(TimeStampedModel):
    """
    Model for store users Wishlisted courses
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    course = models.ForeignKey(
        CourseOverview,
        db_constraint=False,
        db_index=True,
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return self.user.username

    class Meta:
        unique_together = ("user", "course")
        app_label = "wishlist"
        verbose_name = "Wishlist"
        verbose_name_plural = "Wishlists"

    @classmethod
    def is_wishlisted(cls, user, course_id):
        """
        Return whether `user` has wishlisted `course_id`.

        Used by the legacy Mako course-about page, which renders this
        unconditionally for every visitor -- so `user` may be an
        AnonymousUser, which can never have wishlisted anything.
        """
        if not user.is_authenticated:
            return False

        return cls.objects.filter(user=user, course_id=course_id).exists()
