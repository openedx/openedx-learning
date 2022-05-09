# type: ignore
# variable: ignore
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



def write_lib_to_lms(library_key):

   # Find the existing state in the LMS
   existing_content = get_content_summary(library_key, branch="draft")

   # Figure out what the state is in Studio's Modulestore
   desired_content = generate_content_summary(library_key)

   # Diff the two to see what things we need to write
   content_keys_to_write = diff_content_summaries(existing_content, desired_content)

   if not content_keys_to_write:
      # Some early return logic here

   # This is some generator so we don't have to pull everything into memory at once.
   content_to_write = get_contents(library_key, keys=content_keys_to_write)


   with transaction.atomic():
      # Step 1: Write the bare content objects, with no policy information
      publishing_api.write_contents(content_obj)

      # Step 2: Write compositional data to stitch together
      




def create_partitions():
    pass


class ContentObject(models.Model):
    """
    This is the long-lived representation of a piece of content.

    Actual metadata lives in versions.
    """
    identifier = identifier_field(unique=False)
    content_package = models.ForeignKey(ContentPackage, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            # Within a ContentPackage, ContentObject identifiers are unique.
            models.UniqueConstraint(
                fields=["content_package_id", "identifier"],
                name="learning_publishing_co_uniq_cp_ident",
            )
        ]


class ContentObjectVersion(models.Model):
    uuid = immutable_uuid_field()
    content_object = models.ForeignKey(ContentObject, on_delete=models.CASCADE)
    version_num = models.PositiveIntegerField()

    class Meta:
        constraints = [
            # Within a ContentObject, version numbers are unique.
            models.UniqueConstraint(
                fields=["content_object_id", "version_num"],
                name="learning_publishing_cov_uniq_co_version_num",
            )
        ]





class ContentObject(models.Model):
    """
    This is the long-lived representation of a piece of content.

    Actual metadata lives in versions.
    """
    uuid = immutable_uuid_field()