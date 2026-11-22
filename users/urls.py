from django.urls import path

from . import views

app_name = 'users'

urlpatterns = [
    path('list/', views.user_list, name='user_list'),
    path('skills/', views.skill_list, name='skill_list'),
    path('<int:user_id>/skills/add', views.add_skill, name='add_skill'),
    path('<int:user_id>/skills/add/', views.add_skill),
    path('<int:user_id>/skills/<int:skill_id>/remove/',
         views.remove_skill, name='remove_skill'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('change-password/', views.change_password, name='change_password'),
    path('<int:user_id>/', views.user_detail, name='user_detail'),
]
