# Generated by Django 4.1.10 on 2023-12-13 13:17

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("test_manager", "0012_test_show_prev_button_test_show_skip_button"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="testsubmission",
            unique_together=set(),
        ),
    ]
