# Generated by Django 4.1.10 on 2023-10-04 08:16

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("test_manager", "0006_testsubmission_expiration_date"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="testsubmission",
            unique_together={("test", "student")},
        ),
    ]
