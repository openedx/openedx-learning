from contextvars import ContextVar
from datetime import datetime, timezone

from django.db.transaction import Atomic

from .models import DraftChangeSet


class DraftChangeSetContext(Atomic):
    """
    Context manager for batching draft changes into DraftChangeSets.

    🛑 This is a PRIVATE implementation. Outside of the publishing app, clients
    should use the draft_changes_for() API call instead of using this manager
    directly, since this is a bit experimental and the implementation may shift
    around a bit.
    
    The main idea is that we want to create a context manager that will keep
    track of what the "active" DraftChangeSet is for a given LearningPackage.
    The problem is that declaring the context can happen many layers higher in
    the stack than doing the draft changes. For instance, imagine::

        with draft_changes_for(learning_package.id):
            for section in course:
                update_section_drafts(learning_package_id, section)

    In this hypothetical code block, update_section_drafts might call a function
    to update sequences, which calls something to update units, etc. Only at the
    very bottom layer of the stack will those code paths actually alter the
    drafts themselves. It would make the API too cumbersome to explicitly pass
    the active DraftChangeSet through every layer. So instead, we use this class
    to essentially keep the active DraftChangeSet in a global (ContextVar) so
    that the publishing API draft-related code can access it later.

    Since it is possible to nest context managers, we keep a list of the
    DraftChangeSets that have been created and treat it like a stack that gets
    pushed to whenever we __enter__ and popped off whenever we __exit__.

    DraftChangeSetContext also subclasses Django's Atomic context manager, since
    any operation on multiple Drafts as part of a DraftChangeSet will want to be
    an atomic operation. 
    """
    _draft_change_sets: ContextVar[list | None] = ContextVar('_draft_change_sets', default=None)
    
    def __init__(self, learning_package_id, changed_by=None, changed_at=None):
        super().__init__(using=None, savepoint=False, durable=False)

        self.learning_package_id = learning_package_id
        self.changed_by = changed_by
        self.changed_at = changed_at or datetime.now(tz=timezone.utc)

    @classmethod
    def get_active_draft_change_set(cls, learning_package_id: int) -> DraftChangeSet | None:
        """
        Get the DraftChangeSet that new DraftChanges should be attached to.

        This is expected to be called internally by the publishing API when it
        modifies Drafts. If there is no active DraftChangeSet, this method will
        return None, and the caller should create their own DraftChangeSet.
        """
        draft_change_sets = cls._draft_change_sets.get()

        # If we've never used this manager...
        if draft_change_sets is None:
            return None

        # Otherwise, find the most recently created DraftChangeSet *that matches
        # the learning_package_id*. This is for two reasons:
        #
        # 1. We might nest operations so that we're working across multiple
        #    LearningPackages at once, e.g. copying content from different
        #    libraries and importing them into another library.
        # 2. It's a guard in case we somehow got the global state management
        #    wrong. We want the failure mode to be "we didn't find the
        #    DraftChangeSet you were looking for, so make another one and suffer
        #    a performance penalty", as opposed to, "we accidentally gave you a
        #    DraftChangeSet for an entirely different LearningPackage, and now
        #    your Draft data is corrupted."
        for draft_change_set in reversed(draft_change_sets):
            if draft_change_set.learning_package_id == learning_package_id:
                return draft_change_set

        # If we got here, then either the list was empty (the manager was used
        # at some point but exited), or none of the DraftChangeSets are for the
        # correct LearningPackage.
        return None

    def __enter__(self):
        super().__enter__()

        self.draft_change_set = DraftChangeSet.objects.create(
            learning_package_id=self.learning_package_id,
            changed_by=self.changed_by,
            changed_at=self.changed_at,
        )
        draft_change_sets = self._draft_change_sets.get()
        if not draft_change_sets:
            draft_change_sets = []
        draft_change_sets.append(self.draft_change_set)
        self._draft_change_sets.set(draft_change_sets)

        return self.draft_change_set

    def __exit__(self, type, value, traceback):
        draft_change_sets = self._draft_change_sets.get()
        if draft_change_sets:
            draft_change_sets.pop()
        self._draft_change_sets.set(draft_change_sets)

        return super().__exit__(type, value, traceback)
