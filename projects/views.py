from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

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
        Project.objects.select_related('owner').prefetch_related('participants'),
        pk=project_id,
    )
    return render(request, 'projects/project-details.html', {'project': project})


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
        request, 'projects/create-project.html', {'form': form, 'is_edit': False},
    )
