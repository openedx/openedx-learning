Backup/Restore Applet
=====================

The ``backup_restore`` is responsible for making a backup archive of an existing Learning Package, or creating a new Learning Package from an existing archive.

Motivation
----------


Intended Use Cases
------------------



Architecture Guidelines
-----------------------



Archive → Filesystem → Learning Package Doc + Resources → Input Models → LearningPackage

Extract -> Validate -> Load


Archive

We are very intentionally separating the following aspects:

archive.py
  The actual