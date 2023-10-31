15. Serving Course Team Authored Static Assets
==============================================

Context
--------

Both Studio and the LMS need to serve course team authored static assets as part of the authoring and learning experiences. These will most often be images, but may also include things like subtitles, audio files, and even JavaScript. It does NOT typically include video files, which are treated separately because of their size.

This ADR is the synthesis of various ideas that were discussed across a handful of pull requests and issues. These links are provided for extra context, but they are not required to understand this ADR:

* `File uploads + Experimental Media Server #31 <https://github.com/openedx/openedx-learning/pull/31>`_
* `File Uploads + media_server app #33 <https://github.com/openedx/openedx-learning/pull/33>`_
* `Modeling Files and File Dependencies #70 <https://github.com/openedx/openedx-learning/issues/70>`_
* `Serving static assets (disorganized thoughts) #108 <https://github.com/openedx/openedx-learning/issues/108>`_

The underlying data models live in the openedx-learning repo. The most relevant models are:

* `RawContent in contents/models.py <https://github.com/openedx/openedx-learning/blob/main/openedx_learning/core/contents/models.py>`_
* `Component and ComponentVersion in components/models.py <https://github.com/openedx/openedx-learning/blob/main/openedx_learning/core/components/models.py>`_

Key takeaways about how this data is stored:

* Raw asset data is stored in django-storages using its hash value as the file name. This makes it cheap to make many references to the same asset data under different names and versions, but it means that we cannot simply give direct links to the raw file data to the browser.
* Assets are associated and versioned with Components, where a Component is typically an XBlock. So you don't ask for "version 5 of /static/fig1.webp", you ask for "the /static/fig1.webp associated with version 5 of this block".
* This initial MVP would be to serve assets for v2 content libraries, where all static assets are associated with a particular component XBlock. Later on, we'll want to allow courses to port their existing files and uploads into this system in a backwards compatible way. We will probably do this by creating a Component that treats the entire course as a Component. The specifics for how that is modeled on the backend are out of scope for this ADR, but this general approach is meant to work for both use cases.

Application Requirements
~~~~~~~~~~~~~~~~~~~~~~~~

**Relative links between assets must be preserved.**
  Assets may reference each other in relative links, e.g. a JavaScript file that references images or other JavaScript files. That means that our solution cannot require querystring-based authorization tokens in the style of S3 signed URLs, since asset files would have no way to encode those into their relative links.

**Multiple versions of the asset should be available at the same time.**
  Our system should be able to serve at minimum the current draft and published versions of an asset. Ideally, it should be able to serve any version of an asset. This is a departure from the way Studio and the LMS currently handle files and uploads, since there is currently no versioning at all–assets exist in a flat namespace at the course level and are immediately published.

Security Requirements
~~~~~~~~~~~~~~~~~~~~~

**Assets must enforce user+file read permissions at the Learning Context level.**
  The MongoDB GridFS backed ContentStore currently supports course-level access checks that can be toggled on and off for individual assets. Uploaded assets are public by default, and can be downloaded by anyone who knows the URL, regardless of whether or not they are enrolled in the course. They can optionally be "locked", which will restrict downloads to students who are enrolled in the course.

**Assets should enforce more granular permissions at the individual Component level.**
  An important distinction between ContentStore and v2 Content Library assets is that the latter can be directly associated with a Component. As a long term goal, we should be able to make permissions check on per-Component basis. So if a student does not have permission to view a Component for whatever reason (wrong content group, exam hasn't started, etc.), then they should also not have permission to see static assets associated with that component.

  The further implication of this requirement is that *permissions checking must be extensible*. The openedx-learning repo will implement the details of how to serve an asset, but it will not have the necessary models and logic to determine whether it is allowed to.

**Assets must be served from an entirely different domain than the LMS and Studio instances.**
  To reduce our chance of maliciously uploaded JavaScript compromising LMS and Studio users, user-uploaded assets must live on an entirely different domain from LMS and Studio (i.e. not just another subdomain). So if our LMS is located at ``sandbox.openedx.org``, the files should be accessed at a URL like ``assets.sandbox.openedx.io``.

Operational Requirements
~~~~~~~~~~~~~~~~~~~~~~~~

**The asset server must be capable of handling high levels of traffic.**
  Django views are poor choice for streaming files at scale, especially when deploying using WSGI (as Open edX does), since it will tie down a worker process for the entire duration of the response. While a Django-based streaming response is sufficient for small-to-medium sites, we should allow for a more scalable solution that fully takes advantage of modern CDN capabilities.

**Serving assets should not *require* an S3-like object store.**
  While S3-like object stores are often used in Open edX deployments at scale, our approach shouldn't *require* it. It is acceptable to require an S3-like store for high-scale traffic.

**Serving assets should not *require* ASGI deployment.**
  Deploying the LMS and Studio using ASGI would likely substantially improve the scalability of a Django-based streaming solution, but migrating and testing this new deployment type for the entire stack is a large task and is considered out of scope for this project.

Decision
--------

URLs
~~~~

The format will be: ``https://{asset_server}/assets/apps/{app}/{learning_package_key}/{component_key}/{version}/{filepath}``

The asset server will have a completely different domain from the LMS and Studio, and will not be a subdomain.

A more concrete example: ``https://studio.assets.sandbox.openedx.io/apps/content_libraries/lib:Axim:200/xblock.v1:problem@826eb471-0db2-4943-b343-afa65a6fdeb5/v2/static/images/fig1.png``

The ``version`` can be:

* ``draft`` indicating the latest draft version (viewed by authors in Studio).
* ``published`` indicating the latest published version (viewed by students in the LMS)
* ``v{num}`` meaning a specific version–e.g. ``v20`` for version 20.

Site Separation
~~~~~~~~~~~~~~~

The asset-serving site will run in the same process as the LMS or Studio process the links, so ``studio.assets.sandbox.openedx.io`` would point to the same place that ``studio.sandbox.openedx.org``. Being in the same process will make it easier to implement permissions checks and URL generation code.

The switching between the two would happen with a new Middleware class that is implemented in openedx-learning. We would use this Middleware to make sure that assets are never served through the Studio and LMS URLs, and that no other Studio or LMS views are served through the asset server URL. This will require new configuration settings.

View Implementation
~~~~~~~~~~~~~~~~~~~

The Learning Core will implement a Django REST Framework APIView that will provide the core functionality for serving assets. This view will be subclassed and customized by apps in LMS and Studio that want to make use of this functionality.

The Learning Core will also provide auth related endpoints.

Permissions
~~~~~~~~~~~

The Learning Core will not implement any permissions checking. It will be the responsibility of an app in Studio or the LMS add permissions classes to their subclass of the APIView.

For instance, Studio would likely implement a simple permissions checking model that only examines the learning context and restricts access to course staff. LMS might eventually use a much more sophisticated model that looks at the individual Component that an asset belongs to.

Cookie Authentication
~~~~~~~~~~~~~~~~~~~~~

Authentication will use a domain cookie on the root assets domain (e.g. ``*.assets.sandbox.openedx.io``). The cookie will have the ``Secure`` and ``HttpOnly`` attributes.

OPEN QUESTIONS:

* What's the best way to do handoff between LMS/Studio and get that cookie information over to the asset domains?

Masquerading
~~~~~~~~~~~~

We could theoretically add masquerading information to the cookie, but we would not implement in the first iteration.

Performance at Scale
~~~~~~~~~~~~~~~~~~~~

The performance of this system for any particular asset view request should be similar to what already exists today. The difference in the long term is that by tying permissions to individual Components, we will in practice be caching far less than we do today, which will increase the load on the LMS.

The high scale version of this approach will require having a CDN with programmable workers and a scalable object store that supports signed URLs (such as S3). The main objective would be to shift the file streaming burden out of Django and onto the CDN and object store.

In Learning Core, we would implement an APIView (or possibly extend the asset-serving one) to return a JSON response of file metadata. This would include things like size, MIME type, last modified date, cache expiration policy, etc. The response would also contain a signed URL pointing to a object store resource, like S3. The CDN worker then does the fetch on that resource. We would create an example worker for at least CloudFlare.

Rejected Alternatives
---------------------
