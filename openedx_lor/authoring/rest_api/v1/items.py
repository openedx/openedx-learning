from rest_framework import viewsets
from rest_framework.response import Response

from openedx_learning.core.itemstore.models import Item


class ItemViewSet(viewsets.ViewSet):
    
    def list(self, request):
        items = Item.objects.all()
        return Response({'hello': 'world'})

    def retrieve(self, request, pk=None):
        return Response({'hello': 'world'})

    def create(self, request):
        return Response({'hello': 'world'})

    def update(self, request, pk=None):
        return Response({'hello': 'world'})

    def partial_update(self, request, pk=None):
        return Response({'hello': 'world'})

    def destroy(self, request, pk=None):
        raise NotImplementedError
