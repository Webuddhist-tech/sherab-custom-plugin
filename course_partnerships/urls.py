"""
Defines the URL routes for this app.
"""

from django.urls import path

from .views import *

app_name = "course_partnerships"


urlpatterns = [
    path("schools/<slug:slug>/", PartnerDetailView.as_view(), name="partner-detail"),
    path("schools/<slug:partner_slug>/<slug:center_slug>/", CenterDetailView.as_view(), name="center-detail"),

    # Endpoint to retrieve partner-organization mappings visible in the mobile app
    path("api/partners/", PartnerListAPIView.as_view(), name="partner-list"),

    # Endpoint to retrieve all partners, for the homepage schools-and-partners carousel
    path("api/partners/homepage/", PartnerHomepageListAPIView.as_view(), name="partner-homepage-list"),

    # Endpoint to retrieve the homepage course categories with their courses
    path("api/categories/homepage/", HomepageCategoryListAPIView.as_view(), name="homepage-category-list"),

    # Endpoint to retrieve the courses shown in the homepage hero cards
    path("api/courses/hero/", HeroCourseListAPIView.as_view(), name="hero-course-list"),
]
