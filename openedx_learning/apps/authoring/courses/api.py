"""
Low Level Courses and Course Runs API

🛑 UNSTABLE: All APIs related to courses in Learning Core are unstable until
they have parity with modulestore courses.
"""
from __future__ import annotations

from datetime import datetime
from logging import getLogger

from .models import Course

# The public API that will be re-exported by openedx_learning.apps.authoring.api
# is listed in the __all__ entries below. Internal helper functions that are
# private to this module should start with an underscore. If a function does not
# start with an underscore AND it is not in __all__, that function is considered
# to be callable only by other apps in the authoring package.
__all__ = [
    "create_course_and_run",
    "create_run",
]


log = getLogger()


def create_course_and_run(
    org_id: str,
    course_id: str,
    run: str,
    *,
    learning_package_id: int,
    created: datetime,
) -> Course:
    """
    Create a new course (CatalogCourse and Course / run).
    """
    raise NotImplementedError


def create_run(
    source_course: Course,
    new_run: str,
    *,
    created: datetime,
) -> Course:
    """
    Create a new run of the given course, with the same content.
    """
    raise NotImplementedError
