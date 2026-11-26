import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from projects.models import Project
from users.models import Skill, User


DEMO_USERS = (
    {
        'email': 'anna@example.com', 'name': 'Анна', 'surname': 'Смирнова',
        'about': 'Изучаю Django и разрабатываю серверную часть веб-приложений.',
        'skills': ('Python', 'Django', 'PostgreSQL'),
        'project': 'Трекер привычек', 'status': 'open',
        'description': 'Приложение для ежедневных привычек. Ищу разработчиков интерфейса.',
        'participant': 'maxim@example.com',
    },
    {
        'email': 'maxim@example.com', 'name': 'Максим', 'surname': 'Иванов',
        'about': 'Создаю удобные интерфейсы и изучаю JavaScript.',
        'skills': ('HTML', 'CSS', 'JavaScript'),
        'project': 'Планировщик задач', 'status': 'open',
        'description': 'Планировщик личных задач со сроками и отметками о выполнении.',
        'participant': 'maria@example.com',
    },
    {
        'email': 'maria@example.com', 'name': 'Мария', 'surname': 'Кузнецова',
        'about': 'Проектирую интерфейсы в Figma и занимаюсь вёрсткой.',
        'skills': ('Figma', 'HTML', 'CSS'),
        'project': 'Портфолио дизайнера', 'status': 'closed',
        'description': 'Завершённый сайт с примерами дизайна и описаниями работ.',
        'participant': 'elena@example.com',
    },
    {
        'email': 'dmitry@example.com', 'name': 'Дмитрий', 'surname': 'Волков',
        'about': 'Пишу на Python, использую Git и запускаю приложения в Docker.',
        'skills': ('Python', 'Docker', 'Git'),
        'project': 'Сервис учёта расходов', 'status': 'open',
        'description': 'Сервис для записи расходов по категориям и планирования бюджета.',
        'participant': 'anna@example.com',
    },
    {
        'email': 'elena@example.com', 'name': 'Елена', 'surname': 'Соколова',
        'about': 'Изучаю базы данных и анализирую данные с помощью SQL и Python.',
        'skills': ('SQL', 'PostgreSQL', 'Python'),
        'project': 'Каталог книг', 'status': 'closed',
        'description': 'Готовый каталог прочитанных книг с описаниями и заметками.',
        'participant': 'dmitry@example.com',
    },
)


class Command(BaseCommand):
    help = 'Создать демопользователей и проекты. Пароль задаётся через DEMO_PASSWORD.'

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get('DEMO_PASSWORD')
        if not password:
            raise CommandError(
                'Задайте переменную окружения DEMO_PASSWORD перед запуском seed_data.'
            )

        users = {}
        projects = {}
        skills = {}
        created_skills = 0
        created_projects = 0
        skipped = 0

        for user_data in DEMO_USERS:
            for name in user_data['skills']:
                if name not in skills:
                    skill, created = Skill.objects.get_or_create(name=name)
                    skills[name] = skill
                    created_skills += int(created)
                    skipped += int(not created)

        for user_data in DEMO_USERS:
            email = user_data['email']
            if User.objects.filter(email__iexact=email).exists():
                skipped += 1
                self.stdout.write(self.style.WARNING(
                    f'Email {email} уже занят: пользователь и его связи пропущены. '
                    'Подтвердить принадлежность к демоданным нельзя.'
                ))
                continue

            user = User.objects.create_user(
                email=email, password=password,
                name=user_data['name'], surname=user_data['surname'],
                about=user_data['about'],
                is_active=True, is_staff=False, is_superuser=False,
            )
            users[email] = user
            user.skills.add(*(skills[name] for name in user_data['skills']))
            project, created = Project.objects.get_or_create(
                owner=user, name=user_data['project'],
                defaults={
                    'description': user_data['description'],
                    'status': user_data['status'],
                },
            )
            created_projects += int(created)
            skipped += int(not created)
            project.participants.add(user)
            projects[email] = project

        for user_data in DEMO_USERS:
            project = projects.get(user_data['email'])
            participant = users.get(user_data['participant'])
            if project is not None and participant is not None:
                project.participants.add(participant)

        self.stdout.write(self.style.SUCCESS(
            f'Заполнение завершено. Создано пользователей: {len(users)}, '
            f'навыков: {created_skills}, проектов: {created_projects}. '
            f'Существующих записей пропущено: {skipped}.'
        ))
