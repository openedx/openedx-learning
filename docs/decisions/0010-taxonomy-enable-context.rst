10. Taxonomy enabled for context
================================

Context
-------

The MVP specification says that taxonomies need to be able to be enabled/disabled for the following contexts: instance, organization, and course.

Content Authors must be able to turn taxonomies (instance and org-levels) on/off at the course level.

Decision
--------

Instance
~~~~~~~~

A Taxonomy can be enabled/disabled for all contexts using its ``enabled`` flag.

Organization
~~~~~~~~~~~~

A OrgTaxonomy can be enabled/disabled for a single organization by setting its ``org_owner`` foreign key field. OrgTaxonomy will live under `cms.djangoapps.tagging` and so has access to the Organization model and logic in Studio.

No specific use cases exist yet for marking a single taxonomy for use by multiple organizations.

Multiple taxonomies with the same name may co-exist in an instance, so separate taxonomies fulfilling the same function can be created and maintained for different organizations.

Course
~~~~~~

All available taxonomies can be enabled/disabled for a given course from the Course Author via the Course's `Advanced Settings`_ using established mechanisms.

Disabling taxonomies for a course will remove/hide the taxonomy fields from the course edit page and unit edit page(s), and tags will not be shown in Studio for that course. LMS use of tags is outside of this MVP.

Future versions may add more granularity to these settings, to be determined by user needs.

Rejected Alternatives
---------------------

Course Waffle Flags
~~~~~~~~~~~~~~~~~~~

Use Course Waffle Flags to enable/disable all taxonomies for a given course.

Waffle flags can only be changed by instance superusers, but the MVP specifically requires that content authors have control over this switch.


Link courses to taxonomies
~~~~~~~~~~~~~~~~~~~~~~~~~~

Link individual courses as enabled/disabled to specific taxonomies.
This was deemed too granular for the MVP, and the data structures and UI can be simplified by using a broader on/off flag.


.. _Advanced Settings: https://github.com/openedx/edx-platform/blob/4dc35c73ffa6d6a1dcb6e9ea1baa5bed40721125/cms/djangoapps/models/settings/course_metadata.py#L28
.. _Course Waffle Flags: https://github.com/openedx/edx-platform/blob/4dc35c73ffa6d6a1dcb6e9ea1baa5bed40721125/openedx/core/djangoapps/waffle_utils/models.py#L14
