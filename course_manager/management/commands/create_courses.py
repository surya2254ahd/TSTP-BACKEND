from django.core.management.base import BaseCommand

from course_manager.models import Course, Subject, CourseSubjects


class Command(BaseCommand):
    help = "Create default courses and subjects"

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        sat_course = Course.objects.update_or_create(name='SAT')
        gre_course = Course.objects.update_or_create(name='GRE')
        # act_course = Course.objects.update_or_create(name='ACT')

        print(sat_course[0])

        english_sub = Subject.objects.update_or_create(name='English')
        math_sub = Subject.objects.update_or_create(name='Math')

        print(Subject.objects.all().values('name'))

        sat_english_metadata = {
            "sections": [
                {
                    "id": 1,
                    "name": "Sec A",
                    "no_of_questions": 27,
                    "time_limit": 32
                },
                {
                    "id": 2,
                    "name": "Sec B",
                    "no_of_questions": 27,
                    "time_limit": 32
                }
            ]
        }
        sat_math_metadata = {
            "sections": [
                {
                    "id": 1,
                    "name": "Sec A",
                    "no_of_questions": 22,
                    "time_limit": 35
                },
                {
                    "id": 2,
                    "name": "Sec B",
                    "no_of_questions": 22,
                    "time_limit": 35
                }
            ]
        }
        CourseSubjects.objects.update_or_create(course=sat_course[0], subject=english_sub[0],
                                                metadata=sat_english_metadata,
                                                order=1)
        CourseSubjects.objects.update_or_create(course=sat_course[0], subject=math_sub[0], metadata=sat_math_metadata,
                                                order=2)

        gre_english_metadata = {
            "sections": [
                {
                    "id": 1,
                    "name": "Sec A",
                    "no_of_questions": 20,
                    "time_limit": 30
                },
                {
                    "id": 2,
                    "name": "Sec B",
                    "no_of_questions": 20,
                    "time_limit": 30
                }
            ]
        }
        gre_math_metadata = {
            "sections": [
                {
                    "id": 1,
                    "name": "Sec A",
                    "no_of_questions": 20,
                    "time_limit": 35
                },
                {
                    "id": 2,
                    "name": "Sec B",
                    "no_of_questions": 20,
                    "time_limit": 35
                }
            ]
        }
        CourseSubjects.objects.update_or_create(course=gre_course[0], subject=english_sub[0],
                                                metadata=gre_english_metadata, order=1)
        CourseSubjects.objects.update_or_create(course=gre_course[0], subject=math_sub[0], metadata=gre_math_metadata,
                                                order=2)

        print(CourseSubjects.objects.all().values())
