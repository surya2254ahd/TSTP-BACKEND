# Generated by Django 4.1.10 on 2024-02-19 17:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("test_manager", "0019_answeredquestions"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="test",
            options={"ordering": ["-created_at"]},
        ),
    ]
