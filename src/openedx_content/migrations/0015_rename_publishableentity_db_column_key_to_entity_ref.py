from django.db import migrations

import openedx_django_lib.fields


class Migration(migrations.Migration):
    """
    Rename the underlying DB column for PublishableEntity.entity_ref from
    '_key' to 'entity_ref'.

    Uses SeparateDatabaseAndState: the state operation tells Django the field
    no longer has db_column='_key'; the database operation does the actual
    column rename via RunSQL.

    The table is named 'openedx_content_publishableentity' (the Django default
    after migration 0002 reset all oel_* table names).
    """

    dependencies = [
        ('openedx_content', '0014_rename_publishableentity_key_to_entity_ref'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='publishableentity',
                    name='entity_ref',
                    field=openedx_django_lib.fields.MultiCollationCharField(
                        db_collations={'mysql': 'utf8mb4_bin', 'sqlite': 'BINARY'},
                        max_length=500,
                    ),
                ),
            ],
            database_operations=[
                # Rename the physical column from '_key' to 'entity_ref'.
                # MySQL and SQLite both support RENAME COLUMN (SQLite >= 3.25.0,
                # MySQL >= 8.0). Django's test runner uses SQLite >= 3.25.
                migrations.RunSQL(
                    sql='ALTER TABLE openedx_content_publishableentity RENAME COLUMN _key TO entity_ref',
                    reverse_sql='ALTER TABLE openedx_content_publishableentity RENAME COLUMN entity_ref TO _key',
                ),
            ],
        ),
    ]
