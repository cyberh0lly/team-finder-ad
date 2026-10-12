from django.shortcuts import render
from django.shortcuts import redirect, render
from .forms import UserRegistrationForm

def user_list(request):
    return render(request, 'users/participants.html')

def user_detail(request, user_id):
    return render(request, 'users/user-details.html')

def login_view(request):
    return render(request, 'users/login.html')


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