from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Test, Section, CourseSubjects


@receiver(post_save, sender=Test)
def create_sections_for_test(sender, instance, created, **kwargs):
    if created:  # Only execute for new tests
        course_subjects = CourseSubjects.get_subjects_for_course(instance.course)
        for course_subject in course_subjects:
            section = Section.objects.create(
                test=instance,
                course_subject=course_subject,
                name=course_subject.subject.name,
                order=course_subject.order
            )
            for section_meta in course_subject.metadata['sections']:
                sub_section = {
                    "id": section_meta["id"],
                    "name": section_meta["name"],
                    "duration": section_meta['time_limit'],
                    "no_of_questions": section_meta['no_of_questions'],
                    "questions": []
                }
                section.add_sub_section(sub_section)
