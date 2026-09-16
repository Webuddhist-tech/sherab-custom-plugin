"""
Defines the URL routes for this app.
"""

from django.urls import path

from .views import (
    WishListChangeView,
    WishlistDetailView,
    WishlistListCreateView,
    WishlistStatusView,
    wishlist_view,
)

app_name = "wishlist"


urlpatterns = [
    # Legacy HTML/plain-text endpoints, kept for backward compatibility.
    path("wishlist/change-status/", WishListChangeView.as_view(), name="change-wishlist-status"),
    path("wishlist/", wishlist_view, name="wishlist-view"),

    # JSON API used by the catalog MFE. "status/" is registered ahead of
    # "<str:course_id>/" so it isn't swallowed by that pattern.
    path("api/wishlist/status/", WishlistStatusView.as_view(), name="wishlist-status"),
    path("api/wishlist/<str:course_id>/", WishlistDetailView.as_view(), name="wishlist-detail"),
    path("api/wishlist/", WishlistListCreateView.as_view(), name="wishlist-list-create"),
]
