from django.urls import path
from .views import RunSimulation, ViewSBML, UpdateParameters

urlpatterns = [
    path('', ViewSBML.as_view(), name='view_sbml'),
    path('update_parameters/', UpdateParameters.as_view(), name='update_parameters'), 
    path('run_simulation/', RunSimulation.as_view(), name='run_simulation'),
]
