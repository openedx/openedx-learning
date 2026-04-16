"""
Rename PublishableEntity.key -> entity_ref and LearningPackage.key -> package_ref.

Both fields previously had db_column='_key'; this migration also renames the
underlying DB columns to match the new field names.
"""
from django.db import migrations, models

import openedx_django_lib.fields


class Migration(migrations.Migration):

    dependencies = [
        ('openedx_content', '0010_add_container_code'),
    ]

    operations = [
        # ---- PublishableEntity.key -> entity_ref ----
        migrations.RemoveConstraint(
            model_name='publishableentity',
            name='oel_pub_ent_uniq_lp_key',
        ),
        migrations.RemoveIndex(
            model_name='publishableentity',
            name='oel_pub_ent_idx_key',
        ),
        migrations.RenameField(
            model_name='publishableentity',
            old_name='key',
            new_name='entity_ref',
        ),
        # RenameField only changes the Django field name; the DB column is still
        # '_key' (set via db_column). Use SeparateDatabaseAndState to rename the
        # actual column and drop the db_column override from state.
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
                migrations.RunSQL(
                    sql='ALTER TABLE openedx_content_publishableentity RENAME COLUMN _key TO entity_ref',
                    reverse_sql='ALTER TABLE openedx_content_publishableentity RENAME COLUMN entity_ref TO _key',
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name='publishableentity',
            constraint=models.UniqueConstraint(
                fields=['learning_package', 'entity_ref'],
                name='oel_pub_ent_uniq_lp_key',
            ),
        ),
        migrations.AddIndex(
            model_name='publishableentity',
            index=models.Index(
                fields=['entity_ref'],
                name='oel_pub_ent_idx_key',
            ),
        ),

        # ---- LearningPackage.key -> package_ref ----
        migrations.RemoveConstraint(
            model_name='learningpackage',
            name='oel_publishing_lp_uniq_key',
        ),
        migrations.RenameField(
            model_name='learningpackage',
            old_name='key',
            new_name='package_ref',
        ),
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
        migrations.AddConstraint(
            model_name='learningpackage',
            constraint=models.UniqueConstraint(
                fields=['package_ref'],
                name='oel_publishing_lp_uniq_key',
            ),
        ),
    ]
