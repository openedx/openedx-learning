11. Taxonomy and tag changes
============================

Context
-------

Tagging content may be a labor-intensive, and the data produced is precious, both for human and automated users. Content tags should be structured and namespaced according to the needs of the instance's taxonomy administrators. But taxonomies themselves need to allow for changes: their tags can be overridden with a single import, they can be deleted, reworked, and their rules changed on the fly.

What happens to the existing content tags if a Taxonomy or Tag is renamed, moved, or deleted?

Decision
--------

Preserve content tag name:value pairs even if the associated taxonomy or tag is removed.
Reflect name:value changes from the linked taxonomy:tag immediately to the user.

Content tags (through their base ObjectTag class) store a foreign key to their Taxonomy and Tag (if relevant), but they also store a copy of the Taxonomy.name and Tag.value, which can be used if there is no Taxonomy or Tag available.

We consult the authoritative Taxonomy.name and Tag.value whenever displaying a content tag, so any changes are immediately reflected to the user.

If a Taxonomy or Tag is deleted, the linked content tags will remain, and cached copies of the name:value pair will be displayed.

This cached "value" field enables content tags (through their base ObjectTag class) to store free-text tag values, so that the free-text Taxonomy itself need not be modified when new free-text tags are added.

This extra storage also allows tagged content to be imported independently of a taxonomy. The taxonomy (and appropriate tags) can be constructed later, and content tags validated and re-synced by editing the content tag or by running a maintenance command.

Rejected Alternatives
---------------------

Require foreign keys
~~~~~~~~~~~~~~~~~~~~

Require a foreign key from a content tag to Taxonomy for the name, and Tag for the value.

Only using foreign keys puts the labor-intensive content tag data at risk during taxonomy changes, and requires free-text tags to be made part of a taxonomy.
