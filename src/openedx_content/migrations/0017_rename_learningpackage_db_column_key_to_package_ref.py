from django.db import migrations

import openedx_django_lib.fields


class Migration(migrations.Migration):
    """
    Rename the underlying DB column for LearningPackage.package_ref from
    '_key' to 'package_ref'.

    Uses SeparateDatabaseAndState with RunSQL (RENAME COLUMN) for
    SQLite/MySQL compatibility. The table is named
    'openedx_content_learningpackage' (Django default after migration 0002).
    """

    dependencies = [
        ('openedx_content', '0016_rename_learningpackage_key_to_package_ref'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='learningpackage',
                    name='package_ref',
                    field=openedx_django_lib.fields.MultiCollationCharField(
                        db_collations={'mysql': 'utf8mb4_bin', 'sqlite': 'BINARY'},
                        max_length=500,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE openedx_content_learningpackage RENAME COLUMN _key TO package_ref',
                    reverse_sql='ALTER TABLE openedx_content_learningpackage RENAME COLUMN package_ref TO _key',
                ),
            ],
        ),
    ]
