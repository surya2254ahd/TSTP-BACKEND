# Generated by Django 4.1.10 on 2023-09-27 15:28

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("course_manager", "0007_alter_question_question_type"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="course",
            name="students",
        ),
        migrations.CreateModel(
            name="CourseEnrollment",
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
                ("subscription_start_date", models.DateField(null=True)),
                ("subscription_end_date", models.DateField(null=True)),
                (
                    "subscription_type",
                    models.CharField(
                        choices=[("Free", "Free"), ("Paid", "Paid")],
                        default="Free",
                        max_length=10,
                    ),
                ),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="enrollments",
                        to="course_manager.course",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="course_enrollments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "unique_together": {("student", "course")},
            },
        ),
    ]