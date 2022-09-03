from django.urls import path

from . import views

urlpatterns = [
    path('item/', views.item_list, name='item_list'),
]
