import re

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

import openedx_django_lib.fields


def backfill_container_code(apps, schema_editor):
    """
    Backfill container_code and learning_package from publishable_entity.

    For existing containers, container_code is set to the entity key (the
    only identifier available at this point). Future containers will have
    container_code set by the caller.
    """
    Container = apps.get_model("openedx_content", "Container")
    for container in Container.objects.select_related("publishable_entity__learning_package").all():
        container.learning_package = container.publishable_entity.learning_package
        container.container_code = container.publishable_entity.key
        container.save(update_fields=["learning_package", "container_code"])


class Migration(migrations.Migration):

    dependencies = [
        ("openedx_content", "0009_rename_component_local_key_to_component_code"),
    ]

    operations = [
        # 1. Add learning_package FK (nullable initially for backfill)
        migrations.AddField(
            model_name="container",
            name="learning_package",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="openedx_content.learningpackage",
            ),
        ),
        # 2. Add container_code (nullable initially for backfill)
        migrations.AddField(
            model_name="container",
            name="container_code",
            field=openedx_django_lib.fields.MultiCollationCharField(
                db_collations={"mysql": "utf8mb4_bin", "sqlite": "BINARY"},
                max_length=255,
                null=True,
            ),
        ),
        # 3. Backfill both fields from publishable_entity
        migrations.RunPython(backfill_container_code, migrations.RunPython.noop),
        # 4. Make both fields non-nullable and add regex validation to container_code
        migrations.AlterField(
            model_name="container",
            name="learning_package",
            field=models.ForeignKey(
                null=False,
                on_delete=django.db.models.deletion.CASCADE,
                to="openedx_content.learningpackage",
            ),
        ),
        migrations.AlterField(
            model_name="container",
            name="container_code",
            field=openedx_django_lib.fields.MultiCollationCharField(
                db_collations={"mysql": "utf8mb4_bin", "sqlite": "BINARY"},
                max_length=255,
                validators=[
                    django.core.validators.RegexValidator(
                        re.compile(r"^[a-zA-Z0-9_.-]+\Z"),
                        "Enter a valid \"code name\" consisting of letters, numbers, "
                        "underscores, hyphens, or periods.",
                        "invalid",
                    ),
                ],
            ),
        ),
        # 5. Add uniqueness constraint
        migrations.AddConstraint(
            model_name="container",
            constraint=models.UniqueConstraint(
                fields=["learning_package", "container_code"],
                name="oel_container_uniq_lp_cc",
            ),
        ),
        # 6. Add db-level regex validation
        migrations.AddConstraint(
            model_name='container',
            constraint=models.CheckConstraint(
                # The original version of this migration had an ascii-only regex constraint,
                # matching the django-level RegexValidator defined above. However,
                # that constraint caused an IntegrityError on some dev sites with non-ascii component
                # codes in libraries, which technically we allow. So, we've loosened this constraint
                # just to ensure that the migration applies cleanly. Migration 0013 will re-create
                # the constraint and validator to be unicode-friendly, regardless of whether 0010
                # was applied with the ascii-only or unicode-friendly constraint.
                condition=django.db.models.lookups.Regex(models.F('container_code'), '^[\\w.-]+\\Z'),
                name='oel_container_code_regex',
                violation_error_message='Enter a valid "code name" consisting of letters, numbers, underscores, hyphens, or periods.',
            ),
        ),
    ]
