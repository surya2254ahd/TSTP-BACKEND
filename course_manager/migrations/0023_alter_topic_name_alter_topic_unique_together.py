# Generated by Django 4.1.10 on 2023-11-29 05:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("course_manager", "0022_question_difficulty_question_test_type_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="topic",
            name="name",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterUniqueTogether(
            name="topic",
            unique_together={("name", "course_subject")},
        ),
    ]