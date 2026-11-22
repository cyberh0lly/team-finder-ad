from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

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
