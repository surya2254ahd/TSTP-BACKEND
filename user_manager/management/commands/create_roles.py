from django.core.management.base import BaseCommand
from user_manager.models import Role


class Command(BaseCommand):
    help = 'Create default roles'

    def handle(self, *args, **kwargs):
        roles = ['admin', 'faculty', 'mentor', 'content_developer', 'student', 'parent']

        for role_name in roles:
            if not Role.objects.filter(name=role_name).exists():
                Role.objects.create(name=role_name)
                self.stdout.write(self.style.SUCCESS(f'Role "{role_name}" created successfully.'))
            else:
                self.stdout.write(self.style.WARNING(f'Role "{role_name}" already exists.'))

        self.stdout.write(self.style.SUCCESS('Roles creation complete.'))
