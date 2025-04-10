"""
Variable management for Sonne.
Handles loading, processing, and substituting variables in templates.
"""
import os
import json
import yaml
import csv
import re
import importlib.util
import sys
import subprocess
from datetime import datetime
from functools import lru_cache
from pathlib import Path
import logging
import importlib
from typing import Dict, Any, Optional, List, Tuple, Union

logger = logging.getLogger('sonne')

class VariableManager:
    """Manages variables and their substitution in templates."""
        
    def __init__(self, config, base_dir: str):
        """Initialize variable manager.
        
        Args:
            config: Site configuration.
            base_dir: Base directory of the site.
        """
        self.config = config
        self.base_dir = base_dir or os.getcwd()  # Use current directory if base_dir is None
        self.variables = {
            'global': {},
            'site': {},
            'page': {}
        }
        
        # Prepare variable file path
        var_file = config.get('variables', 'file', default='sonne_variables.json')
        
        # Ensure both parts are strings before joining
        if var_file:
            self.variable_file = os.path.join(self.base_dir, var_file)
        else:
            self.variable_file = os.path.join(self.base_dir, 'sonne_variables.json')
        
        # Prepare data directory path
        data_path = config.get('paths', 'data', default='data')
        data_dir = os.path.join(self.base_dir, data_path) if data_path else None
        self.data_dir = data_dir if data_dir and os.path.exists(data_dir) else None
        
        # Prepare scripts directory path
        scripts_path = config.get('paths', 'data', default='scripts') 
        scripts_dir = os.path.join(self.base_dir, scripts_path) if scripts_path else None
        self.scripts_dir = scripts_dir if scripts_dir and os.path.exists(scripts_dir) else None

        
    def _get_version(self) -> str:
        """Get the current version of Sonne."""
        try:
            import sonne.sonne as sonne
            return getattr(sonne, '__version__', '0.2.0')
        except ImportError:
            return '0.2.0'
            
    def _load_from_file(self, file_path: str, scope: str) -> None:
        """Load variables from a file based on its extension.
        
        Args:
            file_path: Path to the data file.
            scope: Variable scope ('global', 'site', or 'page').
        """
        ext = Path(file_path).suffix.lower()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            if ext in ['.json']:
                data = json.load(f)
            elif ext in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            elif ext == '.csv':
                reader = csv.DictReader(f)
                data = list(reader)
            else:
                # Unsupported format
                logger.warning(f"Unsupported data file format: {ext}")
                return
                
        # Update the appropriate scope
        if isinstance(data, dict):
            # For old-style Sonne variables with {"variable": {"data": value}}
            if all(isinstance(v, dict) and "data" in v for v in data.values()):
                for key, value_dict in data.items():
                    self.variables[scope][key] = value_dict.get("data")
            else:
                self.variables[scope].update(data)
        else:
            # For non-dict data (like CSV), store under the file's basename
            name = Path(file_path).stem
            self.variables[scope][name] = data
            
    def _load_from_directory(self, directory: str, scope: str) -> None:
        """Load all data files from a directory.
        
        Args:
            directory: Path to the data directory.
            scope: Variable scope ('global', 'site', or 'page').
        """
        for ext in ['*.json', '*.yaml', '*.yml', '*.csv']:
            for file_path in Path(directory).glob(f'**/{ext}'):
                try:
                    self._load_from_file(str(file_path), scope)
                except Exception as e:
                    logger.error(f"Error loading data from {file_path}: {e}")
                    
    def _run_data_scripts(self, scripts_dir: str) -> None:
        """Run data scripts to populate variables.
        
        Args:
            scripts_dir: Path to the directory containing data scripts.
        """
        for script_path in Path(scripts_dir).glob('*.py'):
            # Skip files starting with underscore
            if script_path.name.startswith('_'):
                continue
                
            try:
                # Create a module spec and load the module
                spec = importlib.util.spec_from_file_location(
                    f"sonne_script_{script_path.stem}", 
                    script_path
                )
                module = importlib.util.module_from_spec(spec)
                
                # Add the sonne_var function to the module's namespace
                module.sonne_var = lambda k, v: self.set(k, v, 'global')
                
                # Execute the module
                spec.loader.exec_module(module)
                logger.debug(f"Ran script: {script_path}")
                
            except Exception as e:
                logger.error(f"Error running script {script_path}: {e}")
                if logger.level <= logging.DEBUG:
                    import traceback
                    traceback.print_exc()
                    
    def load_variables(self) -> None:
        """Load all variables from configured sources."""
        # Initialize with empty variables
        self.variables = {
            'global': {},
            'site': {
                'generator': 'Sonne',
                'generator_version': self._get_version(),
                'build_time': datetime.now().isoformat(),
                'year': datetime.now().year,
            },
            'page': {}
        }

        # Add configuration to site variables - safely get site config
        try:
            # Get site configuration safely
            if hasattr(self.config, 'config') and isinstance(self.config.config, dict):
                site_config = self.config.config.get('site', {})
                if isinstance(site_config, dict):
                    # Process site configuration
                    for key, value in site_config.items():
                        # Safely handle the title field which might be a nested dict
                        if key == 'title' and isinstance(value, dict):
                            # If title is a dictionary, try to extract a usable title or use a default
                            if 'text' in value:
                                self.variables['site'][key] = value['text']
                            else:
                                self.variables['site'][key] = "My Sonne Site"
                        else:
                            self.variables['site'][key] = value
        except Exception as e:
            logger.error(f"Error processing site configuration: {e}")
            
        # Load from variable file if it exists
        if os.path.exists(self.variable_file):
            try:
                self._load_from_file(self.variable_file, 'global')
                logger.debug(f"Loaded variables from {self.variable_file}")
            except Exception as e:
                logger.error(f"Error loading variables from {self.variable_file}: {e}")
                
        # Load from data directory
        if self.data_dir:
            try:
                self._load_from_directory(self.data_dir, 'site')
                logger.debug(f"Loaded data from {self.data_dir}")
            except Exception as e:
                logger.error(f"Error loading data from {self.data_dir}: {e}")
                
        # Run data scripts
        if self.scripts_dir:
            try:
                self._run_data_scripts(self.scripts_dir)
                logger.debug(f"Ran data scripts from {self.scripts_dir}")
            except Exception as e:
                logger.error(f"Error running data scripts from {self.scripts_dir}: {e}")
        
                
    def get(self, key: str, default: Any = None, scope: Optional[str] = None) -> Any:
        """Get a variable value, optionally from a specific scope.
        
        Args:
            key: Variable name.
            default: Default value if variable not found.
            scope: Specific scope to search in. If None, searches all scopes.
            
        Returns:
            Variable value or default if not found.
        """
        if scope:
            return self.variables.get(scope, {}).get(key, default)
            
        # Search all scopes in order: page, site, global
        for current_scope in ['page', 'site', 'global']:
            if key in self.variables.get(current_scope, {}):
                return self.variables[current_scope][key]
                
        return default
        
    def get_all(self) -> Dict[str, Any]:
        """Get all variables merged into a single dictionary.
        
        Returns:
            Dictionary containing all variables from all scopes.
        """
        result = {}
        # Merge in order of precedence: global, site, page
        result.update(self.variables.get('global', {}))
        result.update(self.variables.get('site', {}))
        result.update(self.variables.get('page', {}))
        return result
        
    def set(self, key: str, value: Any, scope: str = 'site') -> None:
        """Set a variable value in the specified scope.
        
        Args:
            key: Variable name.
            value: Variable value.
            scope: Variable scope ('global', 'site', or 'page').
        """
        if scope not in self.variables:
            self.variables[scope] = {}
            
        self.variables[scope][key] = value
        
    def set_page_variables(self, variables: Dict[str, Any]) -> None:
        """Set page-level variables.
        
        Args:
            variables: Dictionary of page variables.
        """
        self.variables['page'] = variables
        
    def substitute_variables(self, content: str) -> str:
        """Substitute variables in content. Handles both Mond and Sonne variable formats.
        
        Args:
            content: Content string containing variable references.
            
        Returns:
            String with variables substituted.
        """
        # Get all variables
        all_vars = self.get_all()
        
        # Replace Sonne variables: {+}{variable_name}
        def replace_sonne_variable(match):
            var_name = match.group(1)
            if var_name in all_vars:
                return str(all_vars[var_name])
            return f"{{+}}{{{var_name}}}"  # Keep the original if not found
            
        # Replace Mond variables: {-}{variable_name}
        def replace_mond_variable(match):
            var_name = match.group(1)
            if var_name in all_vars:
                return str(all_vars[var_name])
            return f"{{-}}{{{var_name}}}"  # Keep the original if not found
            
        # Execute embedded Python: {p}{# ... #}
        def execute_embedded_python(match):
            python_code = match.group(1).strip()
            
            # Prepare code for execution
            logger.debug(f"Executing embedded Python code:\n{python_code}")
            
            # Create a local scope with access to all variables
            local_scope = {'data': all_vars, 'result': None}
            
            try:
                # Execute the code
                exec(f"{python_code}", {}, local_scope)
                
                # Return the result
                return str(local_scope.get('result', ''))
            except Exception as e:
                logger.error(f"Error executing embedded Python: {e}")
                return f"<!-- Error in Python Code: {e} -->"
        
        # First execute Python code blocks
        content = re.sub(r'\{p\}\{#([\s\S]*?)#\}', execute_embedded_python, content)
        
        # Then replace variables
        content = re.sub(r'\{\+\}\{(.*?)\}', replace_sonne_variable, content)
        content = re.sub(r'\{\-\}\{(.*?)\}', replace_mond_variable, content)
        
        return content
        
    def save(self) -> None:
        """Save variables to file."""
        # Only save global variables
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(self.variable_file)), exist_ok=True)
            
            # Convert to old format for backward compatibility
            old_format = {}
            for key, value in self.variables.get('global', {}).items():
                old_format[key] = {
                    "data": value,
                    "datetime": datetime.now().isoformat()
                }
                
            with open(self.variable_file, 'w', encoding='utf-8') as f:
                json.dump(old_format, f, indent=2, default=str)
                
            logger.debug(f"Saved variables to {self.variable_file}")
        except Exception as e:
            logger.error(f"Error saving variables: {e}")