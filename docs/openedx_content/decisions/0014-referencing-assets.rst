.. _openedx-content-adr-0014:

14. Referencing Assets
======================

Status
------

Draft. Depends on :ref:`openedx-content-adr-0005`, :ref:`openedx-content-adr-0012` and :ref:`openedx-content-adr-0013`.

Context
-------

:ref:`openedx-content-adr-0013` introduces "Assets" (also called "shared assets") to hold shared asset files within a learning package. This ADR decides how content refers to those files, and to the files attached directly to a component.

Today, course content references assets in one of two ways:

**Portable URLs**, e.g. ``/static/Time_medium_icon.png``.
  These resolve against a single course-wide namespace of files, and must be rewritten before they can be served. They technically share a namespace with Studio's built-in assets (e.g. ``/static/studio/css/studio-main-v1.css``). However, since user-authored content generally does not reference Studio's built-in JS/CSS files, any usage of ``"/static/..."`` or ``'/static/...'`` in XBlock OLX is assumed to be referring to course Files, and will be rewritten to the form shown below before being served to the user.

**Asset key URLs**, e.g. ``https://courses.example.com/asset-v1:HarvardX+StudioAdv1+2T2019+type@asset+block@Time_medium_icon.png`` or sometimes just ``/asset-v1:HarvardX+StudioAdv1+2T2019+type@asset+block@Time_medium_icon.png``
  These are unambiguous, but they encode the course run key and sometimes the hostname, so they can break when content is copied to a new run (every rerun), to another course, or to another instance, and the original version is deleted or modified. Technically, the ``asset-v1:...`` opaque key part could be used as an identifier on its own, but this rarely occurs in practice.

For backwards compatibility, both of these formats must continue to be supported indefinitely.

Of the two, only the ``/static/`` format is portable, so it is the one we build on. Its weakness is detection: ``/static/`` can occur in many unrelated contexts, so the system currently limits auto-detection to *quoted* URLs like ``"/static/blah"``, which means that any reference that is not quoted as expected (e.g. something on its own line in the text or something like ``&quot;/static/...&quot;``) will not be detected.

Decisions
---------

1. Assets can be referenced using the existing ``/static/`` URL format, improved
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When editing an XBlock Component (stored in ``openedx_content``, not modulestore), whether using a visual editor or editing OLX directly, users who want to reference a static asset file (e.g. embed an image) can browse through all files attached to the current component (with the ``/static/`` prefix to indicate they're public), as well as all shared assets in the course (or copied/linked into the course from a library). They can then use the existing ``/static/`` path prefix to identify that asset::

    /static/filename.ext

For example, for an HTML component that wants to use the Asset ``moon-orbit.svg``:

.. code-block:: html

    <img src="/static/moon-orbit.svg">

However, the existing "URL rewriting" code for detecting ``/static/x`` references only detects them if they are quoted in either single quotes or double quotes. This does not detect other situations like ``&quot;/static/triangle.png&quot;`` which occurs in the Drag and Drop XBlock's OLX, JSON-escaped references like ``\/static\/triangle.png`` inside JSON stored in an OLX field, nor plain text references where ``/static/x`` is on its own line.

To improve this, the updated ``/static/`` detection should detect any occurrence of ``/static/...`` that is not preceded by a word character, hyphen, or period.

TODO: Legacy paths can contain spaces, parentheses and other punctuation, so some paths like ``/static/image 001.png`` that are ambiguous unless quoted may still only be detected if quoted/escaped. Investigate this during implementation.

2. References prefer component assets over shared assets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Imagine a course with ``solar-system.svg`` and ``earth.svg`` as shared assets in the Course Files area.

If that course contains an HTML Component (an ``html`` XBlock) with ``earth.svg`` attached as an asset file, then any reference that XBlock makes to ``/static/earth.svg`` will refer to the local ``earth.svg`` attached to the Component, not to the shared ``earth.svg`` Asset used by the overall course. But a reference to ``/static/solar-system.svg`` will use the shared asset from Course Files, since there is no local asset file with that name attached to the HTML Component.

3. References using ``/static/`` URLs are tracked as dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When editing an XBlock/Component such as a Text (HTML) component, course authors can freely copy and paste ``/static/`` references into the HTML/OLX to reference any available shared assets in the course (including ones copied from content libraries). When the author saves their changes, the OLX will be scanned for ``/static/`` references using the improved detection from decision 1, and each reference will be resolved as described in decision 2. As part of saving the new ``ComponentVersion``, the system will create a :class:`PublishableEntityVersionDependency` from the component version to any shared assets used. (References that resolve to the component's own attached files need no dependency.)

This means the existing side-effect machinery works unchanged: editing a draft Asset marks every component that uses it as having unpublished changes, and the publish log records the change against those components as well. It also answers "where is this asset used?" with a query instead of by parsing content.

⚠️ However, note that on its own, this cannot detect relative references among Assets. For example, if an Asset ``example.html`` references ``<img src="image.png">``, then there is a dependency between ``example.html`` and ``image.png`` that is not represented by a :class:`PublishableEntityVersionDependency`. We can attempt to reduce the occurrence of this by scanning HTML files for references as well, but that is not going to be particularly reliable and could also generate circular dependencies, which the ``set_version_dependencies`` API says should be avoided.

4. Unresolved references create placeholder Assets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Authors will sometimes save a component that references ``/static/foo.png`` before ``foo.png`` has been uploaded, or after it has been deleted. Rendering is unaffected, since references are resolved by name at render time, but without a :class:`PublishableEntityVersionDependency` the side-effect machinery from decision 3 would not apply once the file is uploaded: the component would not show as having unpublished changes, publishing it would not publish ``foo.png``, and "where is this asset used?" would miss it.

To avoid this, when a ``/static/`` reference does not match any attached asset or shared asset, the system will create a *placeholder* Asset: an :class:`Asset` with the referenced filename, but with no versions. The dependency is then created as usual, because :class:`PublishableEntityVersionDependency` references an entity, not a version.

When a file with that name is later uploaded, it becomes the first version of the placeholder rather than a new :class:`Asset`, and the normal draft side effects mark every referencing component as having unpublished changes. This also means a never-uploaded file and a deleted Asset end up in the same state: an entity with no current draft version, which other component versions still depend on.

Additional rules:

- No placeholder is created if the referencing component has an attached asset file with that name (decision 2).
- A placeholder is identified by being an :class:`Asset` with no versions at all. Placeholders are excluded from regular Asset listings, export, and search indexing.
- Placeholders that no longer have any dependents (e.g. typos that were later fixed) can be hard-deleted, since they never had any content. The ``on_delete=RESTRICT`` on ``referenced_entity`` ensures a placeholder that is still referenced cannot be deleted by mistake.
- When a component referencing a placeholder is copied to another Learning Package (decision 5), a placeholder is created in the destination too.

5. Conflicting shared assets are renamed when copied to another Learning Package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When an XBlock Component with references to shared assets is pasted/copied from one Learning Package to another, e.g. from a library to a course, or from a library to another library, the shared Assets that it references are copied along with it. The OLX of the copied Component should **only change when necessary to avoid a filename conflict**. So if the Component has some HTML like ``<img src="/static/example5.png" alt="Example" />``, it is copied unchanged unless the destination Learning Package already has an unrelated Asset named ``example5.png``.

Each referenced Asset is handled as follows:

1. If the destination Learning Package already has an Asset that is a downstream copy of the same upstream Asset (see decision 7), that existing copy is reused, under whatever filename it has in the destination.
2. Otherwise, if the destination Learning Package already has an Asset with an identical filename and file hash, it is reused.
3. Otherwise, if the destination Learning Package has no Asset with that filename (or only a placeholder, per decision 4), the Asset is copied under the same filename.
4. Otherwise, the destination has a conflicting Asset with the same filename but different content. The Asset is copied under a new, unique filename, and the ``/static/`` references to it in the copied Component's OLX are rewritten to use the new filename. The scheme for choosing the new filename (e.g. a prefix or suffix derived from the source context) is left to the implementation.

In every case, a :class:`PublishableEntityVersionDependency` is created from the copied Component's version to the Asset it uses in the destination, and an Asset copied from a library is tracked as a downstream of the library Asset (decision 7). Copied Assets keep their ``locked`` and ``private`` flags.

When a downstream Component is later synced from its upstream, its new OLX is copied and the same rules apply. Rule 1 finds each previously copied Asset, including renamed ones, so the same rewrite is applied again and the downstream Component keeps using the same Asset copies. Code that compares an upstream Component's OLX to its downstream copy must account for these rewritten references.

Renaming cannot fix references that are not detected by decision 1, such as relative references from a renamed HTML Asset to other Assets, or implicit references by filename. In particular, a conflicting ``python_lib.zip`` cannot be renamed without breaking the problems that use it, so a conflict on ``python_lib.zip`` should be shown to the author as an error. Decision 9 is the long-term fix for that.

6. Editors should de-reference full URLs on save
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the course of editing courseware, authors may use their browser's "Copy Image URL" to copy the URL of an image and paste it elsewhere, resulting in a full, rewritten URL like ``https://demo.openedx.org/assets/content_libraries/lib:Axim:200/xblock.v1:problem@multi_choice_8/v4/static/images/fig1.png`` ending up in the OLX. If any such URLs are detected, they should be automatically rewritten to the ``/static/`` format (subject to some sanity checks to ensure it will still reference the correct asset).

Note: Only rewrite full URLs that point to a shared asset in the same learning package, and don't conflict with any of the component's own asset files.

7. Versioning follows the library content model
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are two independent layers of versioning, and they work the same way as for library components used in courses today.

**Within a learning package, references are unpinned.** A ``PublishableEntityVersionDependency`` names an Asset, not a version of it, just as a unit's unpinned children are components rather than component versions. The version used is determined by where the content is rendered:

- In Studio (authoring), the component's draft is rendered, and ``/static/`` references resolve to the **draft** version of each linked Asset.
- In the LMS, the component's published version is rendered, and ``/static/`` references resolve to the **published** version of each linked Asset.

Editing an Asset's draft therefore immediately changes what authors see in every component that uses it, and marks those components as having unpublished changes (via the dependency from decision 3). Learners see nothing until the Asset is published. Publishing a component also publishes the draft versions of the Assets it links to, the same way publishing a unit publishes its unpinned children, so a published component never references an unpublished Asset.

**Between a library and a course, updates are pulled explicitly.** A course copy of a library Asset is a downstream of the library Asset, and it tracks the upstream the same way downstream course blocks do:

- ``version_synced``: the library Asset's published version number that the course copy was created from or last synced with.
- ``version_declined``: the latest upstream version the course author chose not to sync, if any.

Only *published* library versions are ever copied into a course. Library drafts are never visible to courses.

Upstream tracking for Assets uses the same platform-level mechanism as components (currently the ``ComponentLink`` model and related sync APIs in ``openedx-platform``). The ``upstream`` model may need adjustment, since an Asset is not a Component or an XBlock and has no XBlock fields to store ``upstream_version`` in. The details are left to the platform implementation.

8. Backwards compatibility in OLX export
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

TODO: document format for assets attached to components.

9. Support for multiple python libraries per course
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Problem component (also known as "capa") has support for writing advanced problems that use Python to compute parts of the problem or grade user answers. In particular, it allows authors to provide a library of python functions that will be available for use in any python code used to define a given problem. Currently, this is limited to one library file per course, which must be called ``python_lib.zip``. Once courseware is moved into ``openedx_content``, we should extend the Problem component so that the Python library is a field that can point to any shared asset (e.g. ``/static/alternative_python_lib.zip``), falling back to whichever asset has the filename ``python_lib.zip``. This will provide authors with more flexibility and simplify the process of linking advanced python-based Problems from a library into a course, without breaking backwards compatibility.

Consequences
------------

- Asset usage ("which components use this file?") becomes a simple query over ``PublishableEntityVersionDependency``, rather than a best-effort parse of all course content.
- The course "Files" page can show a list of "broken references" / "missing files" by querying for placeholder Assets (decision 4) that still have dependents, along with the components that reference each one. Deleted Assets that are still referenced can be included in the same list.
- For content using ``/static/...`` references: reruns never need to rewrite references in component content, and clipboard copy/paste, library import and library sync only need to do so when a shared Asset's filename conflicts with an unrelated Asset in the destination (decision 5).
- A course's learning package always contains every (properly-referenced) asset it uses, so it can be exported, backed up and restored in isolation.
- Every component version snapshots its links, adding a small number of rows per component version for components that use shared assets.
- The existing two URL formats (``/static/`` or ``[https://host]/asset-v1:``) have to be supported by the rendering pipeline indefinitely.
- Library Assets used in many courses are copied into each course. This costs rows, not bytes, because blobs are deduplicated per org.
- Some relative references among Assets (e.g. an HTML file with a dynamic reference to a JS file, like ``import(`./${filename}.js`)``) will not be identified and tracked via ``PublishableEntityVersionDependency``.
- Publishing one component publishes the shared assets it uses, which changes what learners see in every other component that uses it. That's consistent with how unit children behave, but may be surprising.
- Deleting a shared asset needs to be handled carefully. Publishing a component publishes its dependencies' unpublished changes, and a soft-delete counts as one. So if an author deletes a still-referenced Asset and then publishes any component that uses it, the deletion goes live and breaks every other published component that uses it. To avoid this, we should warn users when they delete an asset that is still referenced. (Or, don't publish dependency deletions as a side effect.)

Rejected Alternatives
---------------------

Authors must explicitly link Assets themselves
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We could say that authors must explicitly link a component to each Asset it uses via the UI (e.g. using a file picker) before ``/static/...`` style references in the OLX will work. However, this is unduly burdensome for course authors, compared to the relative simplicity of copying and pasting ``/static/...`` strings, and leaving the system to auto-create (or delete) ``PublishableEntityVersionDependency`` references as needed.

Linking directly to Assets in libraries
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Letting a course component link to an Asset that lives in a library's learning package would avoid copying. It was rejected because it breaks learning package isolation (deleting or un-publishing a library asset would break courses), can't use :class:`PublishableEntityVersionDependency` for side effects, would give courses two different versioning and permission models for assets depending on where they came from, and is inconsistent with how library components are used in courses.

A new ``oex-asset:`` URL scheme
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An earlier draft of this ADR introduced a new reference format, e.g. ``<img src="oex-asset:moon-orbit.svg">``, along with an ``AssetComponentLink`` model holding a per-component alias for each referenced Asset. Unlike ``/static/``, ``oex-asset:`` never occurs in content for any other reason, so it can be detected with no false positives (e.g. from platform URLs, or a course on HTML whose examples include ``/static/``).

It was rejected because it adds cost without removing any: ``/static/`` and ``asset-v1:`` must be supported indefinitely anyway, so the rendering pipeline would have to handle three formats instead of two. Every sanitizer and editor that touches authored content would have to allow the new scheme, and exports would have to rewrite ``oex-asset:`` references back to ``/static/`` so that the tarball can be imported on older Open edX versions. The aliases, which were needed to avoid filename collisions when copying from a library, are instead handled by renaming conflicting shared assets (decision 5), which only rewrites plain ``/static/`` references in the rare case of a conflict.

The cost of staying with ``/static/`` is the occasional false positive from the broader detection in decision 1. With placeholder Assets (decision 4), a false positive results in an unused placeholder and a spurious "missing file" entry, rather than broken content.

Converting conflicting shared assets to attached assets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An earlier draft of decision 5 upheld the principle that **OLX should never change** when a Component is copied from one Learning Package to another. When a shared Asset referenced by the copied Component conflicted with an unrelated Asset of the same filename in the destination, the file would be attached to the copied Component instead, so that its ``/static/`` reference resolved to the attached file first (decision 2) with no change to the OLX.

It was rejected because:

- The attached file is no longer a downstream of the library Asset, so later updates to the library Asset are not synced to it.
- Files attached to a Component have no ``locked`` or ``private`` flags, so locked or private Assets could not be handled this way, and would need an error instead.
- An attached HTML file's relative references to other shared Assets fall back to the destination's shared Assets (:ref:`openedx-content-adr-0013`, decision 3), so they would silently resolve to the very conflicting, unrelated Assets that the conversion was meant to avoid.
- The same Asset would end up in different forms (shared in some courses, attached in others) depending on what else happened to be in the destination.

Template placeholders instead of URLs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Placeholders such as ``{{ asset "moon-orbit.svg" }}`` are easy to detect, but they are not URLs. HTML parsers, WYSIWYG editors and sanitizers mangle them in ``src`` and ``href`` attributes, while a URL-shaped reference like ``/static/moon-orbit.svg`` survives those tools.

Pinning links to specific Asset versions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A component version's reference could name a specific version of the Asset, like a pinned container child. This would stop an Asset edit from affecting components that use it, but authors expect that replacing a shared image updates it everywhere in the course. Pinning also creates a different version of the same asset for every component, and requires a new version of every using component each time the Asset changes. Controlled updates are already provided one layer up, between a library and a course (decision 7).

TODOs and open questions
------------------------

- What happens when an Asset that others link to is deleted? (Can we ensure the published Component's old reference still resolves to the Asset version it was last linked to?)
- Referencing a ``private`` Asset from learner-facing content should warn.
- Export: Files attached to a component need a rule for export to older platforms. The ``locked`` and ``title`` need to go into ``policies/assets.json``. Private static files will have to be in a separate folder outside of ``static/`` and won't be backwards compatible.
- Figure out if we can also use the same dependency tracking for references to external Digital Asset Management Systems.
