.. _openedx-tagging-adr-0010:

10. Institution-defined tag code field
========================================

Status
------

Proposed

Context
-------

`Issue #625 <https://github.com/openedx/openedx-core/issues/625>`_ asks the project to
determine an ID field strategy for Competency-Based Education (CBE) competency data.
Competency Management UX designs show a "Competency ID" on each competency tag: a
short, human-readable identifier an institution can reference in its own systems
(spreadsheets, internal catalogs, etc). Clicking it drives the workflow that
creates a ``CompetencyCriteria`` association between the competency and content
criteria rules.

This identifier is explicitly **not** a CASE or CTDL identifier. Those are external
standards bodies' IDs that may need their own storage in the future; conflating them
with an institution's internal code would make each harder to reason about
independently. This ADR is scoped to the internal, institution-defined code only.

``Tag`` already has three identifiers, none of which fit:

- ``id``: internal primary key, never user-visible.
- ``uuid``: stable external reference, not human-readable or institution-assigned.
- ``external_id``: intended to link a Tag to a record in an externally-defined
  taxonomy. It is de facto immutable: no API path mutates it after creation, tag
  re-sync code documents it as "must be an immutable ID", and import/export uses it
  purely as the lookup key to find and update existing tags on re-import. Repurposing
  it as an admin-editable Competency ID would conflict with that existing, load-bearing
  contract.

**Placement constraint.** :ref:`openedx-learning-adr-0001` keeps ``openedx_tagging``
standalone and rejected putting CBE tables inside it for that reason. A CBE-named
field on ``Tag`` would repeat that mistake, but a single scalar identifier — the same
shape ``external_id`` already fills — does not. Every taxonomy listing, search, and
export already reads ``Tag``; putting a per-tag identifier in a separate app would
force a cross-app join into that common path for what is otherwise a plain string
column.

Decision
--------

Add a new field, ``Tag.code``, to ``openedx_tagging`` as a **generic**,
non-CBE-specific identifier slot, available to any taxonomy:

- A plain, optional text field, matching ``external_id``'s shape.
- **Uniqueness:** enforced per-taxonomy, not globally unique (different
  institutions/taxonomies may reasonably reuse a code) and not advisory-only (the CBE
  workflow uses this value as a click target to create a ``CompetencyCriteria``
  association; ambiguity within a taxonomy would be a routing bug, not a
  data-quality nit).
- **Assignment:** user-entered when given in initial import; every non-Competency taxonomy leaves
  ``code`` fully optional with no fallback. For a Competency Taxonomy, every tag
  needs one: creating a new tag without a code — via import, or via the existing
  Taxonomy Editing UI, which has no field for it yet — generates a placeholder (e.g.
  derived once from the tag's current name and position) instead of blocking the
  tag's creation or an otherwise-valid import. If a user forgets to include the code column in their initial import, they can overwrite the placeholder
  with their real code through a follow-up re-import, the same way any other field
  is corrected. Re-importing an *existing* tag whose code is blank in the file leaves
  its current value untouched rather than generating a new one — a blank cell isn't a
  request to clear it since that is not allowed for Competency Taxonomies.
- **Completeness for Competency Taxonomies:** every tag in a Competency Taxonomy must
  have a ``code``, guaranteed either by an explicit value or the placeholder fallback
  above; every other taxonomy leaves it fully optional (see below for how this is
  enforced without ``openedx_tagging`` knowing what a Competency Taxonomy is).
- **Read exposure:** ``code`` is exposed read-only outside of import, so it can still
  be displayed on the Competency Management page and assignment workflow even though
  it isn't editable there yet (planned for a later phase).
- **Migration:** additive only — a new nullable field, no backfill needed. No PII
  annotation is required: ``code`` is institution-authored administrative metadata,
  not personal data.

This keeps ``openedx_tagging`` free of CBE-specific concepts: the word "Competency"
never needs to appear in this app. The CBE applet's API and UI are responsible for
labeling ``code`` as "Competency ID" and driving the click-through workflow.

Completeness rule for Competency Taxonomies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``openedx_tagging`` must not need to know what a "Competency Taxonomy" is to enforce
completeness, per the placement constraint above. The base ``Taxonomy`` class gets a
property that defaults to "not required"; a taxonomy subclass defined outside
``openedx_tagging`` overrides it to require a code. This mirrors the existing
extension pattern already used for system-defined taxonomies, where a subclass living
in another package customizes behavior without ``openedx_tagging`` importing it. The
rule is enforced at the point a tag is saved, so every path that creates one — import,
the existing Taxonomy Editing UI, or the generic API — is covered by one check rather
than one per caller, and none of them can accidentally create a code-less tag.

Import/export
~~~~~~~~~~~~~~

``code`` becomes an optional column in the import file format for every taxonomy. A
new tag with no ``code`` gets the placeholder fallback described above, whether it's
a Competency Taxonomy tag created via import or via the UI. Re-importing an existing
tag never clears or regenerates its ``code`` just because the file's column is blank
for that row; it only changes when the file supplies an explicit new value.

How a Competency Taxonomy itself gets created is out of this ADR's scope — that is
already covered by separate, in-progress work. This ADR's changes don't depend on
that work landing first, and don't introduce any new API endpoints of their own.

Rejected Alternatives
----------------------

Repurpose ``external_id``
~~~~~~~~~~~~~~~~~~~~~~~~~~

Reuse the existing ``external_id`` field instead of adding a new one. Rejected:
``external_id`` is de facto immutable and is the load-bearing lookup key for
import/export matching and system-defined-taxonomy re-sync. Giving it a second,
editable meaning would break that existing contract.

CBE-specific field directly on ``Tag``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add a field explicitly named and documented as the "Competency ID" on ``Tag``, as a
deliberate exception to :ref:`openedx-learning-adr-0001`'s boundary. Rejected: this is
the same schema location as the chosen decision, but naming it as a CBE concept bakes
domain semantics into a library meant to stay standalone, for no benefit over the
generic framing.

Competency-specific field in ``openedx_learning``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add the identifier to a model in the new ``openedx_learning`` app instead, referenced
from ``Tag``. Rejected: this value is display data needed by every competency tag
listing, search, and export. A cross-app join for a plain string column adds cost with
no corresponding benefit, and no table in that app has the right cardinality (one row
per tag, not per taxonomy or per criterion).

``CompetencyTaxonomy`` as the home
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Attach the identifier to the ``CompetencyTaxonomy`` row itself. Rejected on
cardinality: ``CompetencyTaxonomy`` is one row per taxonomy; a Competency ID is one
value per tag.

Keep every code continuously derived from the tag's name and hierarchy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Treat the code as a live, computed value (e.g. ``PK-1.2``) that stays in sync with
the tag's current name and position, rather than a value the institution owns once
it exists. Rejected: once a tag has any code — real or a placeholder from the
fallback above — only a re-import changes it. Continuously recomputing it on every
rename or move would contradict that and mean the institution never really owns the
value once assigned.

Global uniqueness
~~~~~~~~~~~~~~~~~~

Enforce uniqueness across all taxonomies. Rejected: overreaches into assuming a
single global namespace for institution-chosen codes, which a shared library
shouldn't impose.

Advisory-only uniqueness
~~~~~~~~~~~~~~~~~~~~~~~~~

No database constraint, just a UI warning on collision. Rejected: the field is a
click target for creating a ``CompetencyCriteria`` association; a duplicate within a
taxonomy is a functional ambiguity, not just a data-quality nit.

Enforce completeness only during import, not at the model level
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Rejected: tags can already be created outside the import path today, through the
existing Taxonomy Editing UI or the generic tag-creation API, neither of which has a
way to supply a code directly. Enforcing the rule only during import would let those
paths silently create a code-less tag instead of falling back to a placeholder.

Changelog
---------

2026-07-03:

* Proposed.
