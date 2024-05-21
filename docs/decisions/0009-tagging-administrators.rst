9. Taxonomy administrators
==========================

Context
-------

Taxonomy Administrators have the right to create, edit, populate, and delete taxonomies available globably for a given instance, or for a specific organization.

How should these users be identified and their access granted?

Decision
--------

In the Studio context, a modified version of "course creator" access will be used to identify Taxonomy Administrators (ref `get_organizations`_):

#. Global staff and superusers can create/edit/populate/delete Taxonomies for the instance or for any org key.

#. Users who can create courses for "any organization" access can create/edit/populate/delete Taxonomies for the instance or for any org key.

#. Users who can create courses only for specific organizations can create/edit/populate/delete Taxonomies with only these org keys.


Permission #1 requires no external access, so can be enforced by the ``openedx_tagging`` app.

But because permissions #2 + #3 require access to the edx-platform CMS model `CourseCreator`_, this access can only be enforced in Studio, and so will live under ``cms.djangoapps.content_tagging`` along with the ``ContentTag`` class. Tagging MVP must work for libraries v1, v2 and courses created in Studio, and so tying these permissions to Studio is reasonable for the MVP.

Per `OEP-9`_, ``openedx_tagging`` will allow applications to use the standard Django API to query permissions, for example: ``user.has_perm('openedx_tagging.edit_taxonomy', taxonomy)``, and the appropriate permissions will be applied in that application's context.

These rules will be enforced in the tagging `views`_, not the API or models, so that external code using this library need not have a logged-in user in order to call the API. So please use with care.

Rejected Alternatives
---------------------

Django users & groups
~~~~~~~~~~~~~~~~~~~~~

This is a standard way to grant access in Django apps, but it is not used in Open edX.

.. _get_organizations: https://github.com/openedx/edx-platform/blob/4dc35c73ffa6d6a1dcb6e9ea1baa5bed40721125/cms/djangoapps/contentstore/views/course.py#L1958
.. _CourseCreator: https://github.com/openedx/edx-platform/blob/4dc35c73ffa6d6a1dcb6e9ea1baa5bed40721125/cms/djangoapps/course_creators/models.py#L27
.. _OEP-9: https://open-edx-proposals.readthedocs.io/en/latest/best-practices/oep-0009-bp-permissions.html
.. _views: https://github.com/dfunckt/django-rules#permissions-in-views
