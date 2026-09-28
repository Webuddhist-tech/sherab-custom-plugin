"""
Defines the URL routes for this app.
"""

from django.urls import path

from .views import (
    WishlistDetailView,
    WishlistListCreateView,
    WishlistStatusView,
)

app_name = "wishlist"


urlpatterns = [
    # JSON API used by the catalog MFE. "status/" is registered ahead of
    # "<str:course_id>/" so it isn't swallowed by that pattern.
    path("api/wishlist/status/", WishlistStatusView.as_view(), name="wishlist-status"),
    path("api/wishlist/<str:course_id>/", WishlistDetailView.as_view(), name="wishlist-detail"),
    path("api/wishlist/", WishlistListCreateView.as_view(), name="wishlist-list-create"),
]
