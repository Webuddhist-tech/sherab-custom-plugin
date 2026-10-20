"""CMS settings for the temporary Studio help-link override."""

from pathlib import Path


def plugin_settings(settings):
    """Point Studio at this app's help-token file.

    The book base stops before ``latest``. Ulmo rewrites ``/latest`` inside
    HELP_TOKENS_BOOKS to ``open-release-ulmo.master``, which 404s.
    """
    settings.HELP_TOKENS_BOOKS["current_docs"] = "https://docs.openedx.org/en"
    settings.HELP_TOKENS_INI_FILE = str(
        Path(__file__).resolve().parents[1] / "cms_help_tokens.ini"
    )
