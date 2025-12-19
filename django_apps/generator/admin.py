from django.contrib import admin
from .models import ExportJob


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "subject", "status")
    search_fields = ("user__username", "subject__code", "subject__name", "codes_raw")
    list_filter = ("status", "subject")
