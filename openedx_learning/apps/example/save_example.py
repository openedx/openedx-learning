"""
We're dealing with a few different problems here:

1. We want to be able to publish content incrementally, not rebuild everything
   at once. Diff pattern maybe?

In the most common case, there won't be any actual change in the content at all.

What is the shared data model for that?

Maybe it's easiest to just always create a root and repeat data a bit if it will
allow for easy cleanup later.

So in that case, the practice would be:

1. Make a root object to associate with a version of your app's data.
2. Determine if the new versioned data is any different than what you already had.
3. If it isn't, don't make anything new, just make a new assocation between
   LearningContextVersion and your existing content root.



"""
# type: ignore
# variable: ignore


test = foo()

from openedx_learning.apps.core.learning_publishing.api import create_version


def write_to_lms(course):
    """
    This what writing content to the LMS might look like.
    
    How do we deal with LearningApps that never report back?
    """
    partitioning_data = get_partition_data_for_course(course.partitions)
    version = course_version
    lc_version = publishing_api.create_version(context_key, course.version)
    partitioning_api.update_partitions(lc_version, course)



def create_partitions():
    pass

