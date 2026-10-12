from django.shortcuts import render


def project_list(request):
    return render(request, 'projects/project_list.html')


def project_detail(request, project_id):
    return render(request, 'projects/project-details.html')