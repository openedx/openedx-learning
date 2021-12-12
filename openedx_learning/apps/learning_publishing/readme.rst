Publishing App
==============

The ``publishing`` app holds the core data models that allow different apps will
use to track the creation and publishing of new versions of content data. It is
intended to have no external dependencies, though it may execute third-party
code through plugin mechanisms at runtime.

Intended Use Cases
------------------

* Create a new version of content for draft viewing purposes.
* Publish a new version of content.

The idea is that a new LearningContextVersion is created, and an app builds all
the data it needs for that version. Once all apps have built the necessary data,
pointing the latest "published" version to be that version is a fast, atomic
operation.


Architecture Guidelines
-----------------------

Things to remember:

* apps may come and go
* third party plugins to those apps may come and go
* other apps may
* historical content data from old versions does not have to be preserved.
* content **metadata** should have their full history preserved.
