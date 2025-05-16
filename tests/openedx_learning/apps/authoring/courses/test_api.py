"""
Basic tests for the units API.
"""
from datetime import datetime, timezone

from openedx_learning.api import authoring as authoring_api
from openedx_learning.lib.test_utils import TestCase

Entry = authoring_api.UnitListEntry


class CoursesTestCase(TestCase):
    """ Test cases for CatalogCourse + Course """

    def setUp(self) -> None:
        super().setUp()
        self.learning_package = authoring_api.create_learning_package(
            key="CoursesTestCase",
            title="CoursesTestCase",
        )
        self.now = datetime(2025, 10, 20, tzinfo=timezone.utc)

    def test_create_course_and_run(self) -> None:
        """
        Test creating a Catalog Course and Course Run
        (i.e. what users normally think of as "Create a Course")
        """
        course = authoring_api.create_course_and_run(
            org_id="Org",
            course_id="MarineBio",
            run="25A",
            title="Intro to Marine Biology",
            learning_package_id=self.learning_package.id,
            created=self.now,
            created_by=None,
        )

        assert course.catalog_course.org_id == "Org"
        assert course.catalog_course.course_id == "MarineBio"
        assert course.run == "25A"
        assert course.outline_root.created == self.now
        assert course.outline_root.created_by is None
        # There is a draft "version 1" of the course, and it's completely empty:
        assert course.outline_root.versioning.draft.title == "Intro to Marine Biology"
        assert course.outline_root.versioning.draft.version_num == 1
        assert course.outline_root.versioning.draft.created == self.now
        assert course.outline_root.versioning.draft.created_by is None
        assert not authoring_api.get_entities_in_container(course.outline_root, published=False)
        # There is no published version of the course:
        assert course.outline_root.versioning.published is None

    def test_create_empty_course_and_run(self) -> None:
        """
        Test creating a Catalog Course and Course Run but without any initial
        version (this would be done e.g. at the start of an import workflow)
        """
        course = authoring_api.create_course_and_run(
            org_id="Org",
            course_id="MarineBio",
            run="25A",
            title="",  # title is ignored when initial_blank_version=False
            learning_package_id=self.learning_package.id,
            created=self.now,
            created_by=None,
            initial_blank_version=False,
        )

        assert course.catalog_course.org_id == "Org"
        assert course.catalog_course.course_id == "MarineBio"
        assert course.run == "25A"
        assert course.outline_root.created == self.now
        assert course.outline_root.created_by is None
        # There is no "version 1" of the course:
        assert course.outline_root.versioning.draft is None
        assert course.outline_root.versioning.published is None
