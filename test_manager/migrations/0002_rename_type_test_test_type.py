# Generated by Django 4.1.10 on 2023-09-26 17:47

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("test_manager", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="test",
            old_name="type",
            new_name="test_type",
        ),
    ]