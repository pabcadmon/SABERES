from django_apps.accounts.models import UserSubjectAccess


def demo_mode(request):
    user = getattr(request, "user", None)
    is_demo = False
    if user:
        if not user.is_authenticated:
            is_demo = True
        else:
            is_demo = not UserSubjectAccess.objects.filter(user=user).exists()
    return {"demo_mode": is_demo}
