"""
Signal handlers for Collections.

This is to catch updates when things are published.
"""

def update_collections_from_publish(sender, publish_log=None, **kwargs):
    collections_to_update = publish_log
    print(publish_log)

