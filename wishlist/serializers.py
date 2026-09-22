"""
Serializers for the wishlist API responses.
"""

from rest_framework import serializers

from .models import Wishlist


class WishlistItemSerializer(serializers.ModelSerializer):
    """
    Serializer for a single wishlisted course, as returned by the wishlist
    list endpoint.

    Serializes:
        - course_id (str): The course key
        - title (str): The course's display name
        - image_url (str): Host-relative URL to the course card image
        - org (str): The course's organization
        - start (datetime): The course's start date
        - advertised_start (str): The course's human-readable start date
        - created (datetime): When the course was added to the wishlist
    """

    course_id = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    org = serializers.SerializerMethodField()
    start = serializers.DateTimeField(source="course.start", read_only=True)
    advertised_start = serializers.CharField(source="course.advertised_start", read_only=True)

    class Meta:
        model = Wishlist
        fields = [
            "course_id",
            "title",
            "image_url",
            "org",
            "start",
            "advertised_start",
            "created",
        ]

    def get_course_id(self, obj):
        return str(obj.course_id)

    def get_title(self, obj):
        return obj.course.display_name_with_default

    def get_image_url(self, obj):
        return obj.course.course_image_url

    def get_org(self, obj):
        return obj.course.org
