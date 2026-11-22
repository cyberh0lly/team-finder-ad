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
