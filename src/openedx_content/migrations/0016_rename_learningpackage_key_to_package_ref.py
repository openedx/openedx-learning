from django.db import migrations, models

import openedx_django_lib.fields


class Migration(migrations.Migration):

    dependencies = [
        ('openedx_content', '0015_rename_publishableentity_db_column_key_to_entity_ref'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='learningpackage',
            name='oel_publishing_lp_uniq_key',
        ),
        migrations.RenameField(
            model_name='learningpackage',
            old_name='key',
            new_name='package_ref',
        ),
        migrations.AddConstraint(
            model_name='learningpackage',
            constraint=models.UniqueConstraint(
                fields=['package_ref'],
                name='oel_publishing_lp_uniq_key',
            ),
        ),
    ]
