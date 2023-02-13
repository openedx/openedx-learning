Media Server App
================

The ``media_server`` app exists to serve media files that are ultimately backed by the RawContent model, *for development purposes and for sites with light-to-moderate traffic*. It also provides an API that can be used by CDNs for high traffic sites.

Motivation
----------

The ``components`` app stores large binary file data by calculating the hash and creating a django-storages backed file named after that hash. This is efficient from a storage point of view, because we don't store redundant copies for every version of a Component. There are at least two drawbacks:

* We have unintelligibly named files that are confusing for clients.
* Intra-file links between media files break. For instance, if we have a piece of HTML that makes a reference to a VTT file, that filename will have changed.

This app tries to bridge that gap by serving URLs that preserve the original file names and give the illusion that there is a seprate set of media files for every version of a Component, but does a lookup behind the scenes to serve the correct hash-based-file.

The big caveat on this is that Django is not really optimized to do this sort of asset serving. The most scalable approach is to have a CDN-backed solution where ``media_server`` serves the locations of files that are converted by worker code to serving the actual assets. (More details to follow when that part gets built out.)
