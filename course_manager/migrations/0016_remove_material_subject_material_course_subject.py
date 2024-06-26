# Generated by Django 4.1.10 on 2023-11-15 08:09

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("course_manager", "0015_remove_material_created_at_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="material",
            name="subject",
        ),
        migrations.AddField(
            model_name="material",
            name="course_subject",
            field=models.ForeignKey(
                default=1,
                on_delete=django.db.models.deletion.CASCADE,
                to="course_manager.coursesubjects",
            ),
            preserve_default=False,
        ),
    ]
