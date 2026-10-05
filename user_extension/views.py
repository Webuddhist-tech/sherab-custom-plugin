import logging
from django.contrib.auth.decorators import login_required
from django.views.generic import View
from django.db.models import Count
from django.conf import settings
from django.utils.decorators import method_decorator
from django.http import Http404, JsonResponse
from common.djangoapps.edxmako.shortcuts import render_to_response
from organizations.api import get_organizations

from .models import *

log = logging.getLogger(__name__)


class OrganizationDisplayNamesView(View):
    """Return full organization names keyed by their short names."""

    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        """Return the labels used when displaying organization identifiers in Studio."""
        return JsonResponse({
            organization["short_name"]: organization["name"]
            for organization in get_organizations()
            if organization.get("name")
        })
