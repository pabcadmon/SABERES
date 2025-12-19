from django.core.management.base import BaseCommand
from django.db import transaction

from django_apps.accounts.models import Subject


DEFAULT_SUBJECTS = [
    ("1ESO_GeH", "Geografía e Historia 1º ESO"),
    ("3ESO_GeH", "Geografía e Historia 3º ESO"),
    ("1ESO_LyL", "Lengua Castellana y Literatura 1º ESO"),
]


class Command(BaseCommand):
    help = "Crea/actualiza asignaturas por defecto (Subject)."

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        updated = 0

        for code, name in DEFAULT_SUBJECTS:
            obj, was_created = Subject.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "dataset_path": f"data/{code}.xlsx",
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Subjects creadas: {created}, actualizadas: {updated}"
            )
        )
