25. Learning Package Serialization and Validation Approach
==========================================================

Context
-------

Content Libraries map 1:1 to LearningPackages and these need to be imported and exported as file archives. Initial support for this was released in Ulmo, but we wanted to revisit it to make it more robust during the Verawood timeline. This is part of that effort.

* Flexibility of Structure
* Standardization of validation (JSON Schema)
* Justify ZIP
* Justify TOML
* Max 100,000 items.
* Use of fsspec as abstraction

Phases

Archive → Filesystem → Learning Package Doc + Resources → Input Models → LearningPackage


Decision
--------

Some key points:

1. We intentionally separate input and output formats because the output format
   will change over time, but the various input formats must continue to be
   supported. We don't inherit from one from the other because we don't *want*
   those changes to be automatically propogated--that breaks compatibility.
2. We assemble into giant JSON in order to simplify validation and allow for
   more flexibility in structural representation. There's the archive layer and
   then the logical layer and then serialization into the database.


Archive -> Model (validation) + Resources -> Database



Consequences
------------



Rejected alternatives
---------------------

