"""
Utilities for tagging and taxonomy models
"""

RESERVED_TAG_CHARS = [
    '\t',  # Used in the database to separate tag levels in the "lineage" field
           # e.g. lineage="Earth\tNorth America\tMexico\tMexico City\t"
    ' > ',  # Used in the search index and Instantsearch frontend to separate tag levels
            # e.g. tags_level3="Earth > North America > Mexico > Mexico City"
    ';',   # Used in CSV exports to separate multiple tags from the same taxonomy
           # e.g. languages-v1: en;es;fr
]
TAGS_CSV_SEPARATOR = RESERVED_TAG_CHARS[2]
