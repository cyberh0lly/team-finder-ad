from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import AdminUserChangeForm, AdminUserCreationForm
from .models import Skill, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = AdminUserChangeForm
    add_form = AdminUserCreationForm
    list_display = ('email', 'name', 'surname', 'is_active', 'is_staff')
    search_fields = ('email', 'name', 'surname')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    ordering = ('email',)
    filter_horizontal = ('skills', 'groups', 'user_permissions')
    readonly_fields = ('last_login',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Профиль', {
            'fields': ('name', 'surname', 'avatar', 'about', 'phone', 'github_url', 'skills'),
        }),
        ('Права доступа', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Последний вход', {'fields': ('last_login',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'surname', 'password1', 'password2'),
        }),
    )


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    search_fields = ('name',)
