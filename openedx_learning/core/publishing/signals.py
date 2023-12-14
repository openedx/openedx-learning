"""
Publishing related, process-internal signals.
"""
from django.dispatch import Signal


# The PUBLISHED_PRE_COMMIT is sent:
#
# * AFTER a set of PublishableEntity models has been published–i.e. its entries
#   in the publishing.models.Published model have been updated to new versions
#   and a PublishLog entry has been created with associated PublishLogRecords.
# * BEFORE those publishing changes are committed to the database.
#
# This is the signal that you catch if you need to take actions when content is
# published, and failing those actions should cancel/rollback the publish. One
# case in which you might want to do this is if you have data models that need
# to track and add supplemental data to every PublishLog entry. A transient
# failure that occurs during this process might introduce data inconsistencies
# that we want to avoid. It's better to fail the entire request and force the
# system (or user) to try again.
#
# Do NOT try to catch this signal to launch a celery task. It is sent before
# the publishing model additions have been committed to the database, so they
# will not be accessible from another process. It may look like it's working
# because your celery processes are running in-process during development, or
# because delays in celery process launch allow the original request to commit
# before the celery task actually tries to run its query. But this kind of usage
# will cause issues in production environments at some point.
#
# Signal handlers should be simple and fast. Handlers should not do external web
# service calls, or anything else that is prone to unpredictable latency.
#
# providing_args=[
#     'publish_log', # instance of saved PublishLog
# ]
PUBLISHED_PRE_COMMIT = Signal()
