# Generated by Django 4.1.10 on 2023-12-04 18:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("test_manager", "0011_alter_test_options_alter_testsubmission_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="test",
            name="show_prev_button",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="test",
            name="show_skip_button",
            field=models.BooleanField(default=True),
        ),
    ]
