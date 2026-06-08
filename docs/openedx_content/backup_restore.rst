.. _backup-restore-format:

Backup / Restore Format
=======================

The ``backup_restore`` applet lets you export a learning package (V2 content
library) to a portable ZIP archive and restore it on the same or a different
Open edX instance.

.. contents:: Contents
   :local:
   :depth: 2

Overview
--------

A backup ZIP is a self-contained snapshot of one learning package.  It captures
every component, collection, container (sections / subsections / units), static
asset, and version history that existed at export time.

The archive uses `TOML <https://toml.io>`_ for all metadata files and keeps the
actual XBlock content as XML (the same ``block.xml`` format Studio has always
used).  This makes backups both machine-readable and human-inspectable.

.. note::

   The current archive ``format_version`` is **1**.  Future incompatible changes
   to the schema will increment this number so that tooling can detect them
   before attempting a restore.

Exporting a Package
-------------------

Management command (recommended for operators)::

    python manage.py lp_dump <package_ref> output.zip
    python manage.py lp_dump <package_ref> output.zip --username admin --origin_server cms.example.com

Python API::

    from openedx_content.api import create_zip_file

    create_zip_file(
        package_ref="lib:MyOrg:MyLibrary",
        path="/tmp/my_library.zip",
        user=request.user,          # optional – recorded in package.toml
        origin_server="cms.example.com",  # optional
    )

Restoring a Package
-------------------

Management command::

    python manage.py lp_load output.zip <username>

Python API::

    from openedx_content.api import load_learning_package

    result = load_learning_package(path="/tmp/my_library.zip")
    if result["status"] == "error":
        print(result["log_file_error"].getvalue())

.. note::

   ``load_learning_package`` accepts an optional ``package_ref`` argument.
   When provided it overrides the ``key`` stored in ``package.toml``, which
   is useful when importing a library under a new reference.

Archive Structure
-----------------

::

    <package>.zip
    ├── package.toml                          # library metadata + archive metadata
    ├── collections/
    │   └── <collection-key>.toml            # one file per collection
    └── entities/
        ├── <container-slug>.toml            # sections, subsections, units
        └── xblock.v1/
            └── <block-type>/               # e.g. html, problem, video
                ├── <uuid>.toml             # entity metadata + version list
                └── <uuid>/
                    └── component_versions/
                        └── v<N>/
                            ├── block.xml   # XBlock content (XML)
                            └── static/     # media assets referenced by block.xml

File Format Reference
---------------------

package.toml
~~~~~~~~~~~~

Located at the root of the archive.  Contains two sections:

``[meta]`` — archive metadata (not restored to the database, for inspection only):

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Required
     - Description
   * - ``format_version``
     - yes
     - Integer schema version; currently ``1``
   * - ``created_by``
     - no
     - Username of the operator who ran the export
   * - ``created_by_email``
     - no
     - Email address of the exporting user
   * - ``created_at``
     - yes
     - UTC timestamp when the archive was created
   * - ``origin_server``
     - no
     - Hostname of the CMS instance that produced the archive

``[learning_package]`` — library data (restored to the database):

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Required
     - Description
   * - ``title``
     - yes
     - Human-readable name of the library
   * - ``key``
     - yes
     - Package reference string, e.g. ``lib:MyOrg:MyLib``
   * - ``description``
     - yes
     - Free-text description (may be blank)
   * - ``created``
     - yes
     - UTC timestamp when the library was originally created
   * - ``updated``
     - yes
     - UTC timestamp of the library's last modification

Example::

    [meta]
    format_version = 1
    created_by = "lp_user"
    created_by_email = "lp_user@example.com"
    created_at = 2025-10-05T18:23:45.180535Z
    origin_server = "cms.test"

    [learning_package]
    title = "Library test"
    key = "lib:WGU:LIB_C001"
    description = ""
    created = 2025-08-19T04:25:10.988166Z
    updated = 2025-08-19T04:25:10.988166Z

Component entity TOML (``entities/xblock.v1/<type>/<uuid>.toml``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each XBlock component gets one TOML file.

``[entity]``:

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Required
     - Description
   * - ``can_stand_alone``
     - yes
     - Whether this component can be used independently (almost always ``true``)
   * - ``key``
     - yes
     - Entity reference in the form ``xblock.v1:<type>:<uuid>``
   * - ``created``
     - yes
     - UTC creation timestamp

``[entity.draft]`` / ``[entity.published]`` — each contains ``version_num``
pointing at the current draft or published ``[[version]]`` entry respectively.
If a section is absent the entity has no draft or published version.

``[[version]]`` — one entry per saved version, in ascending ``version_num`` order:

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Required
     - Description
   * - ``title``
     - yes
     - Display name of the component at this version
   * - ``version_num``
     - yes
     - Monotonically increasing integer starting at 1

Example::

    [entity]
    can_stand_alone = true
    key = "xblock.v1:html:e32d5479-9492-41f6-9222-550a7346bc37"
    created = 2025-08-19T04:25:43.685529Z

    [entity.draft]
    version_num = 5

    [entity.published]
    version_num = 4

    # ### Versions

    [[version]]
    title = "Text"
    version_num = 4

    [[version]]
    title = "Text"
    version_num = 5

Container entity TOML (``entities/<slug>.toml``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sections, subsections, and units share the same base structure with an
additional ``[entity.container.<type>]`` marker (``section``, ``subsection``,
or ``unit``) and a ``[version.container]`` table that lists child keys.

Example (section)::

    [entity]
    can_stand_alone = true
    key = "section1-8ca126"
    created = 2025-09-04T22:51:40.919872Z

    [entity.draft]
    version_num = 2

    [entity.published]
    # unpublished: no published_version_num

    [entity.container.section]

    # ### Versions

    [[version]]
    title = "Section1"
    version_num = 2

    [version.container]
    children = ["subsection1-48afa3"]

Collection TOML (``collections/<key>.toml``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Required
     - Description
   * - ``title``
     - yes
     - Collection display name
   * - ``key``
     - yes
     - Unique key within the library
   * - ``description``
     - yes
     - Free-text description (may be blank)
   * - ``created``
     - yes
     - UTC creation timestamp
   * - ``entities``
     - yes
     - List of entity reference strings (``xblock.v1:<type>:<uuid>``)

Example::

    [collection]
    title = "Collection test1"
    key = "collection-test"
    description = ""
    created = 2025-08-19T04:25:27.754968Z
    entities = [
        "xblock.v1:html:e32d5479-9492-41f6-9222-550a7346bc37",
        "xblock.v1:problem:256739e8-c2df-4ced-bd10-8156f6cfa90b",
    ]

XBlock content (``component_versions/v<N>/block.xml``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Standard XBlock XML, identical to what Studio stores internally.  Static assets
(images, PDFs, etc.) referenced with ``/static/<filename>`` in the XML are
stored alongside the XML under ``component_versions/v<N>/static/``.

Example ``block.xml``::

    <html display_name="Text">
      <![CDATA[<p>Hello <img src="/static/me.png" alt="Me" /></p>]]>
    </html>
