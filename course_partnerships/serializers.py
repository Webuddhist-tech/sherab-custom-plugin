from rest_framework import serializers

from course_partnerships.models import Category, EnhancedCourse, Partner, PartnerOrganizationMapping


class AbsoluteUrlMixin:
    """
    Shared resolution of a stored asset path to a fully-qualified URL.

    Used by every serializer that exposes an image, so the null-handling and
    absolute-URL rules stay identical across endpoints. Clients run on a
    different origin than the LMS, so host-relative paths have to be made
    absolute here rather than reassembled client-side.
    """

    def absolute_url(self, url):
        """
        Return the given URL made absolute against the current request.

        Args:
            url (str or None): The URL or path to resolve.

        Returns:
            str or None: Fully-qualified URL, or None when nothing is set.
        """
        if not url:
            return None

        request = self.context.get("request")
        # Storage backends that serve from an external host (e.g. S3) already
        # return an absolute URL, in which case build_absolute_uri is a no-op.
        return request.build_absolute_uri(url) if request else url

    def logo_url(self, logo):
        """
        Return a fully-qualified URL for the given logo, or None if unset.

        Args:
            logo (ImageFieldFile or None): The logo field to resolve.

        Returns:
            str or None: Fully-qualified logo URL if available, else None.
        """
        # The falsy check has to come first: an ImageFieldFile with no file is
        # falsy, and reading its `url` raises rather than returning None.
        if not logo or not hasattr(logo, "url"):
            return None

        return self.absolute_url(logo.url)


class PartnerSerializer(AbsoluteUrlMixin, serializers.ModelSerializer):
    """
    Serializer for partners, used for full (unfiltered) partner listings such
    as the homepage schools-and-partners carousel.

    Serializes:
        - partner_name (str): The partner's name
        - logo (str): Fully-qualified URL to the partner's logo
        - slug (str): The partner's slug, used to link to its school page (/schools/<slug>/)
    """

    partner_name = serializers.CharField(source="name")
    logo = serializers.SerializerMethodField()

    class Meta:
        model = Partner
        fields = ["partner_name", "logo", "slug"]

    def get_logo(self, obj):
        """
        Returns the fully-qualified URL for the partner's logo.

        Args:
            obj (Partner): Partner instance

        Returns:
            str or None: Fully-qualified logo URL if available, else None
        """
        return self.logo_url(obj.logo)


class PartnerOrganizationMappingSerializer(AbsoluteUrlMixin, serializers.ModelSerializer):
    """
    Serializer for Partner-Organization mappings.

    Serializes:
        - partner_name (str): Display name if provided, otherwise default partner name
        - logo (str): Fully-qualified URL to the partner's logo
        - organization (str): The short_name of the associated organization
    """

    partner_name = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()
    organization = serializers.CharField(source="organization.short_name")

    class Meta:
        model = PartnerOrganizationMapping
        fields = ["partner_name", "logo", "organization"]

    def get_partner_name(self, obj):
        """
        Return the custom display_name if present, otherwise default partner name.

        Args:
            obj (PartnerOrganizationMapping): Mapping instance

        Returns:
            str: Display name
        """
        return obj.display_name or obj.partner.name

    def get_logo(self, obj):
        """
        Returns the fully-qualified URL for the partner's logo.

        Args:
            obj (PartnerOrganizationMapping): Mapping instance

        Returns:
            str or None: Fully-qualified logo URL if available, else None
        """
        return self.logo_url(obj.partner.logo)


class HomepageCourseSerializer(AbsoluteUrlMixin, serializers.ModelSerializer):
    """
    Serializer for a single course as it appears on a homepage category card.

    Serialized from EnhancedCourse rather than CourseOverview because the
    partner and center a course is offered under are recorded there.

    Serializes:
        - course_id (str): The course key, used to link to the course about page
        - title (str): The course's display name
        - image_url (str): Fully-qualified URL to the course card image
        - provider_name (str): Name of the center, or the partner if no center
        - provider_logo (str): Fully-qualified logo URL for that same provider
    """

    course_id = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    provider_name = serializers.SerializerMethodField()
    provider_logo = serializers.SerializerMethodField()

    class Meta:
        model = EnhancedCourse
        fields = ["course_id", "title", "image_url", "provider_name", "provider_logo"]

    @staticmethod
    def _provider(obj):
        """
        Return the center a course is offered under, falling back to the partner.

        This center-then-partner precedence is the rule the site has always used
        for course branding. Returns None when a course has neither, which both
        provider fields handle.

        Args:
            obj (EnhancedCourse): Course-to-partner mapping instance

        Returns:
            Center or Partner or None: The provider to brand the course with.
        """
        return obj.center or obj.partner

    def get_course_id(self, obj):
        """
        Returns the course key as a string.

        Args:
            obj (EnhancedCourse): Course-to-partner mapping instance

        Returns:
            str: The course key.
        """
        # Read the foreign key's raw column rather than obj.course.id: it holds
        # the same key and avoids depending on the related row being loaded.
        return str(obj.course_id)

    def get_title(self, obj):
        """
        Returns the course's display name.

        Args:
            obj (EnhancedCourse): Course-to-partner mapping instance

        Returns:
            str: The course display name, or a default derived from its key.
        """
        return obj.course.display_name_with_default

    def get_image_url(self, obj):
        """
        Returns the fully-qualified URL for the course card image.

        Args:
            obj (EnhancedCourse): Course-to-partner mapping instance

        Returns:
            str or None: Fully-qualified image URL if available, else None.
        """
        # course_image_url is a plain host-relative path, not an image field,
        # so it needs absolute_url rather than logo_url.
        return self.absolute_url(obj.course.course_image_url)

    def get_provider_name(self, obj):
        """
        Returns the name of the center or partner offering the course.

        Args:
            obj (EnhancedCourse): Course-to-partner mapping instance

        Returns:
            str or None: The provider's name, or None if it has no provider.
        """
        provider = self._provider(obj)
        return provider.name if provider else None

    def get_provider_logo(self, obj):
        """
        Returns the logo of the center or partner offering the course.

        Args:
            obj (EnhancedCourse): Course-to-partner mapping instance

        Returns:
            str or None: Fully-qualified logo URL, or None if unavailable.
        """
        provider = self._provider(obj)
        return self.logo_url(provider.logo) if provider else None


class HomepageCategorySerializer(serializers.ModelSerializer):
    """
    Serializer for a homepage course category and the courses filed under it.

    Serializes:
        - id (int): The category's identifier, used as the tab key
        - name (str): The category's display name, used as the tab label
        - courses (list): The category's courses, see HomepageCourseSerializer
    """

    # Reads the attribute populated by the view's Prefetch(to_attr=...), so the
    # courses here are already filtered to the ones safe to show publicly.
    courses = HomepageCourseSerializer(many=True, source="visible_courses")

    class Meta:
        model = Category
        fields = ["id", "name", "courses"]
