from django.urls import path
from . import views

urlpatterns = [
    path('', views.view_sbml, name='view_sbml'),
    path('update_parameters/', views.update_parameters, name='update_parameters'), 
    path('visualize/', views.visualize_data, name='visualize_data'),
]