from django.conf import settings
from django.db import models
from django_apps.accounts.models import Subject

class ExportJob(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name="export_jobs",
    )

    # lo que escribió el usuario en el textarea (tal cual)
    codes_raw = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.FAILED)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    output_file = models.FileField(upload_to="exports/%Y/%m/%d/", blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.user.username} {self.subject.code} {self.status}"


class secuenciacionPlan(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="secuenciacions")
    name = models.CharField(max_length=120, default="secuenciacion")
    units = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user.username} {self.subject.code} {self.name}"

