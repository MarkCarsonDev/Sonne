# Handles variable substitutions
import os
import re
import importlib.util
import json
from datetime import datetime

sonne_variables = {};

def execute_scripts(source_dir):
    for filename in os.listdir(source_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            file_path = os.path.join(source_dir, filename)
            spec = importlib.util.spec_from_file_location("module.name", file_path)
            module = importlib.util.module_from_spec(spec)

            module.__dict__['sonne_var'] = report_variable_init

            spec.loader.exec_module(module)
            print(f"Ran {filename}")

def report_variable_init(key, value):
    global sonne_variables
    sonne_variables[key] = {
        "data": value,
        "datetime": str(datetime.now())
    }
    print(f"Reported variable {key} with {value}")

def report_variable(key, value, variables_path):
    """Update or add a variable in the global sonne_variables dictionary and save to file."""
    global sonne_variables

    # Load the current variables from the file
    sonne_variables = load_variables(variables_path)

    # Update the variable
    sonne_variables[key] = {
        "data": value,
        "datetime": str(datetime.now())
    }
    print(f"Reported late variable {key} with value updated at {sonne_variables[key]['datetime']}")

    # Save the updated variables back to the file
    save_variables(sonne_variables, variables_path)

    

def process_variables(base_dir, config):
    global sonne_variables
    variables_path = os.path.join(base_dir, config.get_setting('DEFAULT', 'VariablesFile'))
    sonne_variables = load_variables(variables_path) \
            if config.get_setting('DEFAULT', 'PreservePriorVariables') else {}
    source_dir = os.path.join(base_dir, config.get_setting('DEFAULT', 'SourceDirectory'))
    execute_scripts(source_dir)
    save_variables(sonne_variables, variables_path)


def save_variables(data, filepath):

    with open(filepath, 'w') as file:
        json.dump(data, file)

def load_variables(filepath):
    if not os.path.exists(filepath):
        save_variables({}, filepath)

    with open(filepath, 'r') as file:
        return json.load(file)

def oneshot_get_variable_data(data_name, filepath):
    if not os.path.exists(filepath): 
        return

    with open(filepath, 'r') as file:
        variables = json.load(file)
        if not variables[data_name]: 
            return
        return variables[data_name]["data"]
    
def get_variable_data(data_name, data):
    if not data[data_name]: 
        return
    return str(data[data_name]["data"])

    
def substitute_variables(content, filepath):
    # Load the variable data from JSON file
    data = load_variables(filepath)

    # Function to replace each matched variable placeholder
    def replace_sonne_variable(match):
        var_name = match.group(1)

        # Retrieve the variable data if it exists
        try:
            return get_variable_data(var_name, data)
        except KeyError:
            print(f"Variable {var_name} not found.")
            # Return modified placeholder on KeyError
            return f"{{x}}{{{var_name}}}"

    # Correct the regex pattern and replace the placeholders in the content
    updated_content = re.sub(r'\{\+\}\{(.*?)\}', replace_sonne_variable, content)
    return updated_content