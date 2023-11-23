14. Single taxonomy view API
=====================================

Context
--------

This view returns tags of a taxonomy (works with closed, open, and system-defined). It is necessary to make a decision about what structure the tags are going to have, how the pagination is going to work and how will the search for tags be implemented. It was taken into account that taxonomies commonly have the following characteristics:

- It has few root tags.
- It may a very large number of children for each tag.
- It is mostly represented as trees on frontend, with a depth of up to 3 levels.

For the decisions, the following use cases were taken into account:

- As a taxonomy administrator, I want to see all the tags available for use with a closed taxonomy,
  so that I can see the taxonomy's structure in the management interface.

  - As a taxonomy administrator, I want to see the available tags as a list of root tags
    that can be expanded to show children tags.
  - As a taxonomy administrator, I want to sort the list of root tags alphabetically: A-Z (default) and Z-A.
  - As a taxonomy administrator, I want to expand all root tags to see all children tags.
  - As a taxonomy administrator, I want to search for tags, so I can find root and children tags more easily.
- As a course author, when I am editing the tags of a component, I want to see all the tags available
  from a particular taxonomy that I can use.

  - As a course author, I want to see the available tags as a list of root tags
    that can be expanded to show children tags.
  - As a course author, I want to search for tags, so I can find root and children tags more easily.

Excluded use cases:

- As a content author, when searching/filtering a course/library, I want to see which tags are applied to the content
  and use them to refine my search. - This is excluded from this API's use case because this is automatically handled
  by elasticsearch/opensearch.


Decision
---------

Views & Pagination
~~~~~~~~~~~~~~~~~~~

We will have one REST API endpoint that can handle these use cases:

**/tagging/rest_api/v1/taxonomies/:id/tags/?parent_tag=...**

that can handle this cases:

- Get the root tags of the taxonomy. If ``parent_tag`` is omitted.
- Get the children of a tag. Called each time the user expands a parent tag to see its children.
  In this case, ``parent_tag`` is set to the value of the parent tag.

In both cases the results are paginated. In addition to the common pagination metadata, it is necessary to return:

- Total number of pages.
- Total number of tags in the result.
- Range index of current page, Ex. Page 1: 1-12, Page 2: 13-24.
- Total number of children of each tag.

The pagination of root tags and child tags are independent.

**Optional full-depth response**

In order to be able to fulfill the functionality of "Expand-all" in a scalable way, and allow users to quickly browse taxonomies that have lots of small branches, the API will accept an optional parameter ``?full_depth_threshold``. If specified (e.g. ``?full_depth_threshold=1000``) and there are fewer results than this threshold, the full tree of tags will be returned a a single giant page, including all tags up to three levels deep.

**Pros**

- This approach is simple and flexible.
- Paging both root tags and children mitigates the huge number of tags that can be found in large taxonomies.

Search tags
~~~~~~~~~~~~

The same API endpoint will support an optional ``?search_term=...`` parameter to support searching/filtering tags by keyword.

The API endpoint will work exactly as described above (returning a single level of tags by default, paginated, optionally listing only the tags below a specific parent tag, optionally returning a deep tree if the results are small enough) - BUT only tags that match the keyword OR their ancestor tags will be returned. We return their ancestor tags (even if the ancestors themselves don't match the keyword) so that the tree of tags that do match can be displayed correctly. This also allows the UI to load the matching tags one layer at a time, paginated, if desired.

Tag representation
~~~~~~~~~~~~~~~~~~~

Return a list of root tags and within a link to obtain the children tags or the complete list of children tags depending on the requested ``?full_depth_threshold`` and the number of results.
The list of tags will be ordered in tree order (and alphabetically). If it has child tags, they must also be ordered alphabetically.

**Example**::

  {
    "count": 100,
    "tags": [
        {
            "value": "Tag 1",
            "depth": 0,
            "external_id": None,
            "child_count": 15,
            "parent_value": None,
            "sub_tags_url": "http//api-call-to-get-children.com"
        },
        (....)
    ]
  }


**Pros:**

- The edX's interfaces show the tags in the form of a tree.
- The frontend needs no further processing as it is in a displayable format.
- It is kept as a simple implementation.


Backend Python API
~~~~~~~~~~~~~~~~~~

On the backend, a very flexible API is available as ``Taxonomy.get_filtered_tags()`` which can cover all of the same use cases as the REST API endpoint (listing tags, shallow or deep, filtering on search term). However, the Python API returns a ``QuerySet`` of tag data dictionaries, rather than a JSON response.


Rejected Options
-----------------


Render as a simple list of tags
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Return a simple list of tags, regardless of whether it is root or leaf.

**Pros:**

- It is simple and does not need further implementation and processing in the API.

**Cons:**

- It is more work to re-process all that list in the frontend to know who it is whose father.
- In no edX's interface is it used this way and it would be a very specific use case.
- Pagination would be more complicated to perform.


Add the children to the root pagination
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ex. If the ``page_size`` is 100, when fetching the first root tag, which has 10 children tags, 
11 tags are counted for the total and there would be reamin 89 tags to be obtained.

**Cons:**

- If there is a branch with a number of tags that exceeds ``page_size``, 
  it would only return that branch.
- All branches are variable in size, therefore a variable number of root tags
  would be returned. This would cause interfaces between taxonomies to be inconsistent
  in the number of root tags shown.


Search on frontend
~~~~~~~~~~~~~~~~~~

We constrain the number of tags allowed in a taxonomy for MVP, so that the API 
can return all the tags in one page. So we can perform the tag search on the frontend.

**Cons:**

- It is not scalable.
- Sets limits of tags that can be created in the taxonomy.
