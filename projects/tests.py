from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
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
