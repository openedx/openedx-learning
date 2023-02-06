from rest_framework import serializers, viewsets
from rest_framework.response import Response

from ...models import Library

class LibrarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Library
        fields = [
            'learning_package',
        #    'uuid',
        #    'identifier',
        #    'title',
        #    'created',
        #    'updated',
        ]

class LibraryViewSet(viewsets.ModelViewSet):
    queryset = Library.objects.all().select_related('learning_package')
    serializer_class = LibrarySerializer    

class LibraryViewSet2(viewsets.ViewSet):
    
    def list(self, request):
        pass

    