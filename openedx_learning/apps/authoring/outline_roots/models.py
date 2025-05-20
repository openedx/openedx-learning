"""
Models that implement the "outline root" for each course
"""
from django.db import models

from ..publishing.models import Container, ContainerVersion

__all__ = [
    "OutlineRoot",
    "OutlineRootVersion",
]


class OutlineRoot(Container):
    """
    A OutlineRoot is type of Container that defines the root of each course.

    Every course run has one OutlineRoot, and it typically has a list of
    Sections that comprise the course, which in turn have Subsections, Units,
    and Components. However, we also allow OutlineRoot to have Subsections or
    Units as its children, to facilitate smaller courses that don't need a
    three-level hierarchy.

    The requirements for OutlineRoot are:
    - One OutlineRoot per course run
    - Children must all be containers (Sections, Subsections, or Units) and
      all children must be the same type
    - Never used in libraries
    - Never added as a child of another container type

    Via Container and its PublishableEntityMixin, OutlineRoots are publishable
    entities.
    """
    container = models.OneToOneField(
        Container,
        on_delete=models.CASCADE,
        parent_link=True,
        primary_key=True,
    )


class OutlineRootVersion(ContainerVersion):
    """
    A OutlineRootVersion is a specific version of a OutlineRoot.

    Via ContainerVersion and its EntityList, it defines the list of
    Sections[/Subsections/Units] in this version of the OutlineRoot.
    """
    container_version = models.OneToOneField(
        ContainerVersion,
        on_delete=models.CASCADE,
        parent_link=True,
        primary_key=True,
    )

    @property
    def outline_root(self):
        """ Convenience accessor to the Section this version is associated with """
        return self.container_version.container.outline_root  # pylint: disable=no-member
