# Generated by Django 4.2.10 on 2024-02-14 22:02

from django.db import migrations

import openedx_learning.lib.fields


class Migration(migrations.Migration):

    dependencies = [
        ('oel_publishing', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='learningpackage',
            name='key',
            field=openedx_learning.lib.fields.MultiCollationCharField(db_collations={'mysql': 'utf8mb4_bin', 'sqlite': 'BINARY'}, db_column='_key', max_length=500),
        ),
        migrations.AlterField(
            model_name='publishableentity',
            name='key',
            field=openedx_learning.lib.fields.MultiCollationCharField(db_collations={'mysql': 'utf8mb4_bin', 'sqlite': 'BINARY'}, db_column='_key', max_length=500),
        ),
    ]
