# Generated by Django 4.1.10 on 2023-10-24 13:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("test_manager", "0008_alter_testsubmission_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="result",
            name="time_taken",
            field=models.IntegerField(default=0),
        ),
    ]
