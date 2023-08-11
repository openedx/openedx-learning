13. Single taxonomy view API
=====================================


Context
--------

This view returns tags of a closed taxonomy (for MVP has not been implemented yet
for open taxonomies). It is necessary to make a decision about what structure the tags are going 
to have and how the pagination is going to work. It was taken into account that a taxonomy can
have a large number of tags and are mostly represented as trees.

**Branch:** Is the representation of a root Tag and all its children up to the leaves.


Decision
---------


Tag representation
~~~~~~~~

Return a list of root tags and within each one have the list of children tags. Each root would have
its entire branch. The list of root tags will be ordered alphabetically as is each listing at each level of the tree.

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


Rejected Options
-----------------


Render as a simple list of tags
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Return a simple list of tags, regardless of whether it is root or leaf.

**Pros:**

- It is simple and does not need further implementation and processing in the API.

**Cons:**

- It is more work to re-process all that list in the frontend to know who it is
whose father.
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
