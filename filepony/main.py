"""

"""
from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.responses import StreamingResponse

from . import django_init
from asgiref.sync import sync_to_async

django_init.setup()

from .asset_api import get_content

# FastAPI init:
app = FastAPI()


# Example URL: /components/lp129/finalexam-problem14/1/static/images/finalexam-problem14_fig1.png
@app.get(
    "/components/{package_identifier}/{component_identifier}/{version_num}/{asset_path:path}"
)
async def component_asset(
    package_identifier: str,
    component_identifier: str,
    version_num: int,
    asset_path: str,
) -> StreamingResponse:
    content = await sync_to_async(get_content, thread_sensitive=True)(
        package_identifier, component_identifier, version_num, asset_path
    )
    path = content.file.path
    return FileResponse(path, media_type=content.mime_type)
