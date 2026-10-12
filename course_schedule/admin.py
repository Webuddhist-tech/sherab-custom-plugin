from django.contrib import admin

from .models import CourseScheduleSettings, SectionSchedule


@admin.register(CourseScheduleSettings)
class CourseScheduleSettingsAdmin(admin.ModelAdmin):
    list_display = ("course_id", "timezone", "modified")
    search_fields = ("course_id",)
    readonly_fields = ("created", "modified")


@admin.register(SectionSchedule)
class SectionScheduleAdmin(admin.ModelAdmin):
    list_display = ("section_id", "course_id", "start_date", "num_days", "start_time", "end_time", "instructor")
    list_filter = ("start_date",)
    search_fields = ("course_id", "section_id", "instructor")
    readonly_fields = ("created", "modified", "updated_by")
