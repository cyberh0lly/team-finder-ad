from urllib.parse import urlsplit

from django import forms

from .models import Project


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ('name', 'description', 'github_url', 'status')
        labels = {
            'name': 'Название проекта',
            'description': 'Описание',
            'github_url': 'Ссылка на GitHub',
            'status': 'Статус',
        }
        error_messages = {
            'name': {
                'required': 'Введите название проекта.',
                'max_length': (
                    'Название проекта не должно превышать 200 символов.'
                ),
            },
            'github_url': {'invalid': 'Введите корректную ссылку на GitHub.'},
            'status': {
                'required': 'Выберите статус проекта.',
                'invalid_choice': 'Выберите статус «Открыт» или «Закрыт».',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {'open': 'Открыт', 'closed': 'Закрыт'}
        self.fields['status'].choices = [
            (value, labels.get(value, label))
            for value, label in Project._meta.get_field('status').choices
        ]

    def clean_github_url(self):
        github_url = self.cleaned_data['github_url']
        if not github_url:
            return github_url
        url = urlsplit(github_url)
        if url.scheme not in ('http', 'https') or url.hostname != 'github.com':
            raise forms.ValidationError('Укажите ссылку на сайт github.com.')
        return github_url
