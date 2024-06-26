# Generated by Django 4.1.10 on 2024-06-01 03:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("course_manager", "0029_coursesubjects_correct_answer_marks_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="CombinedScore",
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
                ("section1_correct", models.IntegerField()),
                ("section2_correct", models.IntegerField()),
                ("total_score", models.IntegerField()),
            ],
        ),
        migrations.CreateModel(
            name="SectionScore",
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
                ("section_name", models.CharField(max_length=50)),
                ("num_correct", models.IntegerField()),
                ("score", models.IntegerField()),
            ],
        ),
    ]
