15. Serving Course Team Authored Static Assets
==============================================

Context
--------

Both Studio and the LMS need to serve course team authored static assets as part of the authoring and learning experiences. "Static assets" in the edx-platform context presently refers to: image files, audio files, text document files like PDFs, older video transcript files, and even JavaScript and Python files. It does NOT typically include video files, which are treated separately because of their large file size and complex workflows (processing for multiple resolutions, using third-party dictation services, etc.)

This ADR is the synthesis of various ideas that were discussed across a handful of pull requests and issues. These links are provided for extra context, but they are not required to understand this ADR:

* `File uploads + Experimental Media Server #31 <https://github.com/openedx/openedx-learning/pull/31>`_
* `File Uploads + media_server app #33 <https://github.com/openedx/openedx-learning/pull/33>`_
* `Modeling Files and File Dependencies #70 <https://github.com/openedx/openedx-learning/issues/70>`_
* `Serving static assets (disorganized thoughts) #108 <https://github.com/openedx/openedx-learning/issues/108>`_

Data Storage Implementation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The underlying data models live in the openedx-learning repo. The most relevant models are:

* `Content in contents/models.py <https://github.com/openedx/openedx-learning/blob/main/openedx_learning/core/contents/models.py>`_
* `Component and ComponentVersion in components/models.py <https://github.com/openedx/openedx-learning/blob/main/openedx_learning/core/components/models.py>`_

Key takeaways about how this data is stored:

* Assets are associated and versioned with Components, where a Component is typically an XBlock. So you don't ask for "version 5 of /static/fig1.webp", you ask for "the /static/fig1.webp associated with version 5 of this block".
* This initial MVP would be to serve assets for v2 content libraries, where all static assets are associated with a particular component XBlock. Later on, we'll want to allow courses to port their existing files and uploads into this system in a backwards compatible way. We will probably do this by creating a non-XBlock, filesystem Component type that can treat the entire course's uploads as a Component. The specifics for how that is modeled on the backend are out of scope for this ADR, but this general approach is meant to work for both use cases.
* The actual raw asset data is stored in django-storages using its hash value as the file name. This makes it cheap to make many references to the same asset data under different names and versions, but it means that we cannot simply give direct links to the raw file data to the browser (see the next section for details).

The Difficulty with Direct Links to Raw Data Files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Since the raw data is stored as objects in an S3-like store, and the mapping of file names and versions to that raw data is stored in Django models, why not simply have a Django endpoint that redirects a request to the named asset to the hash-named raw data it corresponds to?

**It will break relative links between assets.**
  The raw data files exist in a flat space with hashes for names, meaning that any relative links between assets (e.g. a JavaScript file referencing an image) would break once a browser follows the redirect.

**Setting Metadata: Content types, filenames, and caching.**
  The assets won't generally "work" unless they're served with the correct Content-Type header. For users who want to download a file, it's quite inconvenient if the filename doesn't include the correct file extension (not to mention a friendly name instead of the hash). So we need to set the Content-Type and/or Content-Disposition: ; filename=... headers.

  Setting these values for each request has proved problematic because some (but not all) S3-compatible storage services (including S3 itself) only support setting those headers for each request if you issue a signed GET request, which then gets in the way of caching and introduces the probability of browsers caching expired links, leading to all kinds of annoying cache invalidation issues.

  Setting the filename value at upload time also doesn't work because the same data may be referenced under different filenames by different Components or even different versions of the same Component.

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
  Django views are poor choice for streaming files at scale, especially when deploying using WSGI (as Open edX does), since it will tie down a worker process for the entire duration of the response. While a Django-based streaming response may sufficient for small-to-medium traffic sites, we should allow for a more scalable solution that fully takes advantage of modern CDN capabilities.

**Serving assets should not *require* ASGI deployment.**
  Deploying the LMS and Studio using ASGI would likely substantially improve the scalability of a Django-based streaming solution, but migrating and testing this new deployment type for the entire stack is a large task and is considered out of scope for this project.

Decision
--------

URLs
~~~~

The format will be: ``https://{asset_server}/assets/apps/{app}/{learning_package_key}/{component_key}/{version}/{filepath}``

The assets will be served from a completely different domain from the LMS and Studio, and will not be a subdomain.

A more concrete example: ``https://studio.assets.sandbox.openedx.io/apps/content_libraries/lib:Axim:200/xblock.v1:problem@826eb471-0db2-4943-b343-afa65a6fdeb5/v2/static/images/fig1.png``

The ``version`` can be:

* ``draft`` indicating the latest draft version (viewed by authors in Studio).
* ``published`` indicating the latest published version (viewed by students in the LMS)
* ``v{num}`` meaning a specific version–e.g. ``v20`` for version 20.

Asset Server Implementation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

There will be two asset server URLs–one corresponding to the LMS and one corresponding to Studio, each with their own subdomain. An example set of domains might be:

* LMS: ``sandbox.openedx.org``
* Studio: ``studio.sandbox.openedx.org``
* LMS Assets: ``lms.assets.sandbox.openedx.io`` (note the ``.io`` top level domain)
* Studio Assets: ``studio.assets.sandbox.openedx.io``

The asset serving domains will be serviced by a Caddy instance that is configured as a reverse proxy to the LMS or Studio. Caddy will be configured to only proxy a specific set of paths that correspond to valid asset URLs.

Django View Implemenation
~~~~~~~~~~~~~~~~~~~~~~~~~

The LMS and Studio will each have one or two apps that implement view endpoints by extending a view that will be provided by the Learning Core. These views will only respond to requests that come via the asset domains (i.e. they will not work if you request the same paths using the LMS or Studio domains).

Django is poorly suited to serving large static assets, particularly when deployed using WSGI. Instead of streaming the actual file data, the Django views serving assets will make use of the ``X-Accel-Redirect`` header. This header is supported by both Caddy and Nginx, and will cause them to fetch the data from the specified URI to send to the user. This redirect happens internally in the proxy and does *not* change the browser address. For sites using an object store like S3, the Django view will generate and send a signed URL to the asset. For sites using file-based Django media storage, the view will send a URL that Caddy or Nginx knows how to load from the file system.

The Django view will also be responsible for setting other important header information, such as size, content type, and caching information.

Permissions
~~~~~~~~~~~

The Learning Core provided view will contain the logic for looking up and serving assets, but it will be the responsibility of an app in Studio or the LMS to extend it with permissions checking logic. This logic may vary from app to app. For instance, Studio would likely implement a simple permissions checking model that only examines the learning context and restricts access to course staff. LMS might eventually use a much more sophisticated model that looks at the individual Component that an asset belongs to.

Cookie Authentication
~~~~~~~~~~~~~~~~~~~~~

Authentication will use a session cookie for each asset server domain.

Assets that are publicly readable will not require authentication.

Asset requests may return a 403 error if the user is logged in but not authorized to download the asset. They will return a 401 error for users that are not authenticated.

There will be a new endpoint exposed in LMS/Studio that will force a redirect and login to the asset server. Pages that make use of assets will be expected to load that endpoint in their ``<head>`` before any page assets are loaded. The flow would go like this:

#. There is a ``<script>`` tag that points to a new check-login endpoint in LMS/Studio, causing the browser to load and execute it before images are loaded.
#. This LMS/Studio endpoint generates a random token, stores user information its backend cache based on that token, and redirects the user to an asset server login endpoint using that token as a querystring parameter.
#. The asset server endpoint checks the cache with that token for the relevant user information, logs that user in, and removes the cache entry. It has access to the cache because it's still proxying to the same LMS/Studio process underneath–it's just being called from a different domain.

Masquerading
~~~~~~~~~~~~

We could theoretically take masquerading into account during the auto-login process for the asset server, but we would not implement it in the first iteration.

Rejected Alternatives
---------------------

Per-asset Login Redirection
~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is possible to initiate a series of redirects for every unauthenticated request to a non-public asset. This remove the need for pages using assets to have to include this special handling in their ``<head>``. Some drawbacks of this approach:

* Injecting tokens in the querystrings of assets may cause errors or security leaks.
* Combining per-asset redirection with dedicated endpoints for the tokens would mean even more redirection, increasing the number of places where things could fail.
* There is a greater risk of bugs causing infinite loops.
* A page that loads many assets concurrently may trigger a large set of duplicated redirects/logins.

Forcing the page to opt into asset authentication is unusual and may cause bugs. But the hope is that it is operationally safer and simpler, and that the number of views that directly render non-public assets will be relatively small.
