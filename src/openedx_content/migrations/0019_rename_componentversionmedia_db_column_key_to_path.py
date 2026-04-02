from django.db import migrations

import openedx_django_lib.fields


class Migration(migrations.Migration):
    """
    Rename the underlying DB column for ComponentVersionMedia.path from
    '_key' to 'path'. Uses SeparateDatabaseAndState with RunSQL for
    SQLite/MySQL compatibility. The table is named
    'openedx_content_componentversionmedia' (Django default).
    """

    dependencies = [
        ('openedx_content', '0018_rename_componentversionmedia_key_to_path'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='componentversionmedia',
                    name='path',
                    field=openedx_django_lib.fields.MultiCollationCharField(
                        db_collations={'mysql': 'utf8mb4_bin', 'sqlite': 'BINARY'},
                        max_length=500,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE openedx_content_componentversionmedia RENAME COLUMN _key TO path',
                    reverse_sql='ALTER TABLE openedx_content_componentversionmedia RENAME COLUMN path TO _key',
                ),
            ],
        ),
    ]
