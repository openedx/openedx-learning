"""
Taxonomy Import views
"""
from __future__ import annotations

import os

from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest
from rest_framework.request import Request
from rest_framework.views import APIView

from ...import_export import api
from .serializers import TaxonomyImportBodySerializer


class TemplateView(APIView):
    """
    View which serves the static Taxonomy Import template files.

    **Example Requests**
        GET /tagging/rest_api/v1/import/template.csv
        GET /tagging/rest_api/v1/import/template.json

    **Query Returns**
        * 200 - Success
        * 404 - Template file not found
        * 405 - Method not allowed
    """
    http_method_names = ['get']

    template_dir = os.path.join(
        os.path.dirname(__file__),
        "../../import_export/",
    )
    allowed_ext_to_content_type = {
        "csv": "text/csv",
        "json": "application/json",
    }

    def get(self, request: Request, file_ext: str, *args, **kwargs) -> FileResponse:
        """
        Downloads the requested file as an attachment,
        or raises 404 if not found.
        """
        content_type = self.allowed_ext_to_content_type.get(file_ext)
        if not content_type:
            raise Http404

        filename = f"template.{file_ext}"
        content_disposition = f'attachment; filename="{filename}"'
        fh = open(os.path.join(self.template_dir, filename), "rb")
        response = FileResponse(fh, content_type=content_type)
        response['Content-Disposition'] = content_disposition
        return response


class ImportView(APIView):
    """
    View to import taxonomies

    **Example Requests**
        POST /tagging/rest_api/v1/import/
        {
            "taxonomy_name": "Taxonomy Name",
            "taxonomy_description": "This is a description",
            "file": <file>,
        }

    **Query Returns**
        * 200 - Success
        * 400 - Bad request
        * 405 - Method not allowed
    """
    http_method_names = ['post']

    def post(self, request: Request, *args, **kwargs) -> HttpResponse:
        """
        Imports the taxonomy from the uploaded file.
        """
        body = TaxonomyImportBodySerializer(data=request.data)
        body.is_valid(raise_exception=True)

        taxonomy_name = body.validated_data["taxonomy_name"]
        taxonomy_description = body.validated_data["taxonomy_description"]
        file = body.validated_data["file"].file
        parser_format = body.validated_data["parser_format"]

        import_success = api.create_taxonomy_and_import_tags(
            taxonomy_name=taxonomy_name,
            taxonomy_description=taxonomy_description,
            file=file,
            parser_format=parser_format,
        )

        if import_success:
            return HttpResponse(status=200)
        else:
            return HttpResponseBadRequest("Error importing taxonomy")
