# Generated by Django 4.1.10 on 2023-09-30 12:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("course_manager", "0008_remove_course_students_courseenrollment"),
    ]

    operations = [
        migrations.AddField(
            model_name="coursesubjects",
            name="order",
            field=models.PositiveIntegerField(default=0),
        ),
    ]