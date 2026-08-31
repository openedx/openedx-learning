Backup/Restore Applet
=====================

The ``backup_restore`` applet is responsible for making a backup archive of an existing Learning Package, or creating a new Learning Package from an existing archive.

Restoring (reading an archive) is done with pydantic schema validation, in a pipeline of small modules that hand plain data to each other::

    archive.py     Archive location (a path)       → FileSystem (fsspec)
    payload.py     FileSystem (fsspec)             → UnvalidatedLearningPackageInput
    validation.py  UnvalidatedLearningPackageInput → ValidatedLearningPackageInput
    loading.py     ValidatedLearningPackageInput   → LearningPackage

Backing up (writing an archive) has not been migrated yet. It still lives in ``zipper.py`` and ``toml.py``, which build TOML directly from the Django models. The ``*OutputData`` models in ``schema.py`` are the beginning of that work, but nothing uses them yet.
