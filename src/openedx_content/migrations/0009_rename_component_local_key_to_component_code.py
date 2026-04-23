"""
Rename Component.local_key -> Component.component_code and change from key_field to code_field.
"""
import re

import django.core.validators
from django.db import migrations, models

import openedx_django_lib.fields


class Migration(migrations.Migration):

    dependencies = [
        ('openedx_content', '0008_rename_collection_key_to_collection_code'),
    ]

    operations = [
        # Drop old constraint and index (reference the old field name).
        migrations.RemoveConstraint(
            model_name='component',
            name='oel_component_uniq_lc_ct_lk',
        ),
        migrations.RemoveIndex(
            model_name='component',
            name='oel_component_idx_ct_lk',
        ),
        # Rename the column.
        migrations.RenameField(
            model_name='component',
            old_name='local_key',
            new_name='component_code',
        ),
        # Change from key_field (max_length=500, no validator) to code_field
        # (max_length=255, with regex validator).
        migrations.AlterField(
            model_name='component',
            name='component_code',
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
        # Re-add constraint and index with the new field name.
        migrations.AddConstraint(
            model_name='component',
            constraint=models.UniqueConstraint(
                fields=('learning_package', 'component_type', 'component_code'),
                name='oel_component_uniq_lc_ct_lk',
            ),
        ),
        migrations.AddConstraint(
            model_name='component',
            constraint=models.CheckConstraint(
                # The original version of this migration had an ascii-only regex constraint,
                # matching the django-level RegexValidator defined above. However,
                # that constraint caused an IntegrityError on some dev sites with non-ascii component
                # codes in libraries, which technically we allow. So, we've loosened this constraint
                # just to ensure that the migration applies cleanly. Migration 0013 will re-create
                # the constraint and validator to be unicode-friendly, regardless of whether 0009
                # was applied with the ascii-only or unicode-friendly constraint.
                condition=django.db.models.lookups.Regex(models.F('component_code'), '^[\\w.-]+\\Z'),
                name='oel_component_code_regex',
                violation_error_message='Enter a valid "code name" consisting of letters, numbers, underscores, hyphens, or periods.',
            ),
        ),
        migrations.AddIndex(
            model_name='component',
            index=models.Index(
                fields=['component_type', 'component_code'],
                name='oel_component_idx_ct_lk',
            ),
        ),
    ]
