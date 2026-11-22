from django.test import TestCase
from django.urls import reverse

from .models import User


class UserDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            id=1,
            email='anna@example.com',
            name='Анна',
            surname='Иванова',
            avatar='avatars/anna.png',
            about='Изучаю Django',
            phone='+79991234567',
            github_url='https://github.com/anna',
        )
        cls.other_user = User.objects.create_user(
            email='petr@example.com',
            name='Пётр',
            surname='Петров',
            avatar='avatars/petr.png',
        )
        cls.url = reverse('users:user_detail', args=[cls.user.id])

    def test_guest_sees_requested_profile(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/user-details.html')
        self.assertEqual(response.context['user'], self.user)
        for value in (
            'Анна Иванова', self.user.avatar.url, self.user.about,
            self.user.email, self.user.phone, self.user.github_url,
        ):
            with self.subTest(value=value):
                self.assertContains(response, value)
        self.assertNotContains(response, 'href="/users/edit-profile"')
        self.assertNotContains(response, 'Добавить проект')
        self.assertContains(response, '<h3>Навыки</h3>', html=True)
        self.assertContains(response, 'Навыки не указаны')
        self.assertContains(response, 'Пока нет проектов')

    def test_missing_user_returns_404(self):
        response = self.client.get(
            reverse('users:user_detail', args=[999999]),
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_sees_profile_actions(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, 'href="/users/edit-profile"')
        self.assertContains(response, 'Добавить проект')
        self.assertNotContains(response, 'id="add-skill-btn"')

    def test_other_user_sees_profile_without_edit_actions(self):
        self.client.force_login(self.other_user)
        response = self.client.get(self.url)
        self.assertEqual(response.context['user'], self.user)
        self.assertContains(
            response,
            '<h2 class="profile-name">Анна Иванова</h2>',
            html=True,
        )
        self.assertContains(
            response,
            '<span class="username">Пётр Петров</span>',
            html=True,
        )
        self.assertNotContains(response, 'href="/users/edit-profile"')
        self.assertNotContains(response, 'Добавить проект')

    def test_empty_optional_fields(self):
        # update() позволяет проверить отсутствие аватара без его генерации.
        User.objects.filter(pk=self.user.pk).update(
            avatar='', about='', phone='', github_url='',
        )
        response = self.client.get(self.url)
        self.assertContains(response, 'images/default-avatar.png')
        self.assertContains(response, 'Описание профиля пока не добавлено.')
        self.assertNotContains(response, self.user.phone)
        self.assertNotContains(response, self.user.github_url)
