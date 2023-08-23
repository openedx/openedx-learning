13. Single taxonomy view API
=====================================


Context
--------

This view returns tags of a closed taxonomy (for MVP has not been implemented yet
for open taxonomies). It is necessary to make a decision about what structure the tags are going 
to have, how the pagination is going to work and how will the search for tags be implemented.
It was taken into account that a taxonomy can have a large number of tags and are mostly represented as trees.

**Branch:** Is the representation of a root Tag and all its children up to the leaves.

For the decisions, the following use cases were taken into account:

- As a taxonomy administrator, I want to see all the tags available for use with a closed taxonomy,
  so that I can see the taxonomy's structure in the management interface.
     - As a taxonomy administrator, I want to see the available tags as a lits of root tags
       that can be expanded to show children tags.
     - As a taxonomy administrator, I want to sort the list of root tags alphabetically: A-Z (default) and Z-A.
     - As a taxonomy administrator, I want to expand all root tags to see all children tags.
     - As a taxonomy administrator, I want to search for tags, so I can find root and children tags more easily.
- (TODO: discuss with UX) As a course author, when I am editing the tags of a component, I want to see all the tags available
  from a particular taxonomy that I can use.

Excluded use cases:

- As a content author, when searching/filtering a course/library, I want to see which tags are applied to the content
  and use them to refine my search. - This is excluded from this API's use case because this is automatically handled
  by elasticsearch/opensearch.


Decision
---------


Tag representation
~~~~~~~~

Return a list of root tags and within each one have the list of children tags. Each root would have
its entire branch. The list of root tags will be ordered alphabetically as is each listing
at each level of the tree. This order can only be reversed in the root tag listing.

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
        },
        (....)
    ]
}


**Pros:**

- The edX's interfaces show the tags in the form of a tree.
- The frontend needs no further processing as it is in a displayable format.
- It is kept as a simple implementation.

**Cons:**

- More implementation on the API side.


Pagination
~~~~~~~~~~~

Apply the pagination only in the root tags and bring the entire branch of each root.
Children do not affect pagination in any way.

**Pros**

- It is the simplest way.

**Cons**

- The children would not have pagination, in the long run there may be cases in which
  the branch has hundreds of children, and they would still all be brought.


Search tags
~~~~~~~~~~~~

Support tag search on the backend. Return a subset of matching tags in the format proposed
in this document.

**Pros**

- It is the most scalable way.


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



Get the branch in another call
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


Get the root tags in one call and all children tags of a branch in another call.
This second function is called when the user expands the parent tag.

**Cons:**

- In the UI there is the functionality *Expand all*, another view would have to 
  be made to handle this functionality in a scalable way.
- A user could make many calls; every time a parent is opened.



Add the children to the pagination
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

- It is not scalable
- Sets limits of tags that can be created in the taxonomy
