import re
from urllib.parse import urlsplit

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm

from .models import User


class UserRegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('email', 'name', 'surname')


class UserLoginForm(forms.Form):
    email = forms.EmailField(label='Email')
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput,
    )

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.user = None

    def clean(self):
        cleaned_data = super().clean()

        email = cleaned_data.get('email')
        password = cleaned_data.get('password')

        if email and password:
            self.user = authenticate(
                request=self.request,
                username=email,
                password=password,
            )

            if self.user is None:
                raise forms.ValidationError(
                    'Неверный имейл или пароль'
                )

        return cleaned_data


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('name', 'surname', 'avatar', 'about', 'phone', 'github_url')
        labels = {
            'name': 'Имя',
            'surname': 'Фамилия',
            'avatar': 'Аватар',
            'about': 'О себе',
            'phone': 'Телефон',
            'github_url': 'Ссылка на GitHub',
        }
        widgets = {
            'avatar': forms.FileInput(attrs={'accept': 'image/*'}),
            'about': forms.Textarea(attrs={'rows': 4}),
        }

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if not phone:
            return phone
        if not re.fullmatch(r'(?:8|\+7)[0-9]{10}', phone):
            raise forms.ValidationError(
                'Введите телефон в формате 8XXXXXXXXXX или +7XXXXXXXXXX.'
            )
        number = phone[-10:]
        # Проверяем оба формата, включая ранее сохранённые номера с 8.
        duplicates = User.objects.filter(
            phone__in=(f'8{number}', f'+7{number}'),
        ).exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError(
                'Этот номер телефона уже используется другим пользователем.'
            )
        return f'+7{number}'

    def clean_github_url(self):
        github_url = self.cleaned_data['github_url']
        if not github_url:
            return github_url
        url = urlsplit(github_url)
        if url.scheme not in ('http', 'https') or url.hostname != 'github.com':
            raise forms.ValidationError('Укажите ссылку на сайт github.com.')
        return github_url
