import csv

from django.contrib import admin
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

from .helpers import get_partner_course_keys
from .models import *


class PartnerAdmin(admin.ModelAdmin):
    list_display = ["name", "activate_school_admin", "donation_enabled"]
    list_filter = ["donation_enabled"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}
    # Two-box picker with a search box; the choices are limited to this
    # school's courses in formfield_for_manytomany().
    filter_horizontal = ["donation_excluded_courses"]
    donation_fields = (
        "donation_enabled",
        "donation_show_heading",
        "donation_heading",
        "donation_message",
        "donation_button_label",
        "donation_url",
        "donation_excluded_courses",
    )

    def get_fieldsets(self, request, obj=None):
        # Everything except the donation settings goes in the first section,
        # so fields added to Partner later still show up without editing this.
        other_fields = [field for field in self.get_fields(request, obj) if field not in self.donation_fields]
        return [
            (None, {"fields": other_fields}),
            (
                "Donation card",
                {
                    "classes": ("collapse",),
                    "description": (
                        "Shows a card on the course home page of this school's courses, linking to the school's "
                        "own donation page. Only learners enrolled in a course that hasn't ended see it."
                    ),
                    "fields": self.donation_fields,
                },
            ),
        ]

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "donation_excluded_courses":
            # Not given the object being edited, so read it from the change URL.
            object_id = request.resolver_match.kwargs.get("object_id") if request.resolver_match else None
            partner = self.get_object(request, object_id) if object_id else None
            kwargs["queryset"] = self.partner_courses(partner)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    @staticmethod
    def partner_courses(partner):
        """
        Return the courses the excluded-courses picker offers, by name: the
        school's courses (see get_partner_course_keys), plus any course it
        already excludes, so saving the form never drops an exclusion. A
        school that isn't saved yet has none.
        """
        if partner is None or partner.pk is None:
            return CourseOverview.objects.none()

        return (
            CourseOverview.objects.filter(
                Q(id__in=get_partner_course_keys(partner)) | Q(donation_excluding_partners=partner)
            )
            .distinct()
            .order_by("display_name")
        )


class CenterAdmin(admin.ModelAdmin):
    list_display = ["name", "partner"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "partner", "show_on_homepage"]
    search_fields = ["name"]
    raw_id_fields = ["partner"]


class EnhancedCourseAdmin(admin.ModelAdmin):
    list_display = ["course", "partner", "center", "category"]
    search_fields = ["course_id"]
    raw_id_fields = ["course", "partner", "center", "category"]


class HeroCourseAdmin(admin.ModelAdmin):
    # Editable inline so rearranging cards or extending a badge is one submit.
    list_display = ["course", "order", "is_active", "new_until", "badge_showing"]
    list_editable = ["order", "is_active", "new_until"]
    list_filter = ["is_active"]
    # Searches the course title, not just the raw key.
    search_fields = ["course__id", "course__display_name"]
    raw_id_fields = ["course"]
    ordering = ["order", "id"]

    # Shows whether the badge is actually live today. Computed, so it can't be
    # list_editable or list_filter.
    @admin.display(boolean=True, description="Badge live")
    def badge_showing(self, obj):
        """
        Returns whether this pick's badge is showing on the site right now.
        """
        return bool(obj.new_until and obj.new_until >= timezone.localdate())


class PartnerOrganizationMappingAdmin(admin.ModelAdmin):
    list_display = ("partner", "organization", "display_name", "show_in_mobile_app")
    list_filter = ("show_in_mobile_app", "partner", "organization")
    search_fields = (
        "partner__name",
        "organization__name",
        "organization__short_name",
        "display_name",
    )


class CourseCreatorAdmin(admin.ModelAdmin):
    list_display = ("name", "partner", "title", "experience")
    list_filter = ("partner",)
    search_fields = ("name", "title", "partner__name")
    raw_id_fields = ("partner",)
    readonly_fields = ("created", "modified")
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("partner", "name", "profile_picture"),
            },
        ),
        (
            "Professional Details",
            {
                "fields": ("title", "experience", "bio"),
            },
        ),
    )


class DonationClickAdmin(admin.ModelAdmin):
    """
    Donation click report: every click, with per-school and per-course totals.

    Read-only. The summary above the list follows the list's filters, and the
    CSV actions export whichever rows are selected ("Select all" for the
    whole filtered list).
    """

    change_list_template = "admin/course_partnerships/donationclick/change_list.html"
    list_display = ["created", "partner", "course_id", "user"]
    list_filter = ["partner"]
    list_select_related = ["partner", "user"]
    date_hierarchy = "created"
    search_fields = ["course_id", "user__username", "partner__name"]
    ordering = ["-created"]
    actions = ["export_summary_csv", "export_clicks_csv"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    # Click history is kept forever.
    def has_delete_permission(self, request, obj=None):
        return False

    @staticmethod
    def summarize(queryset):
        """
        Return total clicks and unique learners per school and course.
        """
        return (
            queryset.order_by()
            .values("partner__name", "course_id")
            .annotate(total_clicks=Count("id"), unique_learners=Count("user", distinct=True))
            .order_by("partner__name", "course_id")
        )

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        # Not a TemplateResponse when the view redirects or runs an action.
        context = getattr(response, "context_data", None)
        if context and "cl" in context:
            context["donation_summary"] = self.summarize(context["cl"].queryset)
        return response

    @staticmethod
    def csv_response(filename, header, rows):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        writer = csv.writer(response)
        writer.writerow(header)
        writer.writerows(rows)
        return response

    @admin.action(description="Export summary as CSV (per school and course)")
    def export_summary_csv(self, request, queryset):
        rows = (
            (row["partner__name"] or "", row["course_id"], row["total_clicks"], row["unique_learners"])
            for row in self.summarize(queryset)
        )
        return self.csv_response(
            "donation-clicks-summary.csv",
            ["School", "Course", "Total clicks", "Unique learners"],
            rows,
        )

    @admin.action(description="Export clicks as CSV (one row per click)")
    def export_clicks_csv(self, request, queryset):
        rows = (
            (
                click.created.isoformat(),
                click.partner.name if click.partner else "",
                click.course_id,
                click.user.username if click.user else "",
            )
            for click in queryset.select_related("partner", "user").order_by("created")
        )
        return self.csv_response("donation-clicks.csv", ["Clicked at", "School", "Course", "Learner"], rows)


admin.site.register(Partner, PartnerAdmin)
admin.site.register(DonationClick, DonationClickAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(EnhancedCourse, EnhancedCourseAdmin)
admin.site.register(Center, CenterAdmin)
admin.site.register(HeroCourse, HeroCourseAdmin)
admin.site.register(PartnerOrganizationMapping, PartnerOrganizationMappingAdmin)
admin.site.register(CourseCreator, CourseCreatorAdmin)
