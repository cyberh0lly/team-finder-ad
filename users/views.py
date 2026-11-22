from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import UserLoginForm, UserRegistrationForm
from .models import User


def user_list(request):
    return render(request, 'users/participants.html')


def user_detail(request, user_id):
    user = get_object_or_404(User, id=user_id)
    return render(
        request,
        'users/user-details.html',
        {'user': user},
    )


def login_view(request):
    form = UserLoginForm(
        request.POST or None,
        request=request,
    )

    if request.method == 'POST' and form.is_valid():
        auth_login(request, form.user)
        return redirect('projects:project_list')

    return render(
        request,
        'users/login.html',
        {'form': form},
    )


def register(request):
    form = UserRegistrationForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('users:login')

    return render(
        request,
        'users/register.html',
        {'form': form},
    )

@require_POST
def logout_view(request):
    auth_logout(request)
    return redirect('users:login')
