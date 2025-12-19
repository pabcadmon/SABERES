from django.core.exceptions import PermissionDenied
from django_apps.accounts.models import Subject, UserSubjectAccess


def require_subject_access(user, subject_code: str) -> Subject:
    try:
        subject = Subject.objects.get(code=subject_code, is_active=True)
    except Subject.DoesNotExist:
        raise PermissionDenied("Asignatura no disponible.")

    has_access = UserSubjectAccess.objects.filter(user=user, subject=subject).exists()
    if not has_access:
        raise PermissionDenied("No tienes acceso a esta asignatura.")

    return subject
