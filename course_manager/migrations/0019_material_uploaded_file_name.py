# Generated by Django 4.1.10 on 2023-11-16 04:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("course_manager", "0018_material_is_active"),
    ]

    operations = [
        migrations.AddField(
            model_name="material",
            name="uploaded_file_name",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]