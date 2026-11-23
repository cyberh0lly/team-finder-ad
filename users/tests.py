from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.contrib.auth.forms import PasswordChangeForm
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .forms import UserProfileForm
from .models import Skill, User


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
        self.assertNotContains(response, 'href="/users/edit-profile/" class="black-button"')
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
        self.assertContains(response, 'href="/users/edit-profile/" class="black-button"')
        self.assertContains(response, 'Добавить проект')
        self.assertContains(response, 'id="add-skill-btn"')

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
        self.assertNotContains(response, 'href="/users/edit-profile/" class="black-button"')
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


class UserProfileEditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email='owner@example.com', name='Анна', surname='Иванова',
            avatar='avatars/old.png', phone='+79991234567',
        )
        cls.other = User.objects.create_user(
            email='other@example.com', name='Пётр', surname='Петров',
            avatar='avatars/other.png', phone='89997654321',
        )
        cls.url = reverse('users:edit_profile')

    def profile_data(self, **changes):
        data = {
            'name': 'Анна', 'surname': 'Смирнова', 'about': 'Изучаю Django',
            'phone': '89991234567', 'github_url': 'https://github.com/anna',
        }
        data.update(changes)
        return data

    def test_guest_cannot_get_or_submit_form(self):
        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method(self.url)
                self.assertRedirects(
                    response, f'{reverse("users:login")}?next={self.url}',
                )

    def test_get_has_initial_values_and_only_allowed_fields(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/edit_profile.html')
        form = response.context['form']
        self.assertFalse(form.is_bound)
        self.assertEqual(form.instance, self.user)
        self.assertEqual(form.initial['phone'], self.user.phone)
        self.assertEqual(form.initial['name'], self.user.name)
        self.assertEqual(
            tuple(form.fields),
            ('name', 'surname', 'avatar', 'about', 'phone', 'github_url'),
        )
        self.assertContains(response, 'enctype="multipart/form-data"')

    def test_post_updates_only_current_user_and_preserves_avatar(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, self.profile_data(
            id=self.other.pk, email='changed@example.com', is_staff='on',
            password='new-password',
        ))
        self.assertRedirects(
            response, reverse('users:user_detail', args=[self.user.pk]),
        )
        password = self.user.password
        self.user.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual(self.user.surname, 'Смирнова')
        self.assertEqual(self.user.phone, '+79991234567')
        self.assertEqual(self.user.about, 'Изучаю Django')
        self.assertEqual(self.user.github_url, 'https://github.com/anna')
        self.assertEqual(self.user.avatar.name, 'avatars/old.png')
        self.assertEqual(self.user.email, 'owner@example.com')
        self.assertEqual(self.user.password, password)
        self.assertFalse(self.user.is_staff)
        self.assertEqual(self.other.surname, 'Петров')

    def test_phone_formats_and_duplicates(self):
        for phone in ('89991234567', '+79991234567', ''):
            with self.subTest(valid=phone):
                form = UserProfileForm(
                    self.profile_data(phone=phone), instance=self.user,
                )
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(
                    form.cleaned_data['phone'], '+79991234567' if phone else '',
                )
        for phone in ('123', '+7999 1234567', '79991234567', '8abcdefghij'):
            with self.subTest(invalid=phone):
                form = UserProfileForm(
                    self.profile_data(phone=phone), instance=self.user,
                )
                self.assertFalse(form.is_valid())
                self.assertIn('phone', form.errors)
        for stored in ('89997654321', '+79997654321'):
            User.objects.filter(pk=self.other.pk).update(phone=stored)
            for phone in ('89997654321', '+79997654321'):
                with self.subTest(stored=stored, submitted=phone):
                    form = UserProfileForm(
                        self.profile_data(phone=phone), instance=self.user,
                    )
                    self.assertFalse(form.is_valid())
                    self.assertIn('уже используется', form.errors['phone'][0])

    def test_github_validation(self):
        for url in ('', 'https://github.com/anna', 'http://github.com/anna'):
            with self.subTest(valid=url):
                form = UserProfileForm(
                    self.profile_data(github_url=url), instance=self.user,
                )
                self.assertTrue(form.is_valid(), form.errors)
        for url in (
            'not a url', 'https://example.com',
            'https://github.com.example.com/anna',
            'https://github.com@example.com/anna', 'ftp://github.com/anna',
        ):
            with self.subTest(invalid=url):
                form = UserProfileForm(
                    self.profile_data(github_url=url), instance=self.user,
                )
                self.assertFalse(form.is_valid())
                self.assertIn('github_url', form.errors)

    def test_invalid_post_displays_errors_without_saving(self):
        self.client.force_login(self.user)
        for changes, field in (
            ({'phone': '123'}, 'phone'),
            ({'phone': '+79997654321'}, 'phone'),
            ({'github_url': 'https://example.com'}, 'github_url'),
        ):
            with self.subTest(field=field, changes=changes):
                response = self.client.post(self.url, self.profile_data(**changes))
                self.assertEqual(response.status_code, 200)
                form = response.context['form']
                self.assertIn(field, form.errors)
                self.assertContains(response, form.errors[field][0])
                self.assertEqual(form['surname'].value(), 'Смирнова')
                self.user.refresh_from_db()
                self.assertEqual(self.user.surname, 'Иванова')

    def test_avatar_upload(self):
        self.client.force_login(self.user)
        image = BytesIO()
        Image.new('RGB', (10, 10), 'blue').save(image, format='PNG')
        upload = SimpleUploadedFile(
            'new.png', image.getvalue(), content_type='image/png',
        )
        with TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    self.url, self.profile_data(avatar=upload),
                )
                self.assertRedirects(
                    response, reverse('users:user_detail', args=[self.user.pk]),
                )
                self.user.refresh_from_db()
                self.assertTrue(self.user.avatar.name.startswith('avatars/new'))
                self.assertTrue(self.user.avatar.storage.exists(self.user.avatar.name))

    def test_invalid_image_is_rejected(self):
        self.client.force_login(self.user)
        upload = SimpleUploadedFile(
            'fake.png', b'not an image', content_type='image/png',
        )
        response = self.client.post(self.url, self.profile_data(avatar=upload))
        self.assertEqual(response.status_code, 200)
        self.assertIn('avatar', response.context['form'].errors)
        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar.name, 'avatars/old.png')


class ChangePasswordTests(TestCase):
    old_password = 'Old-TeamFinder-42!'
    new_password = 'New-TeamFinder-73!'

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email='password@example.com', password=cls.old_password,
            name='Анна', surname='Иванова', avatar='avatars/anna.png',
        )
        cls.url = reverse('users:change_password')

    def password_data(self, **changes):
        data = {
            'old_password': self.old_password,
            'new_password1': self.new_password,
            'new_password2': self.new_password,
        }
        data.update(changes)
        return data

    def test_guest_is_redirected_to_login(self):
        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method(self.url)
                self.assertRedirects(
                    response, f'{reverse("users:login")}?next={self.url}',
                )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.old_password))

    def test_authenticated_get_shows_standard_form(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/change_password.html')
        form = response.context['form']
        self.assertIsInstance(form, PasswordChangeForm)
        self.assertFalse(form.is_bound)
        self.assertEqual(
            tuple(form.fields),
            ('old_password', 'new_password1', 'new_password2'),
        )
        for field in form.fields:
            self.assertContains(response, f'name="{field}"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'Сохранить пароль')

    def test_invalid_passwords_show_errors_without_saving(self):
        self.client.force_login(self.user)
        for changes, field, code in (
            ({'old_password': 'wrong'}, 'old_password', 'password_incorrect'),
            ({'new_password2': 'different'}, 'new_password2', 'password_mismatch'),
        ):
            with self.subTest(field=field):
                response = self.client.post(self.url, self.password_data(**changes))
                self.assertEqual(response.status_code, 200)
                form = response.context['form']
                self.assertEqual(form.errors.as_data()[field][0].code, code)
                self.assertContains(response, form.errors[field][0])
                self.user.refresh_from_db()
                self.assertTrue(self.user.check_password(self.old_password))

    @override_settings(AUTH_PASSWORD_VALIDATORS=[{
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 12},
    }])
    def test_configured_password_validator_is_used(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, self.password_data(
            new_password1='Short1!', new_password2='Short1!',
        ))
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(
            form.errors.as_data()['new_password2'][0].code, 'password_too_short',
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.old_password))

    def test_password_changes_and_session_stays_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, self.password_data())
        self.assertRedirects(
            response, reverse('users:user_detail', args=[self.user.pk]),
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))
        self.assertFalse(self.user.check_password(self.old_password))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.user.pk, self.user.pk)
        self.client.logout()
        self.assertFalse(self.client.login(
            email=self.user.email, password=self.old_password,
        ))
        self.assertTrue(self.client.login(
            email=self.user.email, password=self.new_password,
        ))


class SkillTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email='skills@example.com', name='Анна', surname='Иванова',
            avatar='avatars/anna.png',
        )
        cls.other = User.objects.create_user(
            email='other-skills@example.com', name='Пётр', surname='Петров',
            avatar='avatars/petr.png',
        )
        cls.python = Skill.objects.create(name='Python')

    def test_skill_name_and_validation(self):
        self.assertEqual(str(self.python), 'Python')
        Skill(name='A' * 124).full_clean()
        for name in ('', 'A' * 125):
            with self.subTest(name=name):
                with self.assertRaises(ValidationError):
                    Skill(name=name).full_clean()

    def test_user_can_have_no_skills(self):
        self.assertFalse(self.user.skills.exists())

    def test_many_to_many_relationship_and_reverse_lookup(self):
        django = Skill.objects.create(name='Django')
        self.user.skills.add(self.python, django)
        self.other.skills.add(self.python)
        self.assertCountEqual(self.user.skills.all(), [self.python, django])
        self.assertCountEqual(self.other.skills.all(), [self.python])
        self.assertCountEqual(self.python.users.all(), [self.user, self.other])
        self.assertCountEqual(django.users.all(), [self.user])

    def test_exact_duplicate_is_rejected_by_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Skill.objects.create(name='Python')


class SkillManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            email='skill-owner@example.com', name='Анна', surname='Иванова',
            avatar='avatars/anna.png',
        )
        cls.other = User.objects.create_user(
            email='skill-other@example.com', name='Пётр', surname='Петров',
            avatar='avatars/petr.png',
        )
        cls.skill = Skill.objects.create(name='Python')
        cls.add_url = reverse('users:add_skill', args=[cls.owner.pk])
        cls.remove_url = reverse('users:remove_skill', args=[cls.owner.pk, cls.skill.pk])
        cls.profile_url = reverse('users:user_detail', args=[cls.owner.pk])

    def test_profile_skills_and_owner_controls(self):
        self.owner.skills.add(self.skill)
        for viewer in (None, self.other, self.owner):
            with self.subTest(viewer=viewer):
                self.client.logout()
                if viewer:
                    self.client.force_login(viewer)
                response = self.client.get(self.profile_url)
                self.assertContains(response, 'Python')
                self.assertNotContains(response, 'Навыки не указаны')
                for control in ('id="add-skill-btn"', 'class="remove-skill-btn"'):
                    if viewer == self.owner:
                        self.assertContains(response, control)
                    else:
                        self.assertNotContains(response, control)

    def test_autocomplete_prefix_order_and_limit(self):
        for number in reversed(range(12)):
            Skill.objects.create(name=f'Py{number:02}')
        Skill.objects.create(name='NotPython')
        response = self.client.get(reverse('users:skill_list'), {'q': 'Py'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item['name'] for item in response.json()],
            [f'Py{number:02}' for number in range(10)],
        )
        self.assertEqual(set(response.json()[0]), {'id', 'name'})
        self.assertEqual(self.client.get(
            reverse('users:skill_list'), {'q': 'missing'},
        ).json(), [])

    def test_add_existing_and_repeat(self):
        self.client.force_login(self.owner)
        for added in (True, False):
            response = self.client.post(
                self.add_url, {'skill_id': self.skill.pk}, content_type='application/json',
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {
                'skill_id': self.skill.pk, 'created': False, 'added': added,
            })
        self.assertEqual(self.owner.skills.count(), 1)
        self.assertEqual(Skill.objects.count(), 1)

    def test_create_by_name_and_reuse(self):
        self.client.force_login(self.owner)
        for created in (True, False):
            response = self.client.post(
                self.add_url, {'name': '  Django  '}, content_type='application/json',
            )
            self.assertEqual(response.status_code, 200)
            skill = Skill.objects.get(name='Django')
            self.assertEqual(response.json(), {
                'skill_id': skill.pk, 'created': created, 'added': created,
            })
        self.assertEqual(self.owner.skills.count(), 1)

    def test_invalid_payload_and_missing_objects(self):
        self.client.force_login(self.owner)
        for data in ({}, [], {'name': ''}, {'name': '   '}, {'name': 'x' * 125},
                     {'name': 3}, {'skill_id': 'bad'}, {'skill_id': None}):
            with self.subTest(data=data):
                response = self.client.post(self.add_url, data, content_type='application/json')
                self.assertEqual(response.status_code, 400)
        response = self.client.post(self.add_url, '{', content_type='application/json')
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            self.add_url, {'skill_id': 999999}, content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            reverse('users:add_skill', args=[999999]),
            {'name': 'Django'}, content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(self.owner.skills.exists())

    def test_only_owner_can_modify_skills(self):
        self.owner.skills.add(self.skill)
        for viewer in (None, self.other):
            self.client.logout()
            if viewer:
                self.client.force_login(viewer)
            for url in (self.add_url, self.remove_url):
                with self.subTest(viewer=viewer, url=url):
                    response = self.client.post(
                        url, {'name': 'Forbidden'}, content_type='application/json',
                    )
                    self.assertEqual(response.status_code, 403)
        self.assertFalse(Skill.objects.filter(name='Forbidden').exists())
        self.assertTrue(self.owner.skills.filter(pk=self.skill.pk).exists())

    def test_remove_only_relationship(self):
        self.owner.skills.add(self.skill)
        self.other.skills.add(self.skill)
        self.client.force_login(self.owner)
        response = self.client.post(self.remove_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.owner.skills.exists())
        self.assertTrue(Skill.objects.filter(pk=self.skill.pk).exists())
        self.assertTrue(self.other.skills.filter(pk=self.skill.pk).exists())
        self.assertEqual(self.client.post(self.remove_url).status_code, 404)

    def test_methods_and_csrf_protection(self):
        self.client.force_login(self.owner)
        for url in (self.add_url, self.remove_url):
            self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(reverse('users:skill_list')).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        for url in (self.add_url, self.remove_url):
            self.assertEqual(client.post(url).status_code, 403)
        client.get(self.profile_url)
        token = client.cookies['csrftoken'].value
        response = client.post(
            self.add_url, {'skill_id': self.skill.pk}, content_type='application/json',
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.post(self.remove_url, HTTP_X_CSRFTOKEN=token).status_code, 200)


class ParticipantListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.members = [
            User.objects.create_user(
                email=f'participant{number}@example.com',
                name=f'Участник {number}', surname='Тестовый',
                avatar=f'avatars/member{number}.png',
            )
            for number in range(25)
        ]
        cls.python = Skill.objects.create(name='Python')
        cls.special = Skill.objects.create(name='C++ & веб')
        cls.unused = Skill.objects.create(name='Django')
        for member in cls.members[:13]:
            member.skills.add(cls.python, cls.special)
        cls.url = reverse('users:user_list')

    def test_guest_sees_ordered_users_and_profile_links(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/participants.html')
        self.assertQuerySetEqual(
            response.context['participants'], [user.pk for user in self.members],
            transform=lambda user: user.pk,
        )
        self.assertEqual(list(response.context['page_obj']), self.members[:12])
        self.assertContains(response, 'class="participant-card"', count=12)
        self.assertContains(response, self.members[0].avatar.url)
        self.assertContains(response, 'Участник 0 Тестовый')
        for member in self.members[:12]:
            self.assertContains(response, f'href="{reverse("users:user_detail", args=[member.pk])}"')
        self.assertEqual(
            list(response.context['all_skills']), [self.special, self.unused, self.python],
        )
        self.assertNotContains(response, 'class="filter-reset"')

    def test_exact_skill_filter_and_reset(self):
        response = self.client.get(self.url, {'skill': 'Python'})
        self.assertEqual(response.context['page_obj'].paginator.count, 13)
        self.assertQuerySetEqual(
            response.context['participants'], [user.pk for user in self.members[:13]],
            transform=lambda user: user.pk,
        )
        self.assertContains(
            response, '<a href="?skill=Python" class="filter-chip active">Python</a>', html=True,
        )
        self.assertContains(
            response, f'<a href="{self.url}" class="filter-reset">Сбросить</a>', html=True,
        )
        reset = self.client.get(self.url)
        self.assertEqual(reset.context['page_obj'].paginator.count, 25)

    def test_unknown_or_partial_skill_has_empty_results(self):
        for skill in ('Unknown', 'Py', 'python', 'Django'):
            with self.subTest(skill=skill):
                response = self.client.get(self.url, {'skill': skill})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(list(response.context['page_obj']), [])
                self.assertContains(response, 'Участники с этим навыком не найдены')

    def test_pagination_and_invalid_page_numbers(self):
        for page, expected in (
            ('1', self.members[:12]), ('2', self.members[12:24]),
            ('3', self.members[24:]), ('bad', self.members[:12]),
            ('999', self.members[24:]), ('0', self.members[24:]),
        ):
            with self.subTest(page=page):
                response = self.client.get(self.url, {'page': page})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(list(response.context['page_obj']), expected)

    def test_filtered_pagination_preserves_encoded_skill(self):
        from urllib.parse import urlencode

        for skill in (self.python, self.special):
            with self.subTest(skill=skill.name):
                response = self.client.get(self.url, {'skill': skill.name})
                prefix = urlencode({'skill': skill.name})
                self.assertContains(response, f'href="?{prefix}&amp;page=2"')
                response = self.client.get(self.url, {'skill': skill.name, 'page': 2})
                self.assertEqual(list(response.context['page_obj']), self.members[12:13])
                self.assertContains(response, f'href="?{prefix}&amp;page=1"')

    def test_empty_database(self):
        User.objects.all().delete()
        Skill.objects.all().delete()
        response = self.client.get(self.url)
        self.assertContains(response, 'Пока нет участников')
        self.assertEqual(list(response.context['page_obj']), [])
        self.assertNotContains(response, 'class="pagination"')

    def test_empty_optional_profile_fields(self):
        User.objects.filter(pk=self.members[0].pk).update(avatar='', about='')
        response = self.client.get(self.url)
        self.assertContains(response, 'images/default-avatar.png')
        self.assertContains(response, 'Участник 0 Тестовый')


class UserWorkflowTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings_override = self.settings(MEDIA_ROOT=media.name)
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        self.user = User.objects.create_user(
            email='workflow@example.com', password='Workflow-Secret-42!',
            name='Анна', surname='Иванова', avatar='avatars/a.png',
        )

    def test_registration_login_and_profile_edit(self):
        response = self.client.post(reverse('users:register'), {
            'email': 'new@example.com', 'name': 'Мария', 'surname': 'Петрова',
            'password1': 'Registration-Secret-42!', 'password2': 'Registration-Secret-42!',
            'is_staff': True, 'is_superuser': True,
        })
        self.assertRedirects(response, reverse('users:login'))
        user = User.objects.get(email='new@example.com')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(user.avatar.storage.exists(user.avatar.name))
        response = self.client.post(reverse('users:login'), {
            'email': user.email, 'password': 'Registration-Secret-42!',
        })
        self.assertRedirects(response, reverse('projects:project_list'))
        profile_url = reverse('users:user_detail', args=[user.pk])
        self.assertContains(self.client.get(profile_url), 'Мария Петрова')
        response = self.client.post(reverse('users:edit_profile'), {
            'name': 'Мария', 'surname': 'Смирнова', 'about': 'Учусь Django',
            'phone': '89991234567', 'github_url': 'https://github.com/maria',
        })
        self.assertRedirects(response, profile_url)
        user.refresh_from_db()
        self.assertEqual(user.phone, '+79991234567')
        self.assertContains(self.client.get(profile_url), 'Мария Смирнова')
        self.assertContains(self.client.get(profile_url), 'Учусь Django')

    def test_skill_profile_filter_and_remove_workflow(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('users:add_skill', args=[self.user.pk]),
                                    {'name': 'WorkflowPython'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        skill_id = response.json()['skill_id']
        self.assertContains(self.client.get(reverse('users:user_detail', args=[self.user.pk])), 'WorkflowPython')
        response = self.client.get(reverse('users:user_list'), {'skill': 'WorkflowPython'})
        self.assertEqual(list(response.context['page_obj']), [self.user])
        response = self.client.post(reverse('users:remove_skill', args=[self.user.pk, skill_id]))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('users:user_list'), {'skill': 'WorkflowPython'})
        self.assertEqual(list(response.context['page_obj']), [])
        self.assertNotContains(self.client.get(reverse('users:user_detail', args=[self.user.pk])), 'WorkflowPython')
        self.assertTrue(Skill.objects.filter(pk=skill_id).exists())

    def test_empty_auth_posts_show_required_errors(self):
        for route in ('users:register', 'users:login'):
            with self.subTest(route=route):
                response = self.client.post(reverse(route), {})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].is_bound)
                self.assertIn('email', response.context['form'].errors)
        self.assertEqual(User.objects.count(), 1)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_invalid_login_and_registration_do_not_authenticate(self):
        response = self.client.post(reverse('users:login'), {
            'email': self.user.email, 'password': 'wrong',
        })
        self.assertTrue(response.context['form'].non_field_errors())
        response = self.client.post(reverse('users:register'), {
            'email': self.user.email, 'name': 'Анна', 'surname': 'Иванова',
            'password1': 'Test-Secret-42!', 'password2': 'Different-Secret-42!',
        })
        self.assertIn('email', response.context['form'].errors)
        self.assertIn('password2', response.context['form'].errors)
        self.assertEqual(User.objects.count(), 1)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_requires_post_and_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        url = reverse('users:logout')
        self.assertEqual(client.get(url).status_code, 405)
        self.assertEqual(client.post(url).status_code, 403)
        self.assertEqual(client.session['_auth_user_id'], str(self.user.pk))
        client.get(reverse('users:user_detail', args=[self.user.pk]))
        response = client.post(url, HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertRedirects(response, reverse('users:login'))
        self.assertNotIn('_auth_user_id', client.session)

    def test_user_forms_reject_missing_csrf(self):
        client = Client(enforce_csrf_checks=True)
        for route in ('users:register', 'users:login'):
            self.assertEqual(client.post(reverse(route), {}).status_code, 403)
            self.assertContains(client.get(reverse(route)), 'name="csrfmiddlewaretoken"')
        client.force_login(self.user)
        for route in ('users:edit_profile', 'users:change_password'):
            self.assertEqual(client.post(reverse(route), {}).status_code, 403)
            self.assertContains(client.get(reverse(route)), 'name="csrfmiddlewaretoken"')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Workflow-Secret-42!'))

    def test_password_post_cannot_target_another_user(self):
        other = User.objects.create_user(
            email='other-workflow@example.com', password='Other-Secret-42!',
            name='Пётр', surname='Петров', avatar='avatars/p.png',
        )
        self.client.force_login(self.user)
        response = self.client.post(reverse('users:change_password'), {
            'id': other.pk, 'user_id': other.pk,
            'old_password': 'Workflow-Secret-42!',
            'new_password1': 'Changed-Secret-93!', 'new_password2': 'Changed-Secret-93!',
        })
        self.assertRedirects(response, reverse('users:user_detail', args=[self.user.pk]))
        other.refresh_from_db()
        self.user.refresh_from_db()
        self.assertTrue(other.check_password('Other-Secret-42!'))
        self.assertTrue(self.user.check_password('Changed-Secret-93!'))

    def test_profile_and_password_get_ignore_submitted_changes(self):
        self.client.force_login(self.user)
        before = User.objects.values().get(pk=self.user.pk)
        for route in ('users:edit_profile', 'users:change_password'):
            response = self.client.get(reverse(route), {
                'name': 'Changed', 'old_password': 'Workflow-Secret-42!',
                'new_password1': 'Changed-Secret-93!', 'new_password2': 'Changed-Secret-93!',
            })
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context['form'].is_bound)
            self.assertEqual(User.objects.values().get(pk=self.user.pk), before)

    def test_missing_skill_on_removal(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('users:remove_skill', args=[self.user.pk, 999999]))
        self.assertEqual(response.status_code, 404)
