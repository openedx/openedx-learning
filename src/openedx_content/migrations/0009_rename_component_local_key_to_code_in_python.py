from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('openedx_content', '0008_rename_collection_key_to_collection_code'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='component',
            name='oel_component_uniq_lc_ct_lk',
        ),
        migrations.RemoveIndex(
            model_name='component',
            name='oel_component_idx_ct_lk',
        ),
        migrations.RenameField(
            model_name='component',
            old_name='local_key',
            new_name='component_code',
        ),
        migrations.AddConstraint(
            model_name='component',
            constraint=models.UniqueConstraint(
                fields=('learning_package', 'component_type', 'component_code'),
                name='oel_component_uniq_lc_ct_lk',
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
