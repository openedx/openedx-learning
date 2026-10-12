"""
Classes and functions to create an import plan and execution.
"""
from __future__ import annotations

from typing import NamedTuple

from attrs import define
from django.db import transaction

from ..models import Tag, TagImportTask, Taxonomy
from ..models.base import TAXONOMY_MAX_DEPTH
from .actions import (
    DeleteTag,
    ImportAction,
    RenameTagExternalId,
    StageTagExternalIdForSwap,
    UpdateParentTag,
    WithoutChanges,
    available_actions,
)
from .exceptions import (
    DuplicateFinalIdError,
    InvalidParentHierarchyError,
    ParentCycleError,
    ParentIdRenamedAwayError,
    StaleIdTargetedByPlainRowError,
    TagImportError,
)


class ExistingTag(NamedTuple):
    """
    The fields of an existing tag that the plan-level validations need.
    """

    pk: int
    parent_pk: int | None
    parent_external_id: str | None


# Existing tags by casefolded external_id.
ExistingTags = dict[str, ExistingTag]


@define
class TagItem:
    """
    Tag representation on the tag import plan
    """

    id: str
    value: str
    index: int | None = 0
    parent_id: str | None = None
    previous_id: str | None = None

    def __str__(self):
        """
        User-facing string representation of a Tag.
        """
        if self.id:
            return f"<{self.__class__.__name__}> ({self.id} / {self.value})"
        return f"<{self.__class__.__name__}> ({self.value})"


class _ParentForest:
    """
    In-memory copy of a taxonomy's parent links, used to dry-run the parent effects of import actions.

    Tags are identified by pk, and new tags get negative ids. Tags are looked up by their casefolded
    external_id, which follows renames.
    """

    def __init__(self, existing: ExistingTags):
        self.node_of: dict[str, int] = {}
        self.key_of: dict[int, str] = {}
        self.parent: dict[int, int | None] = {}
        self.children: dict[int, set[int]] = {}
        self.new_nodes = 0
        for key, info in existing.items():
            self.node_of[key] = info.pk
            self.key_of[info.pk] = key
            self.parent[info.pk] = info.parent_pk
            if info.parent_pk is not None:
                self.children.setdefault(info.parent_pk, set()).add(info.pk)

    def _depth(self, node: int) -> int:
        """
        Return the number of ancestors of ``node``.
        """
        result, ancestor = 0, self.parent.get(node)
        while ancestor is not None and result <= len(self.parent) + 1:
            result += 1
            ancestor = self.parent.get(ancestor)
        return result

    def _height(self, node: int) -> int:
        """
        Return the number of levels below ``node``, stopping once it exceeds the maximum depth.
        """
        result, level = 0, [node]
        while level and result <= TAXONOMY_MAX_DEPTH:
            level = [child for member in level for child in self.children.get(member, ())]
            result += 1 if level else 0
        return result

    def _attach(self, node: int, new_parent: int | None) -> bool:
        """
        Move ``node`` under ``new_parent``; return False if that makes a cycle or a tree too deep.
        """
        if new_parent is not None:
            ancestor: int | None = new_parent
            for _step in range(len(self.parent) + 2):
                if ancestor is None:
                    break
                if ancestor == node:
                    return False
                ancestor = self.parent.get(ancestor)
            if self._depth(new_parent) + 1 + self._height(node) > TAXONOMY_MAX_DEPTH:
                return False
        old_parent = self.parent.get(node)
        if old_parent is not None:
            self.children.get(old_parent, set()).discard(node)
        self.parent[node] = new_parent
        if new_parent is not None:
            self.children.setdefault(new_parent, set()).add(node)
        return True

    def _rekey(self, node: int, key: str) -> None:
        """
        Make ``node``, new or existing, answer to the external_id ``key``.
        """
        self.node_of.pop(self.key_of.get(node, ""), None)
        self.key_of[node] = key
        self.node_of[key] = node

    def _delete(self, key: str) -> None:
        """
        Remove the tag with external_id ``key`` and all its descendants, if it exists.
        """
        doomed = self.node_of.get(key)
        pending = [doomed] if doomed is not None else []
        while pending:
            node = pending.pop()
            pending.extend(self.children.pop(node, ()))
            old_parent = self.parent.pop(node, None)
            if old_parent is not None:
                self.children.get(old_parent, set()).discard(node)
            self.node_of.pop(self.key_of.pop(node, ""), None)

    def apply(self, action: ImportAction) -> bool:
        """
        Apply the parent effects of ``action``; return False if it would fail at execution.
        """
        tag = action.tag
        if action.name == "stage_external_id":
            if action.target_pk not in self.parent:
                return False
            self._rekey(action.target_pk, f"staged:{action.target_pk}")
        elif action.name == "delete":
            self._delete(tag.id.casefold())
        elif action.name in ("update_parent", "create", "rename_external_id"):
            new_parent = self.node_of.get(tag.parent_id.casefold()) if tag.parent_id else None
            if tag.parent_id and new_parent is None:
                return False
            if action.name == "create":
                self.new_nodes -= 1
                self.parent[self.new_nodes] = None
                if not self._attach(self.new_nodes, new_parent):
                    return False
                self._rekey(self.new_nodes, tag.id.casefold())
            elif action.name == "update_parent":
                target = self.node_of.get(tag.id.casefold())
                return target is not None and self._attach(target, new_parent)
            else:
                target = action.target_pk if action.target_pk in self.parent else None
                if target is None or not self._attach(target, new_parent):
                    return False
                self._rekey(target, tag.id.casefold())
        return True


class TagImportPlan:
    """
    Class with functions to build an import plan and excute the plan
    """

    actions: list[ImportAction]
    errors: list[TagImportError]
    indexed_actions: dict
    actions_dict: dict
    taxonomy: Taxonomy

    def __init__(self, taxonomy: Taxonomy):
        self.actions = []
        self.errors = []
        self.taxonomy = taxonomy
        self.actions_dict = {}
        self._init_indexed_actions()

    def _init_indexed_actions(self):
        """
        Initialize the `indexed_actions` dict
        """
        self.indexed_actions = {}
        for action in available_actions:
            self.indexed_actions[action.name] = []

    def _build_action(self, action_cls: type[ImportAction], tag: TagItem, target_pk: int | None = None):
        """
        Build an action with `tag`.

        Run action validation and adds the errors to the errors lists
        Add to the action list and the indexed actions
        """
        action = action_cls(self.taxonomy, tag, len(self.actions) + 1, target_pk=target_pk)

        # We validate if there are no inconsistencies when executing this action
        self.errors.extend(action.validate(self.indexed_actions))

        # Add action
        self.actions.append(action)

        # Index the actions for search
        self.indexed_actions[action.name].append(action)

    def _search_parent_update(
        self,
        child_external_id,
        parent_external_id,
    ):
        """
        Checks if there is a parent update in a child
        """
        for action in self.indexed_actions["update_parent"]:
            if (
                child_external_id == action.tag.id
                and parent_external_id != action.tag.parent_id
            ):
                return True

        return False

    def _get_tag_id(self, tag: Tag) -> str:
        """
        Get the id used on the Tag model.

        The external_id is used for import and export.
        """
        return tag.external_id

    def _build_delete_actions(self, tags: dict):
        """
        Adds delete actions for `tags`

        Every kept child is promoted to a root before the first delete, because
        deleting a tag also deletes all its descendants.
        """
        for tag in tags.values():
            for child in tag.children.all():
                # Verify if there is not a parent update before
                if not self._search_parent_update(self._get_tag_id(child), self._get_tag_id(tag)):
                    # Change parent to avoid delete childs
                    if self._get_tag_id(child) not in tags:
                        # Only update parent if the child is not going to be deleted
                        self._build_action(
                            UpdateParentTag,
                            TagItem(
                                id=child.external_id,
                                value=child.value,
                                parent_id=None,
                            ),
                        )

        for tag in tags.values():
            # Delete action
            self._build_action(
                DeleteTag,
                TagItem(
                    id=tag.external_id,
                    value=tag.value,
                ),
            )

    def _resolve_rename_target_pk(self, tag: TagItem) -> int | None:
        """
        Resolve the pk of the tag a RenameTagExternalId row targets, via its
        previous_id. Returns None if no such tag exists (an unmatched
        previous_id -- RenameTagExternalId.validate() already rejects this).
        """
        return self.taxonomy.tag_set.filter(external_id=tag.previous_id).values_list("pk", flat=True).first()

    def _validate_no_duplicate_final_ids(self, tags: list[TagItem]) -> None:
        """
        Reject two or more rows in the same import that claim the same
        final `id`, before staging or per-row action-building runs. This
        also catches a row colliding with a staged tag's target, since a
        tag is only ever staged because its external_id is already another
        row's target id.

        Without this, the outcome depended on row order: a silent
        overwrite of whichever row landed first, or an uncaught crash at
        execute time.

        Rows are identified by their 1-based position in `tags`, not
        `TagItem.index`: index is parser-assigned and optional, and left
        at its default for hand-built rows (e.g. in tests), while position
        is always defined.
        """
        positions_by_id: dict[str, list[int]] = {}
        display_id_by_key: dict[str, str] = {}
        for position, tag in enumerate(tags, start=1):
            key = tag.id.casefold()
            display_id_by_key.setdefault(key, tag.id)
            positions_by_id.setdefault(key, []).append(position)

        for key, positions in positions_by_id.items():
            if len(positions) > 1:
                self.errors.append(DuplicateFinalIdError(display_id_by_key[key], positions))

    def _validate_no_plain_row_targets_a_vacated_id(self, tags: list[TagItem]) -> None:
        """
        Reject a plain row (no previous_id) whose `id` matches another
        row's `previous_id` in the same import: that other row is renaming
        its tag away from that id, so a plain row landing on it would
        either resolve to the wrong tag or crash at execute time, depending
        on row order. A rename row landing on that same id is the
        already-supported swap/cycle case and is left alone here. The match is
        case-insensitive, like `external_id`'s own DB collation.
        """
        rename_source_rows: dict[str, int] = {}
        for position, tag in enumerate(tags, start=1):
            if tag.previous_id and tag.id != tag.previous_id:
                rename_source_rows.setdefault(tag.previous_id.casefold(), position)

        for position, tag in enumerate(tags, start=1):
            if bool(tag.previous_id) and tag.id != tag.previous_id:
                continue  # a rename row landing on that id is the already-supported swap case
            rename_row = rename_source_rows.get(tag.id.casefold())
            if rename_row is not None:
                self.errors.append(StaleIdTargetedByPlainRowError(tag.id, position, rename_row))

    def _build_staging_actions(self, tags: list[TagItem]) -> None:
        """
        Stage any tag whose current external_id is another rename row's
        target in this import, so renames never collide on external_id
        regardless of file order (see StageTagExternalIdForSwap).

        Also records every rename's resolved target pk in
        indexed_actions["_vacated_pks"] (pk -> the id it's renamed *to*), staged
        or not: once a tag is renamed away from an external_id, that id is stale
        for anyone still referencing it via the live database, even if nothing
        in this import reuses it (see _validate_parent, which uses the recorded
        new id to name it).
        """
        target_ids = {
            tag.id.casefold() for tag in tags
            if RenameTagExternalId.applies_for(self.taxonomy, tag)
        }
        vacated_pks: dict[int, str] = {}
        for tag in tags:
            if not RenameTagExternalId.applies_for(self.taxonomy, tag):
                continue
            # RenameTagExternalId.applies_for requires previous_id truthy.
            assert tag.previous_id is not None
            target_pk = self._resolve_rename_target_pk(tag)
            if target_pk is None:
                continue
            vacated_pks[target_pk] = tag.id
            is_case_only_rename = tag.previous_id.casefold() == tag.id.casefold()
            if not is_case_only_rename and tag.previous_id.casefold() in target_ids:
                self._build_action(StageTagExternalIdForSwap, tag, target_pk=target_pk)
        self.indexed_actions["_vacated_pks"] = vacated_pks

    def _existing_tags(self) -> ExistingTags:
        """
        Return the taxonomy's tags keyed by casefolded external_id, with their pk, parent pk and
        parent external_id.

        One query, so the plan-level validations don't query per row.
        """
        return {
            external_id.casefold(): ExistingTag(pk, parent_pk, parent_external_id)
            for external_id, pk, parent_pk, parent_external_id in self.taxonomy.tag_set.values_list(
                "external_id", "pk", "parent_id", "parent__external_id",
            )
        }

    def _validate_parent_id_not_stale(self, tags: list[TagItem], existing: ExistingTags) -> None:
        """
        Reject a row whose ``parent_id`` is its current parent's pre-import id
        when this import renames that parent to another id.

        The error names the parent's new id. A case-only rename is not
        flagged. After a swap, a child naming the stale id of a swapped parent
        is rejected, and one naming the end-state id is accepted. A case
        variant of the stale id counts too when a rename row claims that id,
        because ids are case-insensitive. Rows are reported by 1-based
        position in the parsed row list, not a file line. Must run after
        ``_build_staging_actions``, which fills ``indexed_actions["_vacated_pks"]``.

        :param tags: the rows of the import file, in file order.
        :param existing: the taxonomy's tags, from ``_existing_tags``.
        """
        vacated_pks: dict[int, str] = self.indexed_actions["_vacated_pks"]
        if not vacated_pks:
            return
        rename_final_ids = {
            tag.id.casefold() for tag in tags
            if tag.previous_id and tag.id != tag.previous_id
        }
        for position, tag in enumerate(tags, start=1):
            if not tag.parent_id:
                continue
            current = existing.get((tag.previous_id or tag.id).casefold())
            parent_key = tag.parent_id.casefold()
            if current is None or (current.parent_external_id or "").casefold() != parent_key:
                continue
            # An exact match is a "no change" row for UpdateParentTag.applies_for, which skips
            # _validate_parent. A case variant reaches _validate_parent as a parent change and
            # is reported there, except when a rename row claims the id: it then passes there.
            if current.parent_external_id != tag.parent_id and parent_key not in rename_final_ids:
                continue
            new_id = vacated_pks.get(current.parent_pk) if current.parent_pk is not None else None
            is_rename = bool(tag.previous_id) and tag.id != tag.previous_id
            # A rename row's own validation already reports a stale parent_id,
            # except in a swap, where the id is also another rename's final id.
            if (
                new_id is not None
                and new_id.casefold() != parent_key
                and (not is_rename or parent_key in rename_final_ids)
            ):
                self.errors.append(ParentIdRenamedAwayError(position, tag.parent_id, new_id))

    def _end_state_parents(
        self, tags: list[TagItem], existing: ExistingTags,
    ) -> tuple[dict[str, str], dict[str, int]]:
        """
        Return the end-state parent graph and the position of each id's first row.

        The graph maps a casefolded final id to its parent's casefolded final id:
        each row contributes ``id -> parent_id``, and each remaining tag (not
        named by any row's id or previous_id, and not deleted) contributes its
        id and its current parent's id, or that parent's new id if it is renamed.

        :param tags: the rows of the import file, in file order.
        :param existing: the taxonomy's tags, from ``_existing_tags``.
        :return: the graph, and the position in ``tags`` of each final id's first row.
        """
        # Not set until _build_staging_actions runs; callers may use this before it.
        vacated_pks: dict[int, str] = self.indexed_actions.get("_vacated_pks", {})
        deleted_ids = {action.tag.id.casefold() for action in self.indexed_actions["delete"]}
        parent_of: dict[str, str] = {}
        row_position: dict[str, int] = {}
        represented: set[str] = set()
        for position, tag in enumerate(tags):
            key = tag.id.casefold()
            represented.add(key)
            if tag.previous_id:
                represented.add(tag.previous_id.casefold())
            if key in row_position:
                continue
            row_position[key] = position
            if tag.parent_id:
                parent_of[key] = tag.parent_id.casefold()
        for key, tag_info in existing.items():
            parent_id = tag_info.parent_external_id
            if key in represented or key in deleted_ids or tag_info.parent_pk is None or parent_id is None:
                continue
            if parent_id.casefold() in deleted_ids:
                continue
            parent_of[key] = vacated_pks.get(tag_info.parent_pk, parent_id).casefold()
        return parent_of, row_position

    def _validate_no_parent_cycles(self, tags: list[TagItem], existing: ExistingTags) -> None:
        """
        Reject a row whose ``parent_id`` makes a tag its own ancestor (a
        self-parent is a cycle of length one) once this import is applied.

        The check runs on the end-state graph from ``_end_state_parents``. A cycle
        is reported once, on its first row in the parsed row list.
        A cycle of definer rows is skipped only when none of its ids is held by
        an existing tag, because only then does ``_validate_parent`` report it
        (as an unknown parent). Must run after ``_build_staging_actions``.

        :param tags: the rows of the import file, in file order.
        :param existing: the taxonomy's tags, from ``_existing_tags``.
        """
        parent_of, row_position = self._end_state_parents(tags, existing)
        is_definer_row = {key: self._defines_id(tags[position], existing) for key, position in row_position.items()}

        state: dict[str, int] = {}  # 1 on the current path, 2 once fully walked
        for tag in tags:
            path: list[str] = []
            node: str | None = tag.id.casefold()
            while node is not None and node not in state:
                state[node] = 1
                path.append(node)
                node = parent_of.get(node)
            if node is not None and state[node] == 1:
                cycle = path[path.index(node):]
                rows = [row_position[key] for key in cycle if key in row_position]
                # _validate_parent only reports a cycle of definer rows when no
                # id in it is held by an existing tag (it finds that one in the DB).
                if rows and (
                    not all(is_definer_row.get(key, False) for key in cycle)
                    or any(key in existing for key in cycle)
                ):
                    position = min(rows)
                    self.errors.append(ParentCycleError(position + 1, tags[position].parent_id or ""))
            for key in path:
                state[key] = 2

    @staticmethod
    def _defines_id(tag: TagItem, existing: ExistingTags) -> bool:
        """
        Return whether the row defines its final id: it is a rename row, or it
        creates a tag, so the id is not held by an existing tag.
        """
        is_rename = bool(tag.previous_id) and tag.id != tag.previous_id
        return is_rename or tag.id.casefold() not in existing

    def _order_rows_by_parent_dependency(self, tags: list[TagItem], existing: ExistingTags) -> list[TagItem]:
        """
        Return ``tags`` reordered so that parent references resolve and no move
        builds a cycle.

        A row follows the row that defines its ``parent_id`` (a rename row or a
        new-tag row with that final id, case-insensitive). A row that moves an
        existing tag under a new parent also follows the rows of the tags on
        that parent's end-state ancestor chain that currently sit inside its
        subtree, so a move out of a subtree runs before a move into it.
        Validation and execution both follow action order, so this makes both
        independent of row order. Only a row and its dependencies are moved:
        unrelated rows between them end up after both. Rows that are already in
        a valid order keep their position, so their plan is unchanged.

        :param tags: the rows of the import file, in file order.
        :param existing: the taxonomy's tags, from ``_existing_tags``.
        """
        definers: dict[str, int] = {}
        for position, tag in enumerate(tags):
            if self._defines_id(tag, existing):
                definers.setdefault(tag.id.casefold(), position)
        parent_of, row_position = self._end_state_parents(tags, existing)
        parent_pk_of = {info.pk: info.parent_pk for info in existing.values()}

        def dependencies(position: int) -> list[int]:
            """
            Return the positions of the rows that must run before the row at ``position``.
            """
            tag = tags[position]
            if not tag.parent_id:
                return []
            result = []
            definer = definers.get(tag.parent_id.casefold())
            if definer is not None:
                result.append(definer)
            current = existing.get((tag.previous_id or tag.id).casefold())
            if current is None:
                return result
            node: str | None = tag.parent_id.casefold()
            visited: set[str] = set()
            while node is not None and node not in visited:
                visited.add(node)
                q_position = row_position.get(node)
                q_row = tags[q_position] if q_position is not None else None
                q_current = existing.get((q_row.previous_id or q_row.id).casefold()) if q_row else None
                if q_current is not None and q_current.pk != current.pk:
                    ancestor_pk = q_current.parent_pk
                    while ancestor_pk is not None and ancestor_pk != current.pk:
                        ancestor_pk = parent_pk_of.get(ancestor_pk)
                    if ancestor_pk is not None and q_position is not None:
                        result.append(q_position)
                node = parent_of.get(node)
            return result

        return self._order_by_dependencies(tags, [dependencies(position) for position in range(len(tags))])

    @staticmethod
    def _order_by_dependencies(tags: list[TagItem], dependencies: list[list[int]]) -> list[TagItem]:
        """
        Return ``tags`` in an order where each row follows the rows listed in
        ``dependencies[position]``, keeping file order otherwise. A dependency
        cycle is broken at its second visit, leaving a best-effort order.
        """
        ordered: list[int] = []
        seen: set[int] = set()  # emitted or in progress; the latter breaks cycles
        for start in range(len(tags)):
            stack = [(start, False)]
            while stack:
                position, done = stack.pop()
                if done:
                    ordered.append(position)
                    continue
                if position in seen:
                    continue
                seen.add(position)
                stack.append((position, True))
                stack.extend((dependency, False) for dependency in reversed(dependencies[position]))
        return [tags[position] for position in ordered]

    def _order_rows_parent_first(self, tags: list[TagItem], existing: ExistingTags) -> list[TagItem]:
        """
        Return ``tags`` with each row after the row whose final id is its ``parent_id``.

        :param tags: the rows of the import file, in file order.
        :param existing: the taxonomy's tags, from ``_existing_tags``.
        """
        _parent_of, row_position = self._end_state_parents(tags, existing)
        dependencies = [
            [row_position[tag.parent_id.casefold()]]
            if tag.parent_id and row_position.get(tag.parent_id.casefold(), position) != position else []
            for position, tag in enumerate(tags)
        ]
        return self._order_by_dependencies(tags, dependencies)

    def _build_detach_actions(self, tags: list[TagItem], existing: ExistingTags) -> None:
        """
        Add an update-to-root action for every existing tag whose row changes its parent.

        After these actions every remaining parent link is an unchanged one, so no later step
        sees a tree deeper or more cyclic than the final one. Tags that the delete phase has
        already promoted are skipped. Must run before ``_build_staging_actions``, because the
        actions find their tag by its pre-import external_id.

        :param tags: the rows of the import file, in file order.
        :param existing: the taxonomy's tags, from ``_existing_tags``.
        """
        end_id_by_pk: dict[int, str] = {}
        for tag in tags:
            current = existing.get((tag.previous_id or tag.id).casefold())
            if current is not None:
                end_id_by_pk.setdefault(current.pk, tag.id)
        deleted_ids = {action.tag.id.casefold() for action in self.indexed_actions["delete"]}
        for tag in tags:
            current = existing.get((tag.previous_id or tag.id).casefold())
            if current is None or current.parent_pk is None or current.parent_external_id is None:
                continue
            if current.parent_external_id.casefold() in deleted_ids:
                continue  # already promoted by the delete phase
            parent_end_id = end_id_by_pk.get(current.parent_pk, current.parent_external_id).casefold()
            if (tag.parent_id or "").casefold() != parent_end_id:
                self._build_action(
                    UpdateParentTag, TagItem(id=tag.previous_id or tag.id, value=tag.value, parent_id=None),
                )

    def _parent_changes_are_valid(self, existing: ExistingTags) -> bool:
        """
        Return whether every parent change in the built actions leaves a valid tree.

        Actions run in order and ``Tag.save`` validates the depth of each step, so a plan can
        fail at execution although its end state is valid. This simulates the parent effects of
        ``self.actions`` in memory, with no database access, and returns False if a step would
        exceed ``TAXONOMY_MAX_DEPTH``, use a tag that an earlier step removed, or create a cycle
        (a second guard: ``_validate_no_parent_cycles`` already rejects cyclic end states).

        :param existing: the taxonomy's tags, from ``_existing_tags``.
        """
        forest = _ParentForest(existing)
        return all(forest.apply(action) for action in self.actions)

    def generate_actions(
        self,
        tags: list[TagItem],
        replace=False,
    ):
        """
        Reads each tag and generates the corresponding actions.

        Validates each action and create respective errors
        If `replace` is True, then creates the delete action for tags
        that are in the existing taxonomy but not the new tags list.

        TODO: Join/reduce actions. Ex. A tag may have no changes,
        but then its parent needs to be updated because its parent is deleted.
        Those two actions should be merged.
        """
        existing = self._existing_tags()
        self._generate_actions(tags, replace, existing, safe=False)
        # A plan whose intermediate states would be invalid is rebuilt detach-first. If that
        # is still invalid, no order of the actions works.
        if not self.errors and not self._parent_changes_are_valid(existing):
            self._generate_actions(tags, replace, existing, safe=True)
            if not self._parent_changes_are_valid(existing):
                self.errors.append(InvalidParentHierarchyError(TAXONOMY_MAX_DEPTH + 1))

    def _generate_actions(self, tags: list[TagItem], replace: bool, existing: ExistingTags, safe: bool) -> None:
        """
        Build the actions for ``tags``, with the rows ordered by ``_order_rows_by_parent_dependency``.

        In ``safe`` mode the existing tags whose parent changes are first detached to roots and
        the rows are ordered by ``_order_rows_parent_first`` instead.
        """
        self.actions.clear()
        self.errors.clear()
        self._init_indexed_actions()

        # Reject two or more rows claiming the same final id outright,
        # before staging or per-row action-building runs (see
        # _validate_no_duplicate_final_ids).
        self._validate_no_duplicate_final_ids(tags)

        # Reject a plain row that targets an id another row is renaming
        # away from in this same import (see
        # _validate_no_plain_row_targets_a_vacated_id).
        self._validate_no_plain_row_targets_a_vacated_id(tags)

        tags_for_delete = {}

        if replace:
            tags_for_delete = {
                self._get_tag_id(tag): tag for tag in self.taxonomy.tag_set.all()
            }
            # external_id is case-insensitive in the DB, so both pops below
            # must match regardless of case too.
            delete_keys_by_fold = {key.casefold(): key for key in tags_for_delete}

            for tag in tags:
                # A rename row's `id` is the new target, not confirmation
                # that the tag currently holding that external_id should be
                # kept: only `previous_id` protects an existing tag from
                # this delete sweep in that case.
                is_rename = bool(tag.previous_id) and tag.id != tag.previous_id
                if not is_rename:
                    key = delete_keys_by_fold.get(tag.id.casefold())
                    if key is not None:
                        tags_for_delete.pop(key, None)
                if tag.previous_id:
                    key = delete_keys_by_fold.get(tag.previous_id.casefold())
                    if key is not None:
                        tags_for_delete.pop(key, None)

            # Delete all not readed tags
            self._build_delete_actions(tags_for_delete)

        if safe:
            self._build_detach_actions(tags, existing)

        # Stage tags whose external_id is contended by another rename row in
        # this same import, so a swap or an N-cycle of renames has a valid
        # execution order regardless of how the rows are ordered in the file.
        self._build_staging_actions(tags)

        # Reject parent references that the per-row actions never validate.
        self._validate_parent_id_not_stale(tags, existing)
        self._validate_no_parent_cycles(tags, existing)

        if safe:
            rows = self._order_rows_parent_first(tags, existing)
        else:
            rows = self._order_rows_by_parent_dependency(tags, existing)
        for tag in rows:
            has_action = False

            # Check all available actions and add which ones should be executed
            for action_cls in available_actions:
                if action_cls.applies_for(self.taxonomy, tag, self.indexed_actions):
                    target_pk = (
                        self._resolve_rename_target_pk(tag)
                        if action_cls is RenameTagExternalId else None
                    )
                    self._build_action(action_cls, tag, target_pk=target_pk)
                    has_action = True

            if not has_action:
                # If it doesn't find an action, a "without changes" is added
                self._build_action(WithoutChanges, tag)

    def plan(self) -> str:
        """
        Returns an string with the plan and errors
        """
        result = (
            f"Import plan for {self.taxonomy.name}\n"
            "--------------------------------\n"
        )
        for action in self.actions:
            result += f"#{action.index}: {str(action)}\n"

        if self.errors:
            result += "\nOutput errors\n" "--------------------------------\n"
            for error in self.errors:
                result += f"{str(error)}\n"

        return result

    @transaction.atomic()
    def execute(self, task: TagImportTask | None = None):
        """
        Executes each action

        If task is set, creates logs for each action
        """
        if self.errors:
            return
        for action in self.actions:
            # Avoid to save each log because it is slow and costs a lot in memory
            # It is necessary to save at the end.
            if task:
                task.add_log(f"#{action.index}: {str(action)} [Started]", save=False)
            action.execute()
            if task:
                task.add_log("Success", save=False)
        if task:
            task.save()
