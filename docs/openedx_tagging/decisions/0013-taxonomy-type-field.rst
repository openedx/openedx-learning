.. _openedx-tagging-adr-0013:

13. Base-model ``taxonomy_type`` field for Competency Taxonomies
==================================================================

Status
------

Proposed

Context
-------

The taxonomy Get endpoints (``TaxonomySerializer``) need to report whether a taxonomy is
a Competency Taxonomy, so that Studio can badge Competency Taxonomies and gate access to
the Competency Management page (#618), symmetrically with the Create/Import endpoint's
``taxonomy_type`` field (#614). ``CompetencyTaxonomy`` is a Django multi-table-inheritance
subclass of ``Taxonomy`` (``CompetencyTaxonomy(Taxonomy)``), owned by the CBE applet and
defined in `ADR 0002 <../../openedx_learning/decisions/0002-competency-criteria-model.rst>`_.

``openedx_tagging`` is a generic tagging library with no knowledge of any specific taxonomy
flavor built on top of it, CBE or otherwise, and must not gain any: a specific downstream
applet's model or relation name has no business appearing in this library's source, since
that reverses the intended dependency direction (CBE depends on ``openedx_tagging``, not
the other way around) and would break for any Open edX install running ``openedx_tagging``
without CBE installed.

Two approaches were tried on #618 and found unsound; see Rejected Alternatives.

This decision does not reopen `ADR 0002 <../../openedx_learning/decisions/0002-competency-criteria-model.rst>`_'s
rejection of a flat ``taxonomy_type`` column as an alternative to multi-table inheritance.
That rejection's deciding reason was that a flat column can't give other CBE tables a
real, database-enforced foreign key to specifically a competency-enabled taxonomy;
``CompetencyRuleProfile.competency_taxonomy_id`` relies on that guarantee. That reasoning
is independent of whether ``CompetencyTaxonomy`` currently defines any columns of its own
beyond the parent link, and is unaffected by this decision. This decision addresses a
narrower, later problem ADR 0002 does not cover: a lightweight type label for
``openedx_tagging``'s own generic REST API.

Decision
--------

Add a ``taxonomy_type`` field directly to ``Taxonomy``:

- A ``TaxonomyType(models.TextChoices)`` enum with values ``TAGS`` (default) and
  ``COMPETENCY``, shared between this field and #614's write-side ``ChoiceField`` so the
  two can never drift apart.
- Set explicitly by whichever code creates the row. The code that creates a
  ``CompetencyTaxonomy`` row (#614) also sets ``taxonomy_type=TaxonomyType.COMPETENCY`` on
  the same ``Taxonomy`` row, in the same transaction that creates both rows (the existing
  lifecycle rule in ADR 0002 Decision 1). ``openedx_tagging`` never inspects, imports, or
  names ``CompetencyTaxonomy`` or any relation to it anywhere in its own source; the field's
  value is opaque to it and owned entirely by the caller.
- Immutable after creation, mirroring the scope-immutability precedent for
  ``CompetencyRuleProfile`` in ADR 0002 Decision 3: a taxonomy's type does not change over
  its lifetime.
- Existing taxonomies are backfilled to ``TaxonomyType.TAGS`` via an additive migration;
  none has a ``CompetencyTaxonomy`` row today, since CBE has no production data yet.
- Exposed read-only on ``TaxonomySerializer`` (#618), returning the field's value directly.

**Known tradeoff.** This creates two facts that must stay in sync: the field's value, and
whether a ``CompetencyTaxonomy`` row actually exists for that taxonomy. This is accepted
because it is enforced at a single transactional chokepoint (the creation path for a
``CompetencyTaxonomy``), not as an ongoing invariant that application code must maintain
across multiple call sites.

Future considerations
~~~~~~~~~~~~~~~~~~~~~~

If a third taxonomy flavor is introduced later, it extends this same field and enum with a
third value; no schema redesign is implied. This field is not a general-purpose
polymorphism mechanism and does not preclude one being added separately if a future need
requires it.

Rejected Alternatives
----------------------

Check for a related ``CompetencyTaxonomy`` row directly inside ``openedx_tagging``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The original #618 proposal: ``hasattr(instance, "competencytaxonomy")`` inside
``openedx_tagging``'s serializer. Rejected because it hardcodes a specific downstream
applet's multi-table-inheritance relation name into a standalone, generic library, which
is exactly the reverse-dependency problem this decision exists to avoid.

An overridable ``Taxonomy.get_type()`` method
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The follow-up #618 proposal: a base ``Taxonomy.get_type()`` method returning ``"tags"``,
overridden by ``CompetencyTaxonomy`` to return ``"competency"``, mirroring the existing
``Taxonomy.system_defined`` / ``SystemDefinedTaxonomy`` base/override shape. Rejected for
two independent reasons:

- That base/override shape is implemented via ``Taxonomy._taxonomy_class`` and
  ``Taxonomy.cast()``/``Taxonomy.copy()``, which #634 (Remove Taxonomy Subclasses) removes.
- Independent of #634: querying taxonomies the normal way (``Taxonomy.objects.all()``)
  returns plain ``Taxonomy`` instances, so a subclass method override is never reached
  without an explicit cast step first. The existing ``.cast()``/``.copy()`` implementation
  would not correctly perform that cast for a true multi-table-inheritance subclass in any
  case: it copies a hardcoded list of base ``Taxonomy`` field values in Python and never
  queries the subclass's own table, so it would silently produce a ``CompetencyTaxonomy``
  instance with unset or wrong subclass-specific fields.

Frontend-only: no backend field
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Studio determines type by combining ``openedx_tagging``'s generic taxonomy list with a
separate, CBE-owned endpoint client-side. Rejected because it gives no answer to any
in-process backend consumer of this published library (other apps, plugins, management
commands), only to whichever frontend chooses to make two calls and join them, and it
pushes the integration cost of that join onto every future consumer rather than paying it
once.

A settings-configured resolver function
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A Django setting pointing at a dotted import path to a resolver function, owned by CBE,
that ``Taxonomy.get_type()`` calls if configured. This would have kept the type-detection
logic entirely out of ``openedx_tagging``'s own source. Rejected because it is a new,
bespoke, ad-hoc hook into ``openedx_tagging``, when this project's established pattern for
a cross-app extension point, if one is genuinely needed, is ``openedx-events``/
``openedx-filters`` rather than a one-off settings hook. Reaching for that established
pattern instead would mean depending on and wiring up a plugin/event framework across
repos for a field with exactly two known values today -- more machinery than either this
alternative or the field approach chosen here, not less.

Changelog
---------

2026-07-16:

* Proposed.
