from django.db import migrations, models

import openedx_django_lib.fields


class Migration(migrations.Migration):

    dependencies = [
        ('openedx_content', '0013_add_container_code'),
    ]

    operations = [
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
    ]
