from django.db import migrations

def forward(apps, schema_editor):
    ExportJob = apps.get_model("generator", "ExportJob")
    Subject = apps.get_model("accounts", "Subject")

    # Para cada export antiguo, asigna subject buscando por code = subject_code
    for job in ExportJob.objects.all():
        if job.subject_id is not None:
            continue

        code = getattr(job, "subject_code", None)
        if not code:
            continue

        subj = Subject.objects.filter(code=code).first()
        if subj:
            job.subject_id = subj.id
            job.save(update_fields=["subject"])

def backward(apps, schema_editor):
    ExportJob = apps.get_model("generator", "ExportJob")
    ExportJob.objects.update(subject=None)

class Migration(migrations.Migration):

    dependencies = [
        ("generator", "0003_remove_exportjob_subject_code_exportjob_subject_and_more"),   # <-- deja el nombre que te haya creado Django
        ("accounts", "0002_subject_dataset_path"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
