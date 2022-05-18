3. Content Extensibility Through Model Relations
================================================

Context
-------

Content extensibility has always been critical to the success of Open edX, with the most obvious example being XBlocks as a mechanism to create custom problem types. Plugin apps have also long interacted with the ModuleStore in order to pull back content information as part of new, custom functionality.

We want the Learning Core to build upon these successes, while addressing a number of architectural pain points in the current system.

Developer Experience Pain Points
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. Plugin applications cannot make queries about learning content without calling into the edx-platform monolith, which makes testing, development, and long term maintenance more difficult.
#. Plugins are prone to bugs around the content publishing lifecycle, such as when content that a plugin cares about is changed or deleted while a course is running.
#. XBlocks data is stored in a way that is opaque at the database layer. Individual fields are collapsed into large key/value documents, making joins and rich database-level querying difficult.

Application Lifecycle and Platform Resilience Pain Points
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#. Content can become completely inaccessible after a plugin has been removed. It was once the case that uninstalling an XBlock would prevent the export of any course that used that XBlock.
#. Hierarchical nesting in import/export means that removing a container XBlock type (e.g. SplitTestBlock) would also completely remove any content in those containers from future exports.
#. Plugin bugs have in the past broken all export functionality, making it difficult to reproduce the issue locally (for lack of access to production content data).
#. The current pattern of listening to the ``course_published`` signal and launching a celery task means that the publishing process is not atomic. Shortly after publishing occurs, a course enters a nebulous state where both the old and new versions are live in different systems.
#. There is no provision for error handling and reporting when applications fail during the publish process.

Decision
--------

Learning Core data models will be built with extensibility in mind, with the following high level principles:

#. There will be a core data model that is always introspectable and exportable, without invoking plugin/extension code.
#. Plugin apps will be able to progressively enhance this core data model by creating their own related models, typically linked to core data models using ``OneToOneField``.
#. Plugin apps are able to extend Core concepts such as Units into what would effectively be sub-types.
#. It will be possible to migrate existing content data over time, as new plugin apps become available.
#. All content and versions of content will have UUIDs to allow for stable references across services.

This layering of related models will add complexity to the data model, but we accept that tradeoff to decouple plugin models from the core application and from other plugins. To make this easier to deal with, openedx-learning should provide abstract models for common use cases, and expose those via a ``models_api.py`` module. This will lower the barrier to entry for developers, and allow us to more easily enforce conventions like setting ``primary_key=True`` with our ``OneToOneField`` relationships.

Rejected Alternatives
---------------------

Subclassing Concrete Models
~~~~~~~~~~~~~~~~~~~~~~~~~~~

One possibility that was brought up was to have extensions subclass the core models into new models with the extra desired metadata. For instance, a subclass that specifically stored images and new how to extract image metadata from the raw binary data. In this scenario, instead of having a shared core object hold the raw binary data and having a plugin model for image metadata that has a ``OneToOneField`` that referenced it, we would have only the plugin's combined model with both binary data and image metadata.

We decided against this for the following reasons:

#. Content data that is stored only in a given plugin app's models may become deleted or inaccessible when that app is removed.
#. Having a shared core data model allows other plugin apps to create content relationships without creating dependencies to other plugins. For instance, a "related content" plugin app would not have to know specifically about the "image content" plugin app in order to capture relationships between images and other content.

External Service-Level Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We could move entirely away from in-database model relationships and push all integrations to take place at a service boundary layer, using standards like LTI. This would have the advantage of not being coupled to Django.

We're not doing this for a number of reasons, including:

#. Open edX has a need for data introspection that is difficult to provide in a performant way via LTI (e.g. grading, completion, research). This is one of the reasons why v2 Content Libraries are not being integrated into the LMS with only LTI.
#. Data models allow for a level of consistency and validation (e.g. via foreign key relations) that are much more difficult to achieve via networked services.
#. Data model-level integration allows plugins to have a much richer ability to query content and cheaply build more dynamic learning experiences.
#. It is still possible to add external integrations on top of model-level integration where it makes sense to do so. The v2 Content Libraries implementation integrates with the LMS at the XBlock level, but still offers an LTI interface for other uses.
