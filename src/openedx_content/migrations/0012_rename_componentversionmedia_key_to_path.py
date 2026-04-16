"""
Rename ComponentVersionMedia.key -> ComponentVersionMedia.path.

The field previously had db_column='_key'; this migration also renames the
underlying DB column to match the new field name.
"""
from django.db import migrations, models

import openedx_django_lib.fields


class Migration(migrations.Migration):

    dependencies = [
        ('openedx_content', '0011_rename_entity_key_and_package_key_to_refs'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='componentversionmedia',
            name='oel_cvcontent_uniq_cv_key',
        ),
        migrations.RenameField(
            model_name='componentversionmedia',
            old_name='key',
            new_name='path',
        ),
        # RenameField only changes the Django field name; the DB column is still
        # '_key' (set via db_column). AlterField drops db_column, so Django sees
        # old column='_key' vs new column='path' and renames it.
        migrations.AlterField(
            model_name='componentversionmedia',
            name='path',
            field=openedx_django_lib.fields.MultiCollationCharField(
                db_collations={'mysql': 'utf8mb4_bin', 'sqlite': 'BINARY'},
                max_length=500,
            ),
        ),
        migrations.AddConstraint(
            model_name='componentversionmedia',
            constraint=models.UniqueConstraint(
                fields=['component_version', 'path'],
                name='oel_cvcontent_uniq_cv_key',
            ),
        ),
    ]
