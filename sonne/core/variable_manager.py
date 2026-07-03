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
import time
from datetime import datetime
from pathlib import Path
import logging
import importlib
from typing import Dict, Any, Optional

logger = logging.getLogger('sonne')

# Try to import Markup from the correct location
try:
    from markupsafe import Markup
except ImportError:
    try:
        from jinja2 import Markup
    except ImportError:
        # Fallback if Markup is not available
        class Markup(str):
            pass

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
        self.stats = None  # Injected by SiteGenerator
        
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
        scripts_path = config.get('paths', 'scripts', default='scripts') 
        scripts_dir = os.path.join(self.base_dir, scripts_path) if scripts_path else None
        self.scripts_dir = scripts_dir if scripts_dir and os.path.exists(scripts_dir) else None

        
    def _get_version(self) -> str:
        """Get the current version of Sonne."""
        try:
            import sonne.sonne as sonne
            return getattr(sonne, '__version__', '0.3.2')
        except ImportError:
            return '0.3.2'
            
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
        """Run data scripts to populate variables."""
        for script_path in Path(scripts_dir).glob('*.py'):
            # Skip files starting with underscore
            if script_path.name.startswith('_'):
                continue
                
            try:
                logger.info(f"  Script: {script_path.name}")

                # Create a module spec and load the module
                spec = importlib.util.spec_from_file_location(
                    f"sonne_script_{script_path.stem}", 
                    script_path
                )
                module = importlib.util.module_from_spec(spec)
                
                # Create a proper closure for sonne_var that captures the manager instance
                # This is critical for maintaining the reference to self
                def create_sonne_var(manager):
                    def sonne_var(k, v):
                        manager.variables['global'][k] = v
                        manager.variables['site'][k] = v
                        logger.debug(f"Variable set: {k}")
                    return sonne_var

                # Create helper function to get blog posts
                def create_get_post(manager):
                    def get_post(slug=None, tag=None):
                        """Get a blog post by slug or tag.

                        Args:
                            slug: The slug of the post to retrieve
                            tag: Return the first post with this tag

                        Returns:
                            Dictionary containing post data, or None if not found
                        """
                        posts = manager.variables.get('global', {}).get('all_blog_posts', [])
                        if not posts:
                            posts = manager.variables.get('site', {}).get('all_blog_posts', [])

                        if slug:
                            for post in posts:
                                if post.get('slug') == slug:
                                    return post
                        elif tag:
                            for post in posts:
                                if tag in post.get('tags', []):
                                    return post
                        return None
                    return get_post

                # Assign the closures
                module.sonne_var = create_sonne_var(self)
                module.get_post = create_get_post(self)

                # Add the module to sys.modules to ensure it's properly loaded
                sys.modules[f"sonne_script_{script_path.stem}"] = module

                # Execute the module
                _t0 = time.perf_counter()
                spec.loader.exec_module(module)
                if self.stats:
                    self.stats.record_script(script_path.name, time.perf_counter() - _t0)

                logger.debug(f"After {script_path.name}: globals={list(self.variables['global'].keys())}")

            except Exception as e:
                logger.error(f"Error running script {script_path}: {e}")
                if logger.level <= logging.DEBUG:
                    import traceback
                    traceback.print_exc()            
    def paths_get(self, key, default=None):
        """Helper to get path from config.paths."""
        paths = self.config.get('paths', default={})
        if isinstance(paths, dict):
            return paths.get(key, default)
        return default
                
    def load_variables(self) -> None:
        """Load all variables from configured sources."""
        # Preserve blog post variables if they were already set by collect_post_metadata()
        existing_blog_vars = {}
        if hasattr(self, 'variables'):
            for var_name in ['all_blog_posts', 'tags', 'categories']:
                if var_name in self.variables.get('global', {}):
                    existing_blog_vars[var_name] = self.variables['global'][var_name]

        # Initialize with empty variables
        self.variables = {
            'global': existing_blog_vars.copy(),  # Preserve blog post variables
            'site': {
                'generator': 'Sonne',
                'generator_version': self._get_version(),
                'build_time': datetime.now().isoformat(),
                'year': datetime.now().year,
                # Add default footer structure
                'footer': {
                    'custom': None
                },
                # Add other defaults needed by templates
                'nav': [],
                'language': 'en'
            },
            'page': {}
        }

        # Also add blog post variables to site scope for template access
        self.variables['site'].update(existing_blog_vars)

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
                        elif key == 'footer' and isinstance(value, dict):
                            # Merge with existing footer structure
                            self.variables['site']['footer'].update(value)
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

        # Restore fresh blog post variables after loading from variable file,
        # since the saved JSON may have stale post data (old dates, old URLs).
        if existing_blog_vars:
            self.variables['global'].update(existing_blog_vars)
            self.variables['site'].update(existing_blog_vars)

        # Load from data directory
        if self.data_dir:
            try:
                self._load_from_directory(self.data_dir, 'site')
                logger.debug(f"Loaded data from {self.data_dir}")
                
                # Specifically load project data
                self.load_project_data()
            except Exception as e:
                logger.error(f"Error loading data from {self.data_dir}: {e}")
                
        # Run data scripts - this should set battery variable
        if self.scripts_dir:
            try:
                self._run_data_scripts(self.scripts_dir)
                logger.debug(f"Scripts complete. Globals: {list(self.variables['global'].keys())}")
            except Exception as e:
                logger.error(f"Error running data scripts from {self.scripts_dir}: {e}")
                
        # Look for the footer.py script specifically in various locations
        footer_py_paths = [
            os.path.join(self.base_dir, 'data', 'footer.py'),
            os.path.join(self.paths_get('data'), 'footer.py') if self.paths_get('data') else None,
            os.path.join(self.base_dir, 'scripts', 'footer.py')
        ]
        
        footer_found = False
        for footer_path in footer_py_paths:
            if footer_path and os.path.exists(footer_path):
                try:
                    # Create a module spec and load the module
                    spec = importlib.util.spec_from_file_location(
                        "sonne_script_footer", 
                        footer_path
                    )
                    module = importlib.util.module_from_spec(spec)
                    sys.modules["sonne_script_footer"] = module
                    
                    # Add the sonne_var function to the module's namespace
                    def create_sonne_var(manager):
                        def sonne_var(k, v):
                            manager.set(k, v, 'global')
                            manager.set(k, v, 'site')
                        return sonne_var
                    
                    module.sonne_var = create_sonne_var(self)
                    
                    # Execute the module
                    spec.loader.exec_module(module)
                    
                    # Check if footer_custom was set
                    if 'footer_custom' in self.variables.get('global', {}):
                        # Mark the HTML content as safe
                        footer_content = self.variables['global']['footer_custom']
                        self.variables['global']['footer_custom'] = Markup(footer_content)
                        self.variables['site']['footer']['custom'] = Markup(footer_content)
                        
                    logger.debug(f"Loaded footer script: {footer_path}")
                    footer_found = True
                    break
                except Exception as e:
                    logger.error(f"Error running footer script at {footer_path}: {e}")
                    
        if not footer_found:
            logger.debug("No footer.py script found")
        
        # Make sure all global variables are also available in site scope
        for key, value in self.variables.get('global', {}).items():
            if key not in self.variables.get('site', {}):
                self.variables['site'][key] = value
                
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
            
        # Special handling for HTML content in certain variables
        if key in ['footer_custom'] and isinstance(value, str) and ('<' in value and '>' in value):
            # Likely HTML content, mark it as safe
            value = Markup(value)
        
        logger.debug(f"Setting variable {key} in scope {scope}")
        self.variables[scope][key] = value
        
        # Special handling for footer_custom
        if key == 'footer_custom' and scope == 'global':
            # Also set in site.footer.custom
            if 'site' not in self.variables:
                self.variables['site'] = {}
            if 'footer' not in self.variables['site']:
                self.variables['site']['footer'] = {}
            self.variables['site']['footer']['custom'] = value
        
        # For 'battery', ensure it's in site scope for template accessibility
        if key == 'battery' and scope in ['global', 'page']:
            self.variables['site'][key] = value
            logger.info(f"Battery variable set in {scope} and also in site scope")
        
    def set_page_variables(self, variables: Dict[str, Any]) -> None:
        """Set page-level variables.
        
        Args:
            variables: Dictionary of page variables.
        """
        self.variables['page'] = variables
        
        # For better accessibility, copy any battery or weather data to page scope
        for key in ['battery', 'weather', 'forecast']:
            if key in self.variables.get('global', {}):
                self.variables['page'][key] = self.variables['global'][key]
            elif key in self.variables.get('site', {}):
                self.variables['page'][key] = self.variables['site'][key]
        
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
        # SECURITY WARNING: This feature allows arbitrary Python code execution
        # It is DISABLED by default and must be explicitly enabled in configuration
        def execute_embedded_python(match):
            # Check if embedded Python is enabled in config
            allow_embedded_python = self.config.get('security', 'allow_embedded_python', default=False)

            if not allow_embedded_python:
                logger.warning("Embedded Python blocks are disabled. Set security.allow_embedded_python: true in config to enable (NOT RECOMMENDED for untrusted content).")
                return "<!-- Embedded Python disabled. Enable in config with security.allow_embedded_python: true -->"

            python_code = match.group(1).strip()

            # Log a security warning
            logger.warning("SECURITY: Executing embedded Python code from content file. This is a potential security risk.")
            logger.debug(f"Executing embedded Python code:\n{python_code}")

            # Create a restricted local scope with limited builtins
            # Remove dangerous builtins
            safe_builtins = {
                '__builtins__': {
                    'len': len, 'str': str, 'int': int, 'float': float, 'bool': bool,
                    'list': list, 'dict': dict, 'tuple': tuple, 'set': set,
                    'range': range, 'enumerate': enumerate, 'zip': zip,
                    'min': min, 'max': max, 'sum': sum, 'abs': abs,
                    'round': round, 'sorted': sorted, 'reversed': reversed,
                    'True': True, 'False': False, 'None': None,
                },
                'data': all_vars,
                'result': None,
            }

            try:
                # Execute the code with restricted scope
                exec(python_code, safe_builtins, safe_builtins)

                # Return the result
                return str(safe_builtins.get('result', ''))
            except Exception as e:
                logger.error(f"Error executing embedded Python: {e}")
                if logger.level <= logging.DEBUG:
                    import traceback
                    traceback.print_exc()
                return f"<!-- Error in Python Code: {str(e)} -->"

        # First execute Python code blocks (if enabled)
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
                # Convert Markup to string
                if hasattr(value, '__html__'):
                    value = str(value)
                    
                old_format[key] = {
                    "data": value,
                    "datetime": datetime.now().isoformat()
                }
                
            with open(self.variable_file, 'w', encoding='utf-8') as f:
                json.dump(old_format, f, indent=2, default=str)
                
            logger.debug(f"Saved variables to {self.variable_file}")
        except Exception as e:
            logger.error(f"Error saving variables: {e}")

    def load_project_data(self) -> None:
        """Load project data from JSON or YAML files in the data directory.
        
        This is a convenience method to ensure project data is loaded from common locations.
        """
        if not self.data_dir:
            logger.warning("No data directory found, unable to load project data")
            return
            
        project_files = [
            os.path.join(self.data_dir, 'projects.json'),
            os.path.join(self.data_dir, 'projects.yaml'),
            os.path.join(self.data_dir, 'projects.yml'),
            os.path.join(self.data_dir, 'portfolio.json'),
            os.path.join(self.data_dir, 'portfolio.yaml'),
            os.path.join(self.data_dir, 'portfolio.yml')
        ]
        
        for file_path in project_files:
            if os.path.exists(file_path):
                try:
                    logger.info(f"Loading project data from {file_path}")
                    self._load_from_file(file_path, 'global')
                    
                    # Check if 'projects' key exists in loaded data
                    if 'projects' in self.variables.get('global', {}):
                        # Ensure 'projects' is also directly available to templates
                        projects = self.variables['global']['projects']
                        logger.info(f"Found {len(projects)} projects in {file_path}")
                        
                        # Make 'projects' directly available at the top level
                        self.set('projects', projects, 'global')
                        # Also set in site scope
                        self.set('projects', projects, 'site')
                        return
                        
                except Exception as e:
                    logger.error(f"Error loading project data from {file_path}: {e}")
                    
        logger.warning("No project data found in data directory")