"""
Remove the "system-defined" taxonomy machinery (Taxonomy subclasses and the
``_taxonomy_class`` casting column) in favour of a simple ``read_only`` flag.

See https://github.com/openedx/openedx-core/issues/634 for the rationale.

This migration:

* Adds the ``read_only`` boolean field to Taxonomy.
* Marks any taxonomy that used to be "system-defined" (i.e. had a
  ``_taxonomy_class`` set) as ``read_only=True``, so that its tags remain
  immutable as they were before.
* Handles the auto-created "Languages" taxonomy (``id=-1``), which was created
  by ``0012_language_taxonomy`` and is no longer supported: if it has been used
  (any related object tags exist) it is converted into a regular, editable
  taxonomy; otherwise it is deleted.
* Removes the now-unused ``_taxonomy_class`` column and the proxy models.
"""

from django.db import migrations, models

# The Languages taxonomy was auto-created with this fixed id by 0012_language_taxonomy.
LANGUAGE_TAXONOMY_ID = -1


def forwards(apps, schema_editor):
    """
    Migrate system-defined taxonomies to the new read_only flag, and either
    convert or drop the auto-created Languages taxonomy.
    """
    Taxonomy = apps.get_model("oel_tagging", "Taxonomy")
    ObjectTag = apps.get_model("oel_tagging", "ObjectTag")

    language_taxonomy = Taxonomy.objects.filter(id=LANGUAGE_TAXONOMY_ID).first()
    if language_taxonomy:
        if ObjectTag.objects.filter(taxonomy_id=LANGUAGE_TAXONOMY_ID).exists():
            # It's in use, so convert it into a regular, editable taxonomy,
            # keeping whatever language Tags have already been created.
            language_taxonomy._taxonomy_class = None
            language_taxonomy.read_only = False
            language_taxonomy.save()
        else:
            # Unused, so remove it (and its tags) entirely.
            language_taxonomy.delete()

    # Any remaining taxonomy that was backed by a subclass was "system-defined",
    # meaning its tags could not be modified. Preserve that by marking it read-only.
    Taxonomy.objects.exclude(_taxonomy_class__isnull=True).exclude(_taxonomy_class="").update(read_only=True)


def backwards(apps, schema_editor):
    """
    Nothing to undo here: the deleted Languages taxonomy and the subclass
    information cannot be restored, because the subclasses no longer exist.
    The ``read_only`` column is dropped by the reversal of the AddField
    operation.
    """


class Migration(migrations.Migration):

    dependencies = [
        ('oel_tagging', '0020_tag_depth_and_lineage'),
    ]

    operations = [
        migrations.DeleteModel(
            name='LanguageTaxonomy',
        ),
        migrations.DeleteModel(
            name='ModelSystemDefinedTaxonomy',
        ),
        migrations.DeleteModel(
            name='SystemDefinedTaxonomy',
        ),
        migrations.DeleteModel(
            name='UserSystemDefinedTaxonomy',
        ),
        migrations.AddField(
            model_name='taxonomy',
            name='read_only',
            field=models.BooleanField(default=False, help_text='Indicates that the tags in this taxonomy are maintained by the system or an external integration; taxonomy admins will not be permitted to add, edit, or delete its tags.'),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name='taxonomy',
            name='_taxonomy_class',
        ),
    ]
