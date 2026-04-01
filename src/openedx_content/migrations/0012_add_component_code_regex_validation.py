import re

import django.core.validators
from django.db import migrations

import openedx_django_lib.fields


class Migration(migrations.Migration):

    dependencies = [
        ('openedx_content', '0011_rename_component_local_key_to_code_in_db'),
    ]

    operations = [
        migrations.AlterField(
            model_name='component',
            name='component_code',
            field=openedx_django_lib.fields.MultiCollationCharField(
                db_collations={'mysql': 'utf8mb4_bin', 'sqlite': 'BINARY'},
                max_length=255,
                validators=[
                    django.core.validators.RegexValidator(
                        re.compile('^[a-zA-Z0-9\\-\\_\\.]+\\Z'),
                        'Enter a valid "code name" consisting of letters, numbers, underscores, hyphens, or periods.',
                        'invalid',
                    ),
                ],
            ),
        ),
    ]
