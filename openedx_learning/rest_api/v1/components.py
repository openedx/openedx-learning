"""
This is just an example REST API endpoint.
"""
from rest_framework import viewsets

from openedx_learning.core.components.models import Component


class ComponentViewSet(viewsets.ViewSet):
    """
    Example endpoints for a Components REST API. Not implemented.
    """
    def list(self, request):
        _items = Component.objects.all()
        raise NotImplementedError

    def retrieve(self, request, pk=None):
        raise NotImplementedError

    def create(self, request):
        raise NotImplementedError

    def update(self, request, pk=None):
        raise NotImplementedError

    def partial_update(self, request, pk=None):
        raise NotImplementedError

    def destroy(self, request, pk=None):
        raise NotImplementedError
