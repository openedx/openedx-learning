"""
Create a database view 'oel_tagging_tag_computed' that uses a WITH RECURSIVE
common table expression to compute the sort_key for every Tag by walking its
ancestor chain up to the root, producing:

    lower("root_value<TAB>...<TAB>tag_value<TAB>")

This sort key allows us to sort arbitrary keys into "tree order", so

    Charlie
        Alice
        Bob
    Danielle

Gets sorted as "Charlie", "Alice", "Bob", "Danielle"
(using sort keys "charlie\t", "charlie\talice\t", "charlie\tbob\t, "danielle\t")

While we're at it, we compute the 'depth' field as well - root tags with no
parent have depth=0, their children have depth=1, and so on.

The tab separator is embedded as a Python \\t escape, which all databases accept
as a literal tab character inside a SQL string literal.  The only remaining
vendor difference is string concatenation: SQLite and PostgreSQL use ||, while
MySQL treats || as logical OR and requires CONCAT().
"""
import django.db.models
from django.db import migrations

# Note: Python's \t is expanded to a real tab character before the SQL reaches
# the DB, so the DB engine just sees a string literal tab '	' (ASCII 9).
# depth starts at 0 in the base case and increments once per recursive step
# (one step = one ancestor level), so when parent_id IS NULL it equals the
# number of ancestors, i.e. the absolute depth of the original tag.
_SQL_PIPE = """
    CREATE VIEW oel_tagging_tag_computed AS
    WITH RECURSIVE tag_path(tag_id, parent_id, sort_key, depth) AS (
        SELECT id, parent_id, LOWER(value || '\t'), 0
        FROM oel_tagging_tag
        UNION ALL
        SELECT tp.tag_id, p.parent_id, LOWER(p.value || '\t' || tp.sort_key), tp.depth + 1
        FROM tag_path tp
        JOIN oel_tagging_tag p ON tp.parent_id = p.id
    )
    SELECT tag_id, sort_key, depth FROM tag_path WHERE parent_id IS NULL
"""

_SQL_MYSQL = """
    CREATE VIEW oel_tagging_tag_computed AS
    WITH RECURSIVE tag_path(tag_id, parent_id, sort_key, depth) AS (
        SELECT id, parent_id, LOWER(CONCAT(value, '\t')), 0
        FROM oel_tagging_tag
        UNION ALL
        SELECT tp.tag_id, p.parent_id, LOWER(CONCAT(p.value, '\t', tp.sort_key)), tp.depth + 1
        FROM tag_path tp
        JOIN oel_tagging_tag p ON tp.parent_id = p.id
    )
    SELECT tag_id, sort_key, depth FROM tag_path WHERE parent_id IS NULL
"""

_DROP_SQL = "DROP VIEW IF EXISTS oel_tagging_tag_computed"


def create_view(_apps, schema_editor):
    """Create the view that backs TagComputed"""
    if schema_editor.connection.vendor == "mysql":
        # MySQL uses non-standard string concatentation via a function rather than an operator:
        schema_editor.execute(_SQL_MYSQL)
    else:
        # SQLite and PostgreSQL use this standard || syntax:
        schema_editor.execute(_SQL_PIPE)


def drop_view(_apps, schema_editor):
    schema_editor.execute(_DROP_SQL)


class Migration(migrations.Migration):
    """Create the oel_tagging_tag_computed view."""

    # CREATE VIEW is DDL; on MySQL, DDL inside a transaction triggers an implicit
    # commit that would silently break Django's rollback guarantee.  Setting
    # atomic=False tells Django to skip the transaction wrapper for this migration.
    atomic = False

    dependencies = [
        ("oel_tagging", "0019_language_taxonomy_class"),
    ]

    operations = [
        # Register the unmanaged model in the migration state (no DDL generated
        # by Django; the actual view is created by the RunPython step below).
        migrations.CreateModel(
            name="TagComputed",
            fields=[
                (
                    "tag",
                    django.db.models.OneToOneField(
                        db_column="tag_id",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        primary_key=True,
                        related_name="computed",
                        serialize=False,
                        to="oel_tagging.tag",
                    ),
                ),
                ("sort_key", django.db.models.TextField()),
                ("depth", django.db.models.IntegerField()),
            ],
            options={
                "managed": False,
                "db_table": "oel_tagging_tag_computed",
            },
        ),
        # Create the actual view in the database.
        migrations.RunPython(create_view, drop_view, elidable=False),
    ]
