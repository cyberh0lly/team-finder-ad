from django.core.paginator import Paginator
from django.shortcuts import render

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
    return render(request, 'projects/project-details.html')
