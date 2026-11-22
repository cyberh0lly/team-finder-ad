from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Project


class ProjectTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(
            email='project-owner@example.com', name='Анна', surname='Иванова',
            avatar='avatars/anna.png',
        )
        cls.member = User.objects.create_user(
            email='project-member@example.com', name='Пётр', surname='Петров',
            avatar='avatars/petr.png',
        )
        cls.project = Project.objects.create(name='TeamFinder', owner=cls.owner)

    def test_creation_with_required_fields(self):
        self.project.full_clean()
        self.assertEqual(self.project.name, 'TeamFinder')
        self.assertEqual(self.project.owner, self.owner)
        self.assertEqual(self.project.description, '')
        self.assertEqual(self.project.github_url, '')
        self.assertEqual(self.project.status, 'open')
        self.assertEqual(str(self.project), 'TeamFinder')

    def test_creation_time_is_automatic_and_does_not_change_on_save(self):
        before = timezone.now()
        project = Project.objects.create(name='Новый проект', owner=self.owner)
        self.assertGreaterEqual(project.created_at, before)
        self.assertLessEqual(project.created_at, timezone.now())
        created_at = project.created_at
        project.name = 'Другое название'
        project.save()
        project.refresh_from_db()
        self.assertEqual(project.created_at, created_at)

    def test_closed_status_and_invalid_status(self):
        self.project.status = 'closed'
        self.project.full_clean()
        self.project.save()
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, 'closed')
        self.project.status = 'other'
        with self.assertRaises(ValidationError):
            self.project.full_clean()

    def test_owner_reverse_relationship(self):
        self.assertCountEqual(self.owner.owned_projects.all(), [self.project])
        self.assertFalse(self.member.owned_projects.exists())

    def test_participants_and_reverse_relationship(self):
        self.project.participants.add(self.member, self.owner)
        self.assertCountEqual(
            self.project.participants.all(), [self.member, self.owner],
        )
        self.assertCountEqual(self.member.participated_projects.all(), [self.project])
        another = Project.objects.create(name='Ещё проект', owner=self.owner)
        another.participants.add(self.member)
        self.assertCountEqual(
            self.member.participated_projects.all(), [self.project, another],
        )

    def test_project_can_have_no_participants(self):
        self.assertFalse(self.project.participants.exists())

    def test_deleting_owner_deletes_project(self):
        project_id = self.project.pk
        self.owner.delete()
        self.assertFalse(Project.objects.filter(pk=project_id).exists())


class ProjectListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            email='list-owner@example.com', name='Анна', surname='Иванова',
            avatar='avatars/anna.png',
        )
        cls.projects = [
            Project.objects.create(name=f'Проект {number}', owner=cls.owner)
            for number in range(13)
        ]
        # Даты намеренно не совпадают с порядком ID.
        created_at = timezone.now()
        for number, project in enumerate(cls.projects):
            Project.objects.filter(pk=project.pk).update(
                created_at=created_at - timedelta(days=number),
            )
        cls.url = reverse('projects:project_list')

    def test_guest_access_order_and_context(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/project_list.html')
        self.assertQuerySetEqual(
            response.context['projects'], [project.pk for project in self.projects],
            transform=lambda project: project.pk,
        )
        self.assertEqual(list(response.context['page_obj']), self.projects[:12])
        self.assertContains(response, 'class="project-card"', count=12)
        self.assertContains(response, 'href="?page=2"')

    def test_authenticated_access(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_last_page_and_invalid_page_numbers(self):
        for page, expected in (
            ('2', self.projects[12:]), ('bad', self.projects[:12]),
            ('999', self.projects[12:]), ('0', self.projects[12:]),
            ('-1', self.projects[12:]),
        ):
            with self.subTest(page=page):
                response = self.client.get(self.url, {'page': page})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(list(response.context['page_obj']), expected)

    def test_equal_dates_are_sorted_by_descending_id(self):
        Project.objects.update(created_at=timezone.now())
        response = self.client.get(self.url)
        self.assertEqual(list(response.context['page_obj']), self.projects[::-1][:12])

    def test_card_data_links_and_empty_optional_fields(self):
        project = self.projects[0]
        project.description = 'Описание учебного проекта'
        project.status = 'closed'
        project.save()
        project.participants.add(self.owner)
        get_user_model().objects.filter(pk=self.owner.pk).update(avatar='')
        response = self.client.get(self.url)
        for value in (
            project.name, project.description, 'Анна Иванова', 'Закрыт', 'Открыт',
            'images/default-avatar.png', 'Описание пока не добавлено.',
            f'href="{reverse("projects:project_detail", args=[project.pk])}"',
            f'href="{reverse("users:user_detail", args=[self.owner.pk])}"',
        ):
            with self.subTest(value=value):
                self.assertContains(response, value)
        project.refresh_from_db()
        self.assertContains(response, project.created_at.strftime('%d.%m.%Y'))
        self.assertEqual(response.context['page_obj'][0].participants.count(), 1)

    def test_empty_project_list(self):
        Project.objects.all().delete()
        response = self.client.get(self.url)
        self.assertContains(response, 'Пока нет проектов')
        self.assertEqual(list(response.context['page_obj']), [])
        self.assertNotContains(response, 'class="pagination"')

    def test_home_redirects_to_project_list(self):
        self.assertRedirects(self.client.get(reverse('home')), self.url)


class ProjectDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(
            email='detail-owner@example.com', name='Анна', surname='Иванова',
            avatar='avatars/owner.png',
        )
        cls.member = User.objects.create_user(
            email='detail-member@example.com', name='Пётр', surname='Петров',
            avatar='avatars/member.png',
        )
        cls.visitor = User.objects.create_user(
            email='detail-visitor@example.com', name='Мария', surname='Смирнова',
            avatar='avatars/visitor.png',
        )
        cls.project = Project.objects.create(
            name='Учебный проект', description='Собираем команду', owner=cls.owner,
            github_url='https://github.com/example/teamfinder',
        )
        cls.project.participants.add(cls.member)
        cls.url = reverse('projects:project_detail', args=[cls.project.pk])

    def test_guest_sees_project_owner_and_participants(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/project-details.html')
        self.assertEqual(response.context['project'], self.project)
        for value in (
            self.project.name, self.project.description, self.project.github_url,
            'Открыт', 'Анна Иванова', 'Пётр Петров',
            self.owner.avatar.url, self.member.avatar.url,
            self.project.created_at.strftime('%d.%m.%Y'),
            f'href="{reverse("users:user_detail", args=[self.owner.pk])}"',
            f'href="{reverse("users:user_detail", args=[self.member.pk])}"',
        ):
            with self.subTest(value=value):
                self.assertContains(response, value)
        for label in ('Завершить проект', 'Участвовать', 'Отказаться от участия',
                      'Редактирование будет доступно позже'):
            self.assertNotContains(response, label)

    def test_missing_project_returns_404(self):
        response = self.client.get(reverse('projects:project_detail', args=[999999]))
        self.assertEqual(response.status_code, 404)

    def test_owner_controls_are_visible_but_disabled(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertContains(response, 'disabled title="Редактирование будет доступно позже"')
        self.assertContains(response, 'disabled title="Завершение проекта будет доступно позже"')
        self.assertContains(response, 'Завершить проект')
        self.assertNotContains(response, 'Участвовать')
        self.assertNotContains(response, 'id="complete-project-btn"')

    def test_non_owner_and_member_controls(self):
        for viewer, expected, absent in (
            (self.visitor, 'Участвовать', 'Отказаться от участия'),
            (self.member, 'Отказаться от участия', 'Участвовать'),
        ):
            with self.subTest(viewer=viewer.email):
                self.client.force_login(viewer)
                response = self.client.get(self.url)
                self.assertContains(response, expected)
                self.assertNotContains(response, absent)
                self.assertContains(response, 'disabled title="Управление участием будет доступно позже"')
                self.assertNotContains(response, 'Завершить проект')
                self.assertNotContains(response, 'Редактирование будет доступно позже')
                self.assertNotContains(response, 'id="participate-btn"')

    def test_closed_project_has_no_complete_button(self):
        self.project.status = 'closed'
        self.project.save()
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertContains(response, 'Завершён')
        self.assertNotContains(response, 'Завершить проект')

    def test_empty_optional_fields_and_participants(self):
        self.project.participants.clear()
        self.project.description = ''
        self.project.github_url = ''
        self.project.save()
        get_user_model().objects.filter(pk=self.owner.pk).update(avatar='')
        response = self.client.get(self.url)
        self.assertContains(response, 'У проекта пока нет участников')
        self.assertContains(response, 'Описание пока не добавлено.')
        self.assertContains(response, 'images/default-avatar.png')
        self.assertNotContains(response, 'Репозиторий на GitHub')

    def test_get_does_not_change_project_or_membership(self):
        before = Project.objects.values().get(pk=self.project.pk)
        for viewer in (None, self.owner, self.member, self.visitor):
            self.client.logout()
            if viewer:
                self.client.force_login(viewer)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(Project.objects.values().get(pk=self.project.pk), before)
            self.assertCountEqual(self.project.participants.all(), [self.member])


class ProjectCreationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email='creator@example.com', name='Анна', surname='Иванова',
            avatar='avatars/anna.png',
        )
        cls.other = get_user_model().objects.create_user(
            email='other-creator@example.com', name='Пётр', surname='Петров',
            avatar='avatars/petr.png',
        )
        cls.url = reverse('projects:create_project')

    def project_data(self, **changes):
        data = {
            'name': 'Новый проект', 'description': 'Описание проекта',
            'github_url': 'https://github.com/example/project', 'status': 'open',
        }
        data.update(changes)
        return data

    def test_guest_cannot_open_or_submit_form(self):
        self.assertRedirects(
            self.client.get(self.url), f'{reverse("users:login")}?next={self.url}',
        )
        self.assertRedirects(
            self.client.post(self.url, self.project_data()),
            f'{reverse("users:login")}?next={self.url}',
        )
        self.assertFalse(Project.objects.exists())

    def test_get_shows_empty_form_with_allowed_fields(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projects/create-project.html')
        self.assertIs(response.context['is_edit'], False)
        form = response.context['form']
        self.assertFalse(form.is_bound)
        self.assertEqual(tuple(form.fields), ('name', 'description', 'github_url', 'status'))
        self.assertEqual(list(form.fields['status'].choices), [('open', 'Открыт'), ('closed', 'Закрыт')])
        self.assertContains(response, '<select name="status"')
        self.assertContains(response, 'Опубликовать')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertFalse(Project.objects.exists())

    def test_valid_post_sets_owner_and_participant(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, self.project_data(
            owner=self.other.pk, participants=[self.other.pk], created_at='2000-01-01',
        ))
        self.assertEqual(Project.objects.count(), 1)
        project = Project.objects.get()
        self.assertEqual(project.owner, self.user)
        self.assertCountEqual(project.participants.all(), [self.user])
        self.assertEqual(project.name, 'Новый проект')
        self.assertEqual(project.description, 'Описание проекта')
        self.assertEqual(project.github_url, 'https://github.com/example/project')
        self.assertEqual(project.status, 'open')
        self.assertNotEqual(project.created_at.year, 2000)
        self.assertRedirects(response, reverse('projects:project_detail', args=[project.pk]))

    def test_optional_fields_and_closed_status(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, self.project_data(
            description='', github_url='', status='closed',
        ))
        project = Project.objects.get()
        self.assertEqual(project.description, '')
        self.assertEqual(project.github_url, '')
        self.assertEqual(project.status, 'closed')
        self.assertRedirects(response, reverse('projects:project_detail', args=[project.pk]))

    def test_invalid_data_displays_errors_and_does_not_create_project(self):
        self.client.force_login(self.user)
        for changes, field in (
            ({'name': ''}, 'name'),
            ({'name': ' '}, 'name'),
            ({'name': 'x' * 201}, 'name'),
            ({'github_url': 'not a url'}, 'github_url'),
            ({'github_url': 'https://example.com'}, 'github_url'),
            ({'github_url': 'https://github.com.example.org'}, 'github_url'),
            ({'github_url': 'https://github.com@example.org'}, 'github_url'),
            ({'github_url': 'https://docs.github.com'}, 'github_url'),
            ({'github_url': 'ftp://github.com/example'}, 'github_url'),
            ({'status': ''}, 'status'),
            ({'status': 'other'}, 'status'),
        ):
            with self.subTest(changes=changes):
                response = self.client.post(self.url, self.project_data(**changes))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, 'projects/create-project.html')
                form = response.context['form']
                self.assertIn(field, form.errors)
                self.assertContains(response, form.errors[field][0])
                self.assertContains(response, 'Описание проекта')
                self.assertFalse(Project.objects.exists())

    def test_create_links_use_named_route(self):
        self.client.force_login(self.user)
        for url in (
            reverse('projects:project_list'),
            reverse('users:user_detail', args=[self.user.pk]),
        ):
            response = self.client.get(url)
            self.assertContains(response, f'href="{self.url}"')
            self.assertNotContains(response, 'href="/projects/create-project"')
