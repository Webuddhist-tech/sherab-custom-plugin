"""Studio help-link overrides.

Temporary CMS app. Delete this package and its setup.py entry once Studio's
own help_tokens.ini points content_highlights at the current docs.
"""

from django.apps import AppConfig

from edx_django_utils.plugins import PluginSettings
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class StudioHelpLinksConfig(AppConfig):
    name = "studio_help_links"
    label = "studio_help_links"
    verbose_name = "Studio Help Links"

    plugin_app = {
        PluginSettings.CONFIG: {
            ProjectType.CMS: {
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
            },
        },
    }
