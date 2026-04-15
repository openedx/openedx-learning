from django.db import migrations

import openedx_django_lib.fields


class Migration(migrations.Migration):

    dependencies = [
        ('openedx_content', '0010_rename_component_local_key_to_code_in_python'),
    ]

    operations = [
        migrations.AlterField(
            model_name='component',
            name='component_code',
            field=openedx_django_lib.fields.MultiCollationCharField(
                db_collations={'mysql': 'utf8mb4_bin', 'sqlite': 'BINARY'},
                max_length=500,
            ),
        ),
    ]
