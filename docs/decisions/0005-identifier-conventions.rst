5. Identifier Conventions
=========================

Context
-------

We want a common set of conventions for how to reference models in various situations, such as:

* From a model in a different app, but in the same Python process.
* From a different server.

Decision
--------

The content-related data models in our system will use the following convention for identifier fields:

Primary Key
  The primary key will be a BigAutoField. This will usually  be ``id``, but it can be different if the model builds off another one via a ``OneToOneField`` primary key. Other apps that are running in the same process should directly make foreign key field references to this. This value will not change.

UUID
  The ``uuid`` field is a randomly generated UUID4 that is globally unique and should be treated as immutable. If you are making a reference to this record in another system (e.g. an external service), this is the identifier to store.

Key
  The ``key`` field is chosen by apps or users, and is the most likely piece to be human-readable (though it doesn't have to be). These values are only locally unique within a given scope, such as a particular LearningPackage or ComponentVersion.
  
  The correlates most closely to OpaqueKeys, though they are not precisely the same. In particular, we don't want to directly store BlockUsageKeys that have the LearningContextKey baked into them, because that makes it much harder to change the LearningContextKey later, e.g. if we ever want to change a CourseKey for a course. Different models can choose whether the ``key`` value is mutable or not, but outside users should assume that it can change, even if it rarely does in practice.

Implementation Notes
--------------------

Helpers to generate these field types are in the ``openedx_learning.lib.fields`` module.

Rejected Alternatives
---------------------

A number of names were considered for ``key``, and were rejected for different reasons:

* ``identifier`` is used in some standards like QTI, but it's too easily confused with ``id`` or the general concept of the three types of identity-related fields we have.
* ``slug`` was considered, but ultimately rejected because that implied these fields would be human-readable, and that's not guaranteed. Most XBlock content that comes from MongoDB will be using GUIDs, for instance.
