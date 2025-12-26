import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

if not username or not password:
    # No env vars -> do nothing
    raise SystemExit(0)

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Created superuser: {username}")
else:
    print(f"Superuser already exists: {username}")
