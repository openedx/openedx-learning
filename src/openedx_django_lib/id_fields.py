"""
Fields for supporting fully-typed integer primary keys
"""

from django.db import models


class TypedBigAutoField(models.BigAutoField):
    """
    Generic helper for constructing a BigAutoField with strongly-typed primary
    keys. Use it like this:

    ```
    class MyModel(models.Model):
        MyModelID = NewType("MyModelID", int)
        type ID = MyModelID

        class IDField(TypedBigAutoField[ID]):
            pass

        id = IDField(primary_key=True)

        ... # rest of your model's fields...
    ```
    """

    # The actual typing + django-stubs "magic" is handled entirely by the .pyi file.

    @classmethod
    def __class_getitem__(cls, _):
        # At runtime, type parameters are ignored — this just lets `TypedBigAutoField[XxxID]`
        # and `class XxxField(TypedBigAutoField[XxxID])` work without `Generic` in the MRO.
        # (Including `Generic` as a superclass here breaks Django's field __deepcopy__.)
        return cls

    def deconstruct(self):
        # Return the standard Django class path so the migration autodetector sees
        # `BigAutoField` rather than the inner `IDField` subclass — otherwise every
        # rename/move of the subclass generates a spurious AlterField migration.
        name, _path, args, kwargs = super().deconstruct()
        return name, "django.db.models.BigAutoField", args, kwargs


class TypedAutoField(models.AutoField):
    """
    Use sparingly. This is a 32-bit version of `TypedBigAutoField`, and you
    should usually be using that instead of this for primary key fields.
    """

    @classmethod
    def __class_getitem__(cls, _):  # See explanation on the class above.
        return cls

    def deconstruct(self):
        # Same reasoning as TypedBigAutoField.deconstruct() above.
        name, _path, args, kwargs = super().deconstruct()
        return name, "django.db.models.AutoField", args, kwargs
