"""
(1) Add a concrete 'depth' column to the oel_tagging_tag table.

The depth column stores:
  - 0 for root tags (parent IS NULL)
  - parent.depth + 1 for all other tags

A CHECK constraint enforces this invariant at the database level:
  parent_id IS NULL OR depth > 0

(2) Add a concrete 'lineage' column to the oel_tagging_tag table.

The lineage column stores the full tab-separated ancestor path including the
tag itself:

    "RootValue\\tParentValue\\t...\\tThisValue\\t"

with original casing and a trailing tab delimiter. Because the column uses a
case-insensitive collation, ORDER BY lineage gives the depth-first tree order
that we want when querying the taxonomy tree.

The trailing tab makes prefix matching unambiguous: every descendant of tag T
has a lineage that starts with T.lineage (since T.lineage ends with '\\t' and
no tag value can contain '\\t').
"""

from django.db import migrations, models
from django.db.models.functions import Concat, Length, Replace

import openedx_django_lib.fields


def populate_depth_and_lineage(apps, _schema_editor):
    """
    Populate the new `depth` and `lineage` columns for all existing tags by
    walking the hierarchy one level at a time (root tags first, then their
    children, etc.).
    """
    Tag = apps.get_model("oel_tagging", "Tag")
    # Root tags: depth 0, lineage = "value\t"
    for tag in Tag.objects.filter(parent__isnull=True).only("id", "value"):
        Tag.objects.filter(pk=tag.pk).update(depth=0, lineage=tag.value + "\t")
    # Walk down the tree one level at a time.
    for level in range(1, 20):  # Depth should be at most 3 or 4, but it doesn't hurt to be thorough.
        children = list(
            Tag.objects.filter(parent__depth=level - 1).select_related("parent").only("id", "value", "parent__lineage")
        )
        if not children:
            break
        for tag in children:
            Tag.objects.filter(pk=tag.pk).update(
                depth=level,
                lineage=tag.parent.lineage + tag.value + "\t",
            )


def reverse_populate_depth_and_lineage(_apps, _schema_editor):
    pass  # Both fields are dropped on reverse, so no cleanup needed.


def _create_lineage_index(_apps, schema_editor):
    """
    Create an index on the lineage column.

    MySQL's InnoDB limits index key length to 3072 bytes; with utf8mb4 (up to
    4 bytes per character) a full-column index on a VARCHAR(3006) would require
    up to 12,024 bytes — far over the limit.  We therefore use a 768-character
    prefix on MySQL (768 × 4 = 3072 bytes, exactly at the limit) and a regular
    full-column index on SQLite and PostgreSQL.
    """
    if schema_editor.connection.vendor == "mysql":
        schema_editor.execute("CREATE INDEX oel_tagging_lineage_d65f82_idx ON oel_tagging_tag (lineage(768))")
    else:
        schema_editor.execute("CREATE INDEX oel_tagging_lineage_d65f82_idx ON oel_tagging_tag (lineage)")


def _drop_lineage_index(_apps, schema_editor):
    if schema_editor.connection.vendor == "mysql":
        schema_editor.execute("DROP INDEX oel_tagging_lineage_d65f82_idx ON oel_tagging_tag")
    else:
        schema_editor.execute("DROP INDEX oel_tagging_lineage_d65f82_idx")


class Migration(migrations.Migration):
    """Add depth and lineage columns to Tag; remove the oel_tagging_tag_computed view."""

    # Even though this migration no longer creates a view, we keep atomic=False
    # as a safety measure since this migration touched DDL on MySQL in its prior form.
    atomic = False

    dependencies = [
        ("oel_tagging", "0019_language_taxonomy_class"),
    ]

    operations = [
        # 1. Add the depth column to oel_tagging_tag with a safe default of 0.
        migrations.AddField(
            model_name="tag",
            name="depth",
            field=models.IntegerField(
                default=0,
                help_text="Number of ancestors this tag has. Zero for root tags, one for their children, and so on. Set automatically by save(); do not set manually.",
            ),
        ),
        # 2. Add the lineage column with an empty default (populated below).
        migrations.AddField(
            model_name="tag",
            name="lineage",
            field=openedx_django_lib.fields.MultiCollationCharField(
                db_collations={"mysql": "utf8mb4_unicode_ci", "sqlite": "NOCASE"},
                default="",
                help_text="Tab-separated ancestor path including this tag: 'Root\\tParent\\t...\\tThisValue\\t'. Used for depth-first tree ordering and descendant prefix matching. Set automatically by save(); do not set manually.",
                max_length=3006,
            ),
        ),
        # 3. Populate depth and lineage for all pre-existing tags.
        migrations.RunPython(populate_depth_and_lineage, reverse_populate_depth_and_lineage, elidable=False),
        # 4. Add CHECK constraints, once we've populated the values.
        migrations.AddConstraint(
            model_name="tag",
            constraint=models.CheckConstraint(
                condition=(models.Q(parent_id__isnull=True) | models.Q(depth__gt=0)),
                name="oel_tagging_tag_depth_parent_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="tag",
            constraint=models.CheckConstraint(
                condition=models.Q(lineage__endswith=Concat(models.F("value"), models.Value("\t"))),
                name="oel_tagging_tag_lineage_ends_with_value",
            ),
        ),
        migrations.AddConstraint(
            model_name="tag",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    depth=(
                        Length(models.F("lineage"))
                        - Length(Replace(models.F("lineage"), models.Value("\t"), models.Value("")))
                        - 1
                    )
                ),
                name="oel_tagging_tag_lineage_tab_count_check",
            ),
        ),
        # 5. Add index on lineage after data is populated, so the build scans real values.
        #    MySQL's InnoDB limits index keys to 3072 bytes; with utf8mb4 (4 bytes/char) that
        #    caps a full-column index at 768 chars — far shorter than max_length=3006.  We use
        #    SeparateDatabaseAndState so Django's migration state records the index normally
        #    (avoiding spurious makemigrations noise) while the actual SQL uses a 768-char
        #    prefix on MySQL and a regular full-column index everywhere else.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name="tag",
                    index=models.Index(fields=["lineage"], name="oel_tagging_lineage_d65f82_idx"),
                ),
            ],
            database_operations=[
                migrations.RunPython(_create_lineage_index, _drop_lineage_index, elidable=False),
            ],
        ),
    ]
