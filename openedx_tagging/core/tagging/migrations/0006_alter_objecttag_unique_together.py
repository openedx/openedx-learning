# Generated by Django 3.2.19 on 2023-08-02 16:20

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("oel_tagging", "0005_language_taxonomy"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="objecttag",
            unique_together={("taxonomy", "_value", "object_id")},
        ),
    ]
