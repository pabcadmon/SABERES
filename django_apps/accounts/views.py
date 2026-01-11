from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.shortcuts import render, redirect
from .forms import SignupForm
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

def signup(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("generator:tables")
    else:
        form = SignupForm()

    return render(request, "registration/signup.html", {"form": form})
