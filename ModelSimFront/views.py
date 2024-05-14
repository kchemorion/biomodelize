from django.http import JsonResponse
from django.shortcuts import render
from rest_framework.views import APIView
import os
import glob
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
from django.conf import settings
import libsbml
import roadrunner
import uuid

# Define model classes (Compartment, Species, Reaction, UnitDefinition, Parameter, Event)
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

# Function to parse SBML file
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

# Function to draw reaction graph
def draw_reaction_graph(filename, output_path):
    # Read the network data from an Excel file
    nw = pd.read_excel(filename)
    num_of_nodes = len(nw['Nodes'])
    node_names = nw['Nodes'].tolist()

    # Initialize a directed graph
    G = nx.DiGraph()

    # Add nodes
    for node in node_names:
        G.add_node(node)

    # Add edges for activation and inhibition
    for i in range(num_of_nodes):
        activators = str(nw['Activators'][i]).split(',')
        inhibitors = str(nw['Inhibitors'][i]).split(',')

        # Clean the node names from spaces and check if they are not NaN
        activators = [act.strip() for act in activators if act.strip() in node_names]
        inhibitors = [inh.strip() for inh in inhibitors if inh.strip() in node_names]

        current_node = node_names[i]

        # Add edges for each activator
        for act in activators:
            if act:  # Check to make sure 'act' is not an empty string
                G.add_edge(act, current_node, color='green', relationship='activates')

        # Add edges for each inhibitor
        for inh in inhibitors:
            if inh:  # Check to make sure 'inh' is not an empty string
                G.add_edge(inh, current_node, color='red', relationship='inhibits')

    # Use a different layout to spread nodes more effectively
    pos = nx.kamada_kawai_layout(G)  # You can also try nx.circular_layout or nx.fruchterman_reingold_layout

    # Draw the graph
    plt.figure(figsize=(24, 24))  # Increase figure size
    edges = G.edges(data=True)
    colors = [data['color'] for u, v, data in edges]
    nx.draw(G, pos, edge_color=colors, with_labels=True, node_color='lightblue', node_size=3000, font_size=12)  # Adjust node size and font size
    edge_labels = dict([((u, v,), d['relationship'])
                        for u, v, d in G.edges(data=True)])
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_color='blue')  # Adjust font color for visibility

    plt.title('Reaction Graph from Network Data')
    plt.savefig(output_path)  # Save as a larger image
    plt.close()

# Endpoint to view SBML
class ViewSBML(APIView):
    def get(self, request, format=None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sbml_files = glob.glob(os.path.join(base_dir, '*.xml'))

        if sbml_files:
            sbml_file = sbml_files[0]
        else:
            return render(request, 'error.html', {'error_message': "No SBML files found in the directory."})

        model_data, errors = parse_sbml(sbml_file)

        if errors:
            return render(request, 'error.html', {'error_message': errors})

        # Generate the reaction graph image
        network_data_file = os.path.join(base_dir, 'CRT.xlsx')  # Ensure this path is correct
        output_path = os.path.join(settings.MEDIA_ROOT, 'reaction_graph.png')
        draw_reaction_graph(network_data_file, output_path)
        reaction_graph_url = os.path.join(settings.MEDIA_URL, 'reaction_graph.png')

        return render(request, 'view_sbml.html', {'model_data': model_data, 'reaction_graph_url': reaction_graph_url})

# Endpoint to run simulation
import json

class RunSimulation(APIView):
    def post(self, request, format=None):
        try:
            files_in_current_folder = os.listdir()
            sbml_files = [file for file in files_in_current_folder if file.endswith('.xml')]

            if not sbml_files:
                return JsonResponse({'success': False, 'message': 'No SBML files found in the current directory.'})

            sbml_file = sbml_files[0]
            sbml_file_path = os.path.join(os.getcwd(), sbml_file)
            rr = roadrunner.RoadRunner(sbml_file_path)
            results = rr.simulate(0, 30, 100)

            # Define the species indices for each category
            plot_indices = {
                'Pro-Inflammatory': [0, 1, 2],
                'Anti-Inflammatory': [3],
                'Growth factors': [9],
                'ECM Destruction': [0, 1],
                'ECM Synthesis': [2],
                'Hypertrophy': [49]
            }

            # Create subplots for each category
            num_categories = len(plot_indices)
            fig, axes = plt.subplots(num_categories, 1, figsize=(10, 2 * num_categories), sharex=True)

            if num_categories == 1:
                axes = [axes]  # Ensure axes is iterable when there's only one subplot

            for ax, (category, indices) in zip(axes, plot_indices.items()):
                indices_to_plot = [i + 1 for i in indices]  # +1 because the first column is time
                filtered_results = results[:, [0] + indices_to_plot]
                filtered_colnames = [results.colnames[0]] + [results.colnames[i + 1] for i in indices]

                for idx in range(1, filtered_results.shape[1]):  # Skip the first column (time)
                    ax.plot(filtered_results[:, 0], filtered_results[:, idx], label=filtered_colnames[idx])

                ax.set_title(category)
                ax.set_ylabel('Concentration')
                ax.legend()

            plt.xlabel('Time')

            random_filename = str(uuid.uuid4()) + '.png'
            plot_path = os.path.join(settings.MEDIA_ROOT, random_filename)
            plt.savefig(plot_path)
            plt.close()  # Close the plot to prevent memory leaks

            plot_image_url = os.path.join(settings.MEDIA_URL, random_filename)

            simulation_data = []
            for i in range(len(results)):
                simulation_data.append(dict(zip(results.colnames, results[i])))

            return JsonResponse({'success': True, 'simulation_data': simulation_data, 'plot_url': plot_image_url})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

# Endpoint to update parameters
class UpdateParameters(APIView):
    def post(self, request, format=None):
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sbml_files = glob.glob(os.path.join(base_dir, '*.xml'))

            if not sbml_files:
                return JsonResponse({'success': False, 'message': 'No SBML files found in the directory.'})

            sbml_file = sbml_files[0]

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
                new_value_str = request.POST.get(parameter_id)
                if new_value_str is not None:
                    new_value = float(new_value_str)
                    model.getParameter(i).setValue(new_value)

            writer = libsbml.SBMLWriter()
            writer.writeSBMLToFile(document, sbml_file)

            return JsonResponse({'success': True, 'message': 'Parameters updated successfully.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

