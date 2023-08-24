"""
This module has collation-related code to allow us to attach collation settings
to specific fields on a per-database-vendor basis. This used by the ``fields``
module in order to specify field types have have normalized behavior between
SQLite and MySQL (see fields.py for more details).
"""
from django.db import models


class MultiCollationMixin:
    """
    Mixin to enable multiple, database-vendor-specific collations.

    This should be mixed into new subclasses of CharField and TextField, since
    they're the only Field types that store text data.
    """

    def __init__(self, *args, db_collations=None, db_collation=None, **kwargs):  # pylint: disable=unused-argument
        """
        Init like any field but add db_collations and disallow db_collation

        The ``db_collations`` param should be a dict of vendor names to
        collations, like::

          {
            'msyql': 'utf8mb4_bin',
            'sqlite': 'BINARY'
          }

        It is an error to pass in a CharField-style ``db_collation``. I
        originally wanted to use this attribute name, but I needed to preserve
        it for Django 3.2 compatibility (see the ``db_collation`` method
        docstring for details).
        """

        super().__init__(*args, **kwargs)
        self.db_collations = db_collations or {}

        # This is part of a hack to get this to work for Django < 4.1. Please
        # see comments in the db_collation method for details.
        self._vendor = None

    @property
    def db_collation(self):
        """
        Return the db_collation, understanding that it varies by vendor.

        This method is a hack for Django 3.2 compatibility and should be removed
        after we move to 4.2.

        Description of why this is hacky:

        In Django 4.2, the schema builder pulls the collation settings from the
        field using the value returned from the ``db_parameters`` method, and
        this does what we want it to do. In Django 3.2, field.db_parameters is
        called, but any collation value sent back is ignored and the code grabs
        the value of db_collation directly from the field:

        https://github.com/django/django/blob/stable/3.2.x/django/db/backends/base/schema.py#L214-L224

        But this call to get the ``field.db_collation`` attribute happens almost
        immediately after the ``field.db_parameters`` method call. So our
        fragile hack is to set ``self._vendor`` in the ``db_parameters`` method,
        using the value we get from the connection that is passed in there. We
        can then use ``self._vendor`` to return the right value when Django
        calls ``field.db_collation`` (which is this property method).

        This method, the corresponding setter, and all references to
        ``self._vendor`` should be removed after we've cut over to Django 4.2.
        """
        return self.db_collations.get(self._vendor)

    @db_collation.setter
    def db_collation(self, value):
        """
        Don't allow db_collation to be set manually (just ignore).

        This can be removed when we move to Django 4.2.
        """

    def db_parameters(self, connection):
        """
        Return database parameters for this field. This adds collation info.

        We examine this field's ``db_collations`` attribute and return the
        collation that maps to ``connection.vendor``. This will typically be
        'mysql' or 'sqlite'.
        """
        db_params = models.Field.db_parameters(self, connection)

        # Remove once we no longer need to support Django < 4.1
        self._vendor = connection.vendor

        # Now determine collation based on DB vendor (e.g. 'sqlite', 'mysql')
        if connection.vendor in self.db_collations:
            db_params["collation"] = self.db_collations[connection.vendor]

        return db_params

    def deconstruct(self):
        """
        How to serialize our Field for the migration file.

        For our mixin fields, this is just doing what the field's superclass
        would do and then tacking on our custom ``db_collations`` dict data.
        """
        name, path, args, kwargs = super().deconstruct()
        if self.db_collations:
            kwargs["db_collations"] = self.db_collations
        return name, path, args, kwargs
