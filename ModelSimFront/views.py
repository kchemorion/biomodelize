from django.http import HttpResponseRedirect
from django.urls import reverse
import libsbml
import os
import glob
import libsbml
from django.shortcuts import render
from django.http import JsonResponse

class Compartment:
    def __init__(self, id, name, size):
        self.id = id
        self.name = name
        self.size = size

class Species:
    def __init__(self, id, name, metaid, substance_units, has_only_substance_units, initial_value, compartment, charge):
        self.id = id
        self.name = name
        self.metaid = metaid
        self.substance_units = substance_units
        self.has_only_substance_units = has_only_substance_units
        self.initial_value = initial_value
        self.compartment = compartment
        self.charge = charge


class Reaction:
    def __init__(self, id, name, metaid, reactants, products, modifiers, math):
        self.id = id
        self.name = name
        self.metaid = metaid
        self.reactants = reactants
        self.products = products
        self.modifiers = modifiers
        self.math = math
        self.reactants_products = f"Reactants: {self.reactants}<br>Products: {self.products}"

class UnitDefinition:
    def __init__(self, id, name, metaid, units):
        self.id = id
        self.name = name
        self.metaid = metaid
        self.units = units


class Parameter:
    def __init__(self, id, name, metaid, units, value):
        self.id = id
        self.name = name
        self.metaid = metaid
        self.units = units
        self.value = value

class Event:
    def __init__(self, id, name):
        self.id = id
        self.name = name

import xml.etree.ElementTree as ET

def parse_sbml(sbml_file):
    reader = libsbml.SBMLReader()
    document = reader.readSBML(sbml_file)
    
    if document.getNumErrors() > 0:
        errors = document.getErrorLog().toString()
        return None, errors
    
    model = document.getModel()
    
    if model is None:
        return None, "No model found in the SBML file."
    
    model_data = {
        'model_id': model.getId(),
        'model_name': model.getName(),
        'num_compartments': model.getNumCompartments(),
        'num_species': model.getNumSpecies(),
        'num_reactions': model.getNumReactions(),
        'num_parameters': model.getNumParameters(),
        'num_events': model.getNumEvents(),
        'compartments': [],
        'species': [],
        'reactions': [],
        'parameters': [],
        'events': [],
        'unit_definitions': [],
        'model_metadata': None
    }


    for i in range(model.getNumCompartments()):
        compartment = model.getCompartment(i)
        model_data['compartments'].append(Compartment(compartment.getId(), compartment.getName(), compartment.getSize()))

    for i in range(model.getNumSpecies()):
        species = model.getSpecies(i)
        model_data['species'].append(Species(
            species.getId(),
            species.getName(),
            species.getMetaId(),
            species.getSubstanceUnits(),
            species.getHasOnlySubstanceUnits(),
            species.getInitialAmount(),
            species.getCompartment(),
            species.getCharge()
        ))
    
    num_unit_definitions = model.getNumUnitDefinitions()
    for i in range(num_unit_definitions):
        unit_definition = model.getUnitDefinition(i)
        units = "; ".join([f"{libsbml.UnitKind_toString(unit.getKind())} ({unit.getExponent()})" for unit in unit_definition.getListOfUnits()])
        model_data['unit_definitions'].append(UnitDefinition(
            unit_definition.getId(),
            unit_definition.getName(),
            unit_definition.getMetaId(),
            units
        ))


    for i in range(model.getNumReactions()):
        reaction = model.getReaction(i)
        equation = libsbml.formulaToL3String(reaction.getKineticLaw().getMath())
        
        reactants = "; ".join([f"{reactant.getSpecies()} ({reactant.getStoichiometry()})" if reactant.isSetStoichiometry() else reactant.getSpecies() for reactant in reaction.getListOfReactants()])
        products = "; ".join([f"{product.getSpecies()} ({product.getStoichiometry()})" if product.isSetStoichiometry() else product.getSpecies() for product in reaction.getListOfProducts()])
        
        modifiers = "; ".join([modifier.getSpecies() for modifier in reaction.getListOfModifiers()])
        
        model_data['reactions'].append(Reaction(
            reaction.getId(),
            reaction.getName(),
            reaction.getMetaId(),
            reactants,
            products,
            modifiers,
            equation
    ))


    for i in range(model.getNumParameters()):
        parameter = model.getParameter(i)
        model_data['parameters'].append(Parameter(
            parameter.getId(),
            parameter.getName(),
            parameter.getMetaId(),  # Get metaid
            parameter.getUnits(),   # Get units
            parameter.getValue()
        ))

    for i in range(model.getNumEvents()):
        event = model.getEvent(i)
        model_data['events'].append(Event(event.getId(), event.getName()))

    # Extract model metadata
    model_metadata = ""
    if model.isSetNotes():
        model_metadata += "Notes:\n" + model.getNotesString() + "\n"
    if model.isSetAnnotation():
        model_metadata +=  model.getAnnotationString() + "\n"

    model_data['model_metadata'] = model_metadata

    return model_data, None


def view_sbml(request):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sbml_files = glob.glob(os.path.join(base_dir, '*.xml'))

    if sbml_files:
        sbml_file = sbml_files[0]
    else:
        return render(request, 'error.html', {'error_message': "No SBML files found in the directory."})
    
    model_data, errors = parse_sbml(sbml_file)

    if errors:
        return render(request, 'error.html', {'error_message': errors})

    return render(request, 'view_sbml.html', {'model_data': model_data})


def update_parameters(request):
    if request.method == 'POST':
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sbml_files = glob.glob(os.path.join(base_dir, '*.xml'))

        if sbml_files:
            sbml_file = sbml_files[0]
        else:
            return JsonResponse({'success': False, 'message': 'No SBML files found in the directory.'})

        reader = libsbml.SBMLReader()
        document = reader.readSBML(sbml_file)

        if document.getNumErrors() > 0:
            errors = document.getErrorLog().toString()
            return JsonResponse({'success': False, 'message': errors})

        model = document.getModel()

        if model is None:
            return JsonResponse({'success': False, 'message': 'No model found in the SBML file.'})

        for i in range(model.getNumParameters()):
            parameter_id = model.getParameter(i).getId()
            new_value = float(request.POST.get(parameter_id))
            model.getParameter(i).setValue(new_value)

        # Write the updated model to the same file
        writer = libsbml.SBMLWriter()
        writer.writeSBMLToFile(document, sbml_file)

        # Return success response
        return JsonResponse({'success': True, 'message': 'Parameters updated successfully.'})
    else:
        # Handle GET request if needed
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})

from django.http import JsonResponse

def visualize_data(request):
    if request.method == 'POST':
        solver = request.POST.get('solver')
        # Perform actions based on the selected solver
        # Example: Run Tellurium simulation with the selected solver
        if solver == 'euler':
            # Run simulation using Euler solver
            simulation_result = run_euler_simulation()
        elif solver == 'runge_kutta':
            # Run simulation using Runge-Kutta solver
            simulation_result = run_runge_kutta_simulation()
        else:
            # Handle unsupported solver
            return JsonResponse({'success': False, 'message': 'Unsupported solver'})

        # Process simulation result and prepare visualization data
        visualization_data = process_simulation_result(simulation_result)

        # Return visualization data as JSON response
        return JsonResponse({'success': True, 'data': visualization_data})

    # Handle GET requests or other HTTP methods
    return JsonResponse({'success': False, 'message': 'Invalid request method'})
