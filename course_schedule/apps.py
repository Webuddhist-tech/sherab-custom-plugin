"""
Course Schedule - App Configuration.

Lets course creators schedule each section (chapter) of an instructor-paced
course - date(s), time, instructor, tools, notes - from the Studio course
outline, and shows that schedule to learners on the Dates tab.

The schedule is informational only: it never changes release dates, due dates
or access. It lives in this app's own tables, not in the modulestore or
edx-when, so it can be moved freely without republishing the course.

Registered in both the LMS (learner API) and the CMS (Studio API); each
service mounts its own urls module.
"""

import logging

from django.apps import AppConfig

from edx_django_utils.plugins import PluginSettings, PluginURLs
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType

log = logging.getLogger(__name__)


class CourseScheduleConfig(AppConfig):
    name = "course_schedule"
    label = "course_schedule"

    # Title shown for this app's models group in the Django admin.
    verbose_name = "Course Schedule"

    # See: https://edx.readthedocs.io/projects/edx-django-utils/en/latest/edx_django_utils.plugins.html
    plugin_app = {
        PluginURLs.CONFIG: {
            ProjectType.LMS: {
                PluginURLs.NAMESPACE: name,
                PluginURLs.REGEX: "^",
                PluginURLs.RELATIVE_PATH: "urls_lms",
            },
            ProjectType.CMS: {
                PluginURLs.NAMESPACE: name,
                PluginURLs.REGEX: "^",
                PluginURLs.RELATIVE_PATH: "urls_cms",
            },
        },
        PluginSettings.CONFIG: {
            ProjectType.LMS: {
                SettingsType.PRODUCTION: {PluginSettings.RELATIVE_PATH: "settings.production"},
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
            },
            ProjectType.CMS: {
                SettingsType.PRODUCTION: {PluginSettings.RELATIVE_PATH: "settings.production"},
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
            },
        },
    }

    def ready(self):
        from . import signals  # pylint: disable=unused-import

        log.debug("{label} is ready.".format(label=self.label))
