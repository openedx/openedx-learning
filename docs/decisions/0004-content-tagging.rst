4. Content Tagging
==================

Context
-------

Tagging content is central to enable content re-use, facilitate the implementation of flexible content structures different from the current implementation and allow adaptive learning in the Open edX platform.

Content tagging should be classified as "kernel" component following `OEP-57's <https://docs.openedx.org/projects/openedx-proposals/en/latest/processes/oep-0057-proc-core-product.html#kernel>`_ guidelines, as a baked-in feature of the platform.

Decision
--------

Implement the new tagging service as a pluggable django app, and installed alongside learning-core as a dependency in the edx-platform.

Tagging data models will follow the guidelines for this repository, and focus on extensibility and flexibility. 

Since some use cases for content tagging are not considered "kernel" (like providing data for a marketing site), a generic mechanism to differentiate those uses cases will be built, and proper Python and REST APIs will be provided, to different taxonomies/tags for the same content. 


Rejected Alternatives
---------------------

Implementing tagging as Discovery service plugin
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Discovery is already used as the source of truth place for course/program/block metadata in the previous implementations, so keeping it here means keeping the platform metadata management "consistent" (specially since it needs to work with all kinds of contents - from atomic learning units all the way up to courses).

Concerns:

#. The course discovery repository is not well documented and has code that is only used by edX/2U.
#. Some implementations are tied to specific closed-source services (example: `openedx/taxonomy-connector <https://github.com/openedx/taxonomy-connector>`_ uses a 3rd party closed-source service to tag video blocks automatically).
#. The data flow from the discovery service is confusing, and evolved as the needs for that repo changed. `Reference <https://discuss.openedx.org/t/when-to-make-a-new-backend-service/8267/5>`_.
#. Many people prefer/need to run the platform without the discovery service.

Implement tagging as a new IDA
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A new IDA dedicated for tagging would represent a break from the current codebases and force implementation using REST APIs.
This option adds extra complexity without a good compelling reason for it.

Concerns:

#. One more app to host: maintenance cost increases over time.
#. Extra response time between services when handling synchronous operations related to tagging.
