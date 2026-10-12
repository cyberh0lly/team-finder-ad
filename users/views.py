from django.shortcuts import render


def user_list(request):
    return render(request, 'users/participants.html')

def user_detail(request, user_id):
    return render(request, 'users/user-details.html')

def login_view(request):
    return render(request, 'users/login.html')


def register(request):
    return render(request, 'users/register.html')