from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import UserSubjectAccess


@login_required
def me(request):
    accesses = (
        UserSubjectAccess.objects
        .select_related("subject")
        .filter(user=request.user)
        .order_by("subject__code")
    )

    return render(request, "accounts/me.html", {"accesses": accesses})
