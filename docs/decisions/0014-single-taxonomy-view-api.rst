13. Single taxonomy view API
=====================================

Context
--------

This view returns tags of a closed taxonomy (for MVP has not been implemented yet
for open taxonomies). It is necessary to make a decision about what structure the tags are going 
to have, how the pagination is going to work and how will the search for tags be implemented.
It was taken into account that taxonomies commonly have the following characteristics:

- It have few root tags.
- It have a very large number of children for each tag.
- It is mostly represented as trees on frontend.

For the decisions, the following use cases were taken into account:

- As a taxonomy administrator, I want to see all the tags available for use with a closed taxonomy,
  so that I can see the taxonomy's structure in the management interface.
    - As a taxonomy administrator, I want to see the available tags as a lits of root tags
      that can be expanded to show children tags.
    - As a taxonomy administrator, I want to sort the list of root tags alphabetically: A-Z (default) and Z-A.
    - As a taxonomy administrator, I want to expand all root tags to see all children tags.
    - As a taxonomy administrator, I want to search for tags, so I can find root and children tags more easily.
- As a course author, when I am editing the tags of a component, I want to see all the tags available
  from a particular taxonomy that I can use.
    - As a course author, I want to see the available tags as a lits of root tags
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

Make two different views:

- **get_root_tags():** It is the first call to obtain the parent tags of the taxonomy.
  It has pagination. In addition to the common pagination metadata, it is necessary to return:
    - Total number of pages.
    - Total number of root tags.
    - Range index of current page, Ex. Page 1: 1-12, Page 2: 13-24
    - Total number of children of each root tag.
- **get_children_tags():** Called each time the user expands a parent tag to see its children.
  It has pagination. In addition to the common pagination metadata, it is necessary to return:
    - Total number of children of each tag.

As described above, the pagination of root tags and child tags are independent.
In order to be able to fulfill the functionality of "Expand-all" in a scalable way,
the following has been agreed:

- Create a ``TAGS_THRESHOLD`` (default: 1000).
- If ``taxonomy.tags.count < TAGS_THRESHOLD``, then ``get_root_tags`` will return all tags on the taxonomy,
  roots and children.
- Otherwise, ``get_root_tags`` will only return root tags, and it will be necessary
  to use ``get_children_tags`` to return children. Also the "Expand-all" functionality will be disabled. 

**Pros**

- It is the simplest way.
- Paging both root tags and children mitigates the huge number of tags that can be.

Search tags
~~~~~~~~~~~~

Support tag search on the backend. Return a subset of matching tags.
We will use the same views to perform a search with the same logic:

- **get_root_tags(search: str)**
- **get_children_tags(search: str)**

For the search ``SEARCH_TAGS_THRESHOLD`` will be used. (It is recommended that it be 20 percent of ``TAGS_THRESHOLD``).
It will work in the same way of ``TAGS_THRESHOLD`` (see Views & Pagination)

**Pros**

- It is the most scalable way.

Tag representation
~~~~~~~~~~~~~~~~~~~

Return a list of root tags and within a link to obtain the children tags
or the complete list of children tags depending of ``TAGS_THRESHOLD`` or ``SEARCH_TAGS_THRESHOLD``. 
The list of root tags will be ordered alphabetically. If it has child tags, they must also
be ordered alphabetically.

**(taxonomy.tags.count < *_THRESHOLD)**::

  {
    "count": 100,
    "tags": [
        {
            "id": "tag_1",
            "value": "Tag 1",
            "taxonomy_id": "1",
            "sub_tags": [
                {
                    "id": "tag_2",
                    "value": "Tag 2",
                    "taxonomy_id": "1",
                    "sub_tags": [
                        (....)
                    ]
                },
                (....)
            ]
  }


**Otherwise**::

  {
    "count": 100,
    "tags": [
        {
            "id": "tag_1",
            "value": "Tag 1",
            "taxonomy_id": "1",
            "sub_tags_link": "http//api-call-to-get-children.com"
        },
        (....)
    ]
  }


**Pros:**

- The edX's interfaces show the tags in the form of a tree.
- The frontend needs no further processing as it is in a displayable format.
- It is kept as a simple implementation.


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
