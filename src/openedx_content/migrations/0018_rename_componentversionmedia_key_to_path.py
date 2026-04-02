from django.db import migrations, models

import openedx_django_lib.fields


class Migration(migrations.Migration):

    dependencies = [
        ('openedx_content', '0017_rename_learningpackage_db_column_key_to_package_ref'),
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
        migrations.AddConstraint(
            model_name='componentversionmedia',
            constraint=models.UniqueConstraint(
                fields=['component_version', 'path'],
                name='oel_cvcontent_uniq_cv_key',
            ),
        ),
    ]
