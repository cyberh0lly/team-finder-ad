from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ProjectForm
from .models import Project


def project_list(request):
    projects = Project.objects.select_related('owner').prefetch_related(
        'participants',
    ).order_by('-created_at', '-id')
    page_obj = Paginator(projects, 12).get_page(request.GET.get('page'))
    return render(
        request,
        'projects/project_list.html',
        {'projects': projects, 'page_obj': page_obj},
    )


def project_detail(request, project_id):
    project = get_object_or_404(
        Project.objects.select_related('owner').prefetch_related(
            'participants'
        ),
        pk=project_id,
    )
    return render(
        request, 'projects/project-details.html', {'project': project}
    )


@login_required(login_url='users:login')
def create_project(request):
    form = ProjectForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        project = form.save(commit=False)
        project.owner = request.user
        project.save()
        project.participants.add(request.user)
        return redirect('projects:project_detail', project_id=project.pk)
    return render(
        request,
        'projects/create-project.html',
        {'form': form, 'is_edit': False},
    )


@login_required(login_url='users:login')
def edit_project(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    if request.user != project.owner:
        raise PermissionDenied
    form = ProjectForm(
        request.POST if request.method == 'POST' else None,
        instance=project,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('projects:project_detail', project_id=project.pk)
    return render(
        request,
        'projects/create-project.html',
        {'form': form, 'is_edit': True},
    )


@require_POST
def complete_project(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    if not request.user.is_authenticated or request.user != project.owner:
        raise PermissionDenied
    if project.status != 'open':
        return JsonResponse({'error': 'Проект уже завершён.'}, status=400)
    project.status = 'closed'
    project.save(update_fields=['status'])
    return JsonResponse({'status': 'ok', 'project_status': 'closed'})


@require_POST
def toggle_participate(request, project_id):
    if not request.user.is_authenticated:
        return JsonResponse(
            {'error': 'Для участия необходимо войти в аккаунт.'}, status=403
        )
    try:
        project = get_object_or_404(Project, pk=project_id)
    except Http404:
        return JsonResponse({'error': 'Проект не найден.'}, status=404)
    if request.user.pk == project.owner_id:
        return JsonResponse(
            {'error': 'Автор не может отказаться от участия в своём проекте.'},
            status=403,
        )
    participating = project.participants.filter(pk=request.user.pk).exists()
    if participating:
        project.participants.remove(request.user)
    else:
        if project.status != 'open':
            return JsonResponse(
                {'error': 'Нельзя присоединиться к завершённому проекту.'},
                status=400,
            )
        project.participants.add(request.user)
    return JsonResponse({'status': 'ok', 'participating': not participating})
