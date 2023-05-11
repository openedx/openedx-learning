6. App Label Prefix
===================

Context
-------

We want this repo to be useful in different Django projects outside of just edx-platform, and we want to avoid downstream collisions with our app names.


Decision
--------

All apps in this repo will create a default AppConfig that sets the ``label`` to have a prefix of ``oel_`` before the app name. So if the app name is ``publishing``, the ``label`` will be ``oel_publishing``. This means that all generated database tables will similarly be prefixed with ``oel_``.
