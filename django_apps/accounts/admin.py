from django.contrib import admin
from .models import Subject, UserSubjectAccess


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "dataset_path", "is_active", "created_at")
    search_fields = ("code", "name")
    list_filter = ("is_active",)


@admin.register(UserSubjectAccess)
class UserSubjectAccessAdmin(admin.ModelAdmin):
    list_display = ("user", "subject", "granted_at")
    search_fields = ("user__username", "subject__code", "subject__name")
