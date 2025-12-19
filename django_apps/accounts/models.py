from django.conf import settings
from django.db import models


class Subject(models.Model):
    # Ej: "GEH_1ESO", "LYL_1ESO"
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    dataset_path = models.CharField(max_length=255, blank=True, default="")

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class UserSubjectAccess(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "subject")

    def __str__(self) -> str:
        return f"{self.user.username} -> {self.subject.code}"
