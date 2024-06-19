# Generated by Django 4.1.10 on 2023-12-01 15:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "course_manager",
            "0025_remove_material_is_active_material_sub_topic_and_more",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="material",
            name="material_type",
            field=models.CharField(
                choices=[("PDF", "Pdf"), ("VIDEO", "Video"), ("IMAGE", "Image")],
                max_length=5,
            ),
        ),
    ]
