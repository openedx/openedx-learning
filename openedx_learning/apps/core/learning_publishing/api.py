"""
The order of data that must come in:

* partitioning <-- multiple things will reference this for data integrity.
* policy, composition <-- navigation relies on composition
* navigation
* scheduling

What does a publishing call look like, in a pluggable world? And how much data
are we talking about?

Boundary between "composition" and "navigation" – fuzzy? Navigation has Unit
metadata, but doesn't know about anything _inside_ the Unit::

    {
        "type": "update",  // as opposed to "replace"
        "version": "someversionindicator",

        "policy": {

        },

        "partitioning": {

        },
        "composition": {

        },
        "navigation": {
            "type": "three_level_static", // This is a terrible name, what do we call what we have?,

        }

    }

How to manage plugin cycle life?

"""


def current_version(learning_context_key):
    pass


def update_published_version(learning_context_key, app_name, published_at=None):
    pass



