1. Purpose of this Repo
=======================

Context
-------

The code that operates on learning content in Open edX primarily resides in edx-platform, and suffers from a few high-level issues:

* Plugins that want to interact with content effectively import  all of edx-platform (a large repo with hundreds of dependencies) as a direct dependency, making development and testing more difficult.
* The existing code assumes that content will take the form of large courses, hindering efforts to experiment with different instructional formats.

Decision
--------

The openedx-learning repository was created to provide a new place for certain core learning concepts, data models, and APIs to be implemented. These concepts will be more granular and composable than the courses we have today.

This would have two long term goals:

#. Enable learning-related plugins to be built in a simple, maintainable, robust way.
#. Allow Open edX to support for more flexible and extensible learning experiences at scale.

This repo will first be piloted with the use case of unit composition in service of v2 Content Libraries work. If this is successful, other concepts would follow.

Consequences
------------

The edx-platform repo will eventually have openedx-learning as a dependency. As functionality is implemented in openedx-learning (e.g. unit composition for content libraries), edx-platform will make use of it.

Over time, plugin apps should be able to make use of stable APIs in this repo instead of having to call into edx-platform's Modulestore or Block Transformers. This will serve as a third leg of the new in-process extension mechanisms, where openedx-events provides event notification, openedx-filters provides the ability to intercept and modify the workflow of existing views, and this repo will allow content querying capability.

Rejected Alternatives
---------------------

For most of edx-platform's existence, we've pushed the idea of evolving it into a smaller, more modular, and more easily extensible core. We would do this by extracting non-core items out of the repo, leaving only the essential bits behind.

Unfortunately, the valiant efforts of numerous people over the years has only managed to slow (not stop or reverse) the growth of edx-platform. That repo now has approximately half a million lines of Python code. Extraction efforts have been hampered by tangled dependencies. It has also suffered from the problem that most of the benefits of a smaller, cleaner core system come near the end of the extraction process–making it more difficult to prioritize incremental work towards that goal.
