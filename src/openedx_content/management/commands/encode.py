from datetime import datetime, timezone
import logging

from django.core.management import CommandError
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

import json


from pydantic import BaseModel, Field
from pydantic.config import ConfigDict
from pydantic.json_schema import models_json_schema

from typing import Annotated, Optional


class EntityVersion(BaseModel):
    version_num: int
    title: str

class VersionRef(BaseModel):
    version_num: Optional[int] = None

class Entity(BaseModel):
    can_stand_alone: bool
    key: str
    created: datetime
    draft: VersionRef
    published: VersionRef
    versions: list[EntityVersion]

class EntityRoot(BaseModel):
    entity: Entity

from openedx_content.applets.backup_restore.schema import (
    LearningPackageOutputData, PackageConfigOutputData, MetaOutputData
)

class Command(BaseCommand):
    """
    Django management command to export a learning package to a zip file.
    """
    help = 'Export a learning package to a zip file.'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        now = datetime.now(tz=timezone.utc)
        config = PackageConfigOutputData(
            meta=MetaOutputData(
                format_version=1,
                created_by="dave",
                created_by_email="dave@axim.org",
                created_at=now,
            ),
            learning_package=LearningPackageOutputData(
                title="Fun Library",
                key="lib:Axim:FunLib",
                description="",
                created=now,
                updated=now,
                origin_server="studio.local.openedx.io:8001",
            )
        )
        toml_output = tomli_w.dumps(config.model_dump(exclude_defaults=False))
        print(toml_output)

        print(json.dumps(PackageConfigOutputData.model_json_schema(), indent=2))


    def handle_old(self, *args, **options):
        e = Entity(
            can_stand_alone=True,
            key="xblock.v1:html:hi-there-9d01929cda81",
            created=datetime.now(tz=timezone.utc),
            draft=VersionRef(version_num=3),
            published=VersionRef(version_num=None),
            versions = [
                EntityVersion(
                    version_num=x,
                    title=f"Title {x}",
                )
                for x in range(10)
            ],
        )
        base = EntityRoot(
            entity=e,
        )

        #toml_output = tomli_w.dumps(base.model_dump(exclude_defaults=True))
        #print(toml_output)


        print(json.dumps(EntityRoot.model_json_schema(), indent=2))

