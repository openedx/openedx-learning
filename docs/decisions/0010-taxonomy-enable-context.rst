10. Taxonomy enabled for context
================================

Context
-------

The MVP specification says that taxonomies need to be able to be enabled/disabled for the following contexts: instance, organization, and course.

Taxonomy Administrators must be able to enable a taxonomy globally for all organizations in an instance, or to set a list of organizations who can use the taxonomy.

Content Authors must be able to turn taxonomies (instance and org-levels) on/off at the course level.

Decision
--------

When is a taxonomy field shown to course authors in a given course?

+-------------+-----------------------------+--------------------------+-------------------------------+
| tax.enabled | tax.enabled_for(course.org) | course enables all tax's | Is taxonomy shown for course? |
+=============+=============================+==========================+===============================+
| True        | True                        | True                     | True                          |
+-------------+-----------------------------+--------------------------+-------------------------------+
| False       | True                        | True                     | False                         |
+-------------+-----------------------------+--------------------------+-------------------------------+
| True        | False                       | True                     | False                         |
+-------------+-----------------------------+--------------------------+-------------------------------+
| True        | True                        | False                    | False                         |
+-------------+-----------------------------+--------------------------+-------------------------------+
| False       | True                        | False                    | False                         |
+-------------+-----------------------------+--------------------------+-------------------------------+
| False       | False                       | True                     | False                         |
+-------------+-----------------------------+--------------------------+-------------------------------+

.. _Course:

Course
~~~~~~

We will add a Course `Advanced Settings`_ that allows course authors to enable/disable *all available taxonomies* for a given course.

In order for a given taxonomy to be "available to a course", it must be enabled in the :ref:`Instance` context and the course's :ref:`Organization` context.

Disabling taxonomies for a course will remove/hide the taxonomy fields from the course edit page and unit edit page(s), and tags will not be shown in Studio for that course. LMS use of tags is outside of this MVP.

Future versions may add more granularity to these settings, to be determined by user needs.

.. _Instance:

Instance
~~~~~~~~

Taxonomy contains a boolean ``enabled`` field.

A Taxonomy can be disabled for all contexts by setting ``enabled = False``.
If ``enabled = True``, then the :ref:`Organization` and :ref:`Course` contexts determine whether a taxonomy will be shown to course authors.

.. _Organization:

Organization
~~~~~~~~~~~~

OrgTaxonomy has a many-to-many relationship with the Organization model, accessed via the ``org_owners`` field.  OrgTaxonomy lives under `cms.djangoapps.tagging` and so has access to the Organization model and logic in Studio.

An OrgTaxonomy is enabled for all organizations if ``org_owners == []``.
If there are any ``org_owners`` set, then the OrgTaxonomy is only enabled for those orgas, i.e. only courses in these orgs will see the taxonomy field in Studio.

Allowing multiple orgs to access a taxonomy reduces redundancy in data and maintenance.

Rejected Alternatives
---------------------

Single org per taxonomy
~~~~~~~~~~~~~~~~~~~~~~~

Having a single org on a taxonomy is simpler from an implementation perspective, but the UI/UX frames demonstrated that it is simpler for the user to maintain a single taxonomy for multiple orgs.

Course Waffle Flags
~~~~~~~~~~~~~~~~~~~

Use `Course Waffle Flags`_ to enable/disable all taxonomies for a given course.

Waffle flags can only be changed by instance superusers, but the MVP specifically requires that content authors have control over this switch.


Link courses to taxonomies
~~~~~~~~~~~~~~~~~~~~~~~~~~

Link individual courses as enabled/disabled to specific taxonomies.
This was deemed too granular for the MVP, and the data structures and UI can be simplified by using a broader on/off flag.


.. _Advanced Settings: https://github.com/openedx/edx-platform/blob/4dc35c73ffa6d6a1dcb6e9ea1baa5bed40721125/cms/djangoapps/models/settings/course_metadata.py#L28
.. _Course Waffle Flags: https://github.com/openedx/edx-platform/blob/4dc35c73ffa6d6a1dcb6e9ea1baa5bed40721125/openedx/core/djangoapps/waffle_utils/models.py#L14
