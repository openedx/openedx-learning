"""
Rename Collection.key -> Collection.collection_code and change from key_field to code_field.
"""
import re

import django.core.validators
import django.db.models.lookups
from django.conf import settings
from django.db import migrations, models

import openedx_django_lib.fields


class Migration(migrations.Migration):

    dependencies = [
        ('openedx_content', '0007_publishlogrecord_direct'),
    ]

    operations = [
        # Drop old constraint (references the old field name).
        migrations.RemoveConstraint(
            model_name='collection',
            name='oel_coll_uniq_lp_key',
        ),
        # Rename the column.
        migrations.RenameField(
            model_name='collection',
            old_name='key',
            new_name='collection_code',
        ),
        # Change from key_field (max_length=500, no validator) to code_field
        # (max_length=255, with regex validator).
        migrations.AlterField(
            model_name='collection',
            name='collection_code',
            field=openedx_django_lib.fields.MultiCollationCharField(
                db_collations={'mysql': 'utf8mb4_bin', 'sqlite': 'BINARY'},
                max_length=255,
                validators=[
                    django.core.validators.RegexValidator(
                        re.compile('^[a-zA-Z0-9_.-]+\\Z'),
                        'Enter a valid "code name" consisting of letters, numbers, underscores, hyphens, or periods.',
                        'invalid',
                    ),
                ],
            ),
        ),
        # Re-add uniqueness constraint with the new field name.
        migrations.AddConstraint(
            model_name='collection',
            constraint=models.UniqueConstraint(
                fields=('learning_package', 'collection_code'),
                name='oel_coll_uniq_lp_key',
            ),
        ),
        # DB-level regex check constraint.
        migrations.AddConstraint(
            model_name='collection',
            constraint=models.CheckConstraint(
                condition=django.db.models.lookups.Regex(
                    models.F('collection_code'),
                    '^[a-zA-Z0-9_.-]+\\Z',
                ),
                name='oel_coll_collection_code_regex',
                violation_error_message=(
                    'Enter a valid "code name" consisting of letters, numbers,'
                    ' underscores, hyphens, or periods.'
                ),
            ),
        ),
    ]
