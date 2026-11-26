import json
from urllib.parse import urlencode

from django import forms
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .forms import UserLoginForm, UserProfileForm, UserRegistrationForm
from .models import Skill, User


def user_list(request):
    active_skill = request.GET.get('skill', '')
    participants = User.objects.order_by('-id')
    if active_skill:
        participants = participants.filter(
            skills__name=active_skill
        ).distinct()
    page_obj = Paginator(participants, 12).get_page(request.GET.get('page'))
    context = {
        'participants': participants,
        'all_skills': Skill.objects.order_by('name'),
        'active_skill': active_skill,
        'page_obj': page_obj,
        'query_prefix': (
            urlencode({'skill': active_skill}) + '&' if active_skill else ''
        ),
    }
    return render(request, 'users/participants.html', context)


def user_detail(request, user_id):
    user = get_object_or_404(User, id=user_id)
    projects = user.owned_projects.prefetch_related('participants').order_by('-created_at', '-id')
    return render(
        request,
        'users/user-details.html',
        {'user': user, 'projects': projects},
    )


@require_GET
def skill_list(request):
    skills = Skill.objects.filter(
        name__istartswith=request.GET.get('q', '').strip(),
    ).order_by('name').values('id', 'name')[:10]
    return JsonResponse(list(skills), safe=False)


@require_POST
def add_skill(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if not request.user.is_authenticated or request.user.pk != user.pk:
        return JsonResponse(
            {'error': 'Можно менять только свои навыки.'}, status=403
        )
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'error': 'Некорректный JSON.'}, status=400)
    if not isinstance(data, dict):
        return JsonResponse(
            {'error': 'Ожидается объект с skill_id или name.'}, status=400
        )
    created = False
    if 'skill_id' in data:
        try:
            skill_id = forms.IntegerField(
                min_value=1, max_value=9223372036854775807,
            ).clean(data['skill_id'])
        except forms.ValidationError:
            return JsonResponse(
                {'error': 'Некорректный ID навыка.'}, status=400
            )
        skill = get_object_or_404(Skill, pk=skill_id)
    else:
        name = data.get('name')
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 124:
            return JsonResponse(
                {
                    'error': (
                        'Название навыка должно содержать '
                        'от 1 до 124 символов.'
                    )
                },
                status=400,
            )
        skill, created = Skill.objects.get_or_create(name=name.strip())
    added = not user.skills.filter(pk=skill.pk).exists()
    user.skills.add(skill)
    return JsonResponse(
        {'skill_id': skill.pk, 'created': created, 'added': added}
    )


@require_POST
def remove_skill(request, user_id, skill_id):
    user = get_object_or_404(User, pk=user_id)
    if not request.user.is_authenticated or request.user.pk != user.pk:
        return JsonResponse(
            {'error': 'Можно менять только свои навыки.'}, status=403
        )
    skill = get_object_or_404(user.skills, pk=skill_id)
    user.skills.remove(skill)
    return JsonResponse({'removed': True})


@login_required(login_url='users:login')
def edit_profile(request):
    form = UserProfileForm(
        request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None,
        instance=request.user,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('users:user_detail', user_id=request.user.id)
    return render(request, 'users/edit_profile.html', {'form': form})


@login_required(login_url='users:login')
def change_password(request):
    form = PasswordChangeForm(
        user=request.user,
        data=request.POST if request.method == 'POST' else None,
    )
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        return redirect('users:user_detail', user_id=user.id)
    return render(request, 'users/change_password.html', {'form': form})


def login_view(request):
    form = UserLoginForm(
        request.POST if request.method == 'POST' else None,
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
    form = UserRegistrationForm(
        request.POST if request.method == 'POST' else None
    )

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
