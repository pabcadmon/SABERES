#!/usr/bin/env bash
set -e

python manage.py shell -c "
import os
from django.contrib.auth import get_user_model

User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL','')

if not username or not password:
    raise SystemExit(0)

u = User.objects.filter(username=username).first()
if u is None:
    User.objects.create_superuser(username=username, email=email, password=password)
    print('Created superuser:', username)
else:
    u.is_staff = True
    u.is_superuser = True
    if email:
        u.email = email
    u.set_password(password)
    u.save()
    print('Updated superuser password:', username)
"
