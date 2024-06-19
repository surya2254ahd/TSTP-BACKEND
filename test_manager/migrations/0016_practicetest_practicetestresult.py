# Generated by Django 4.1.10 on 2023-12-29 08:54

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("course_manager", "0026_alter_material_material_type"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("test_manager", "0015_alter_testsubmission_selected_question_ids"),
    ]

    operations = [
        migrations.CreateModel(
            name="PracticeTest",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "course_subject",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="course_manager.coursesubjects",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="practice_tests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PracticeTestResult",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("correct_answer_count", models.IntegerField()),
                ("incorrect_answer_count", models.IntegerField()),
                ("time_taken", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("detailed_view", models.JSONField(default=dict)),
                (
                    "practice_test",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="test_manager.practicetest",
                    ),
                ),
            ],
        ),
    ]
