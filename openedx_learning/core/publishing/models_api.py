"""
This should have a mixin that gives a "current-version-on-branch"
mixin that will join classes like Component with ComponentVersion and
give them the ability to have one associated with a particular branch
+ history.

Rename this model_mixins.py?

Publishing should lay a framework for three types of versioned Things:

* the Thing itself, across all versions
* a specific ThingVersion
* a ThingDraft

"""

class DraftMixin:
    pass

class VersionMixin:
    pass

