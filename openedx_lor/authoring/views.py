from pipes import Template
from django.template.response import TemplateResponse

from openedx_learning.core.itemstore.models import Item

def item_list(request):
    items = Item.objects.all()
    context = {
        'items': items,
    }
    return TemplateResponse(request, 'authoring/item/list.html', context)

def item_create(request):
    pass
