"""
Defines the URL routes for this app.
"""

from django.urls import path

from .views import OrganizationDisplayNamesView

app_name = "user_extension"

urlpatterns = [
    path(
        "organizations/display-names",
        OrganizationDisplayNamesView.as_view(),
        name="organization_display_names",
    ),
]
