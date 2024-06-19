# Generated by Django 4.1.10 on 2023-09-30 12:52

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("course_manager", "0009_coursesubjects_order"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="coursesubjects",
            options={"ordering": ["order"]},
        ),
        migrations.AlterUniqueTogether(
            name="coursesubjects",
            unique_together={("course", "subject")},
        ),
    ]