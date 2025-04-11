"""
Configuration management for Sonne.
Supports multiple configuration formats and provides validation.
"""

import os
import json
import yaml
from pathlib import Path
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger('sonne')

# Default configuration settings
DEFAULT_CONFIG = {
    'site': {
        'title': 'My Sonne Site',
        'base_url': 'http://localhost',
        'description': 'A site built with Sonne',
        'author': 'Sonne User',
        'keywords': [],
        'language': 'en',
    },
    'paths': {
        'content': 'content',
        'output': 'output',
        'static': 'static',
        'templates': 'templates',
        'data': 'data',
        'cache': '.cache',
    },
    'blog': {
        'enabled': True,
        'directory': 'blog',
        'template': 'blog_post.html',
        'list_template': 'blog_list.html',
        'posts_per_page': 10,
        'excerpt_length': 200,
        'url_pattern': '{year}/{month}/{day}/{slug}',
        'include_drafts': False,
        'taxonomies': {
            'tags': {
                'enabled': True,
                'template': 'tag.html',
                'list_template': 'tags.html',
            },
            'categories': {
                'enabled': True,
                'template': 'category.html',
                'list_template': 'categories.html',
            },
        },
    },
    'images': {
        'dither': True,
        'optimize': True,
        'formats': ['webp', 'png'],
        'sizes': [1200, 800, 400],
        'lazy_loading': True,
    },
    'variables': {
        'file': 'sonne_variables.json',
        'preserve_prior': False,
    },
    'url_style': {
        'prod': 'clean',
        'dev': 'directory',
    },
    'environment': 'prod',
}

class Config:
    """Configuration management for Sonne."""
    
    def __init__(self, config_path: Optional[str] = None, base_dir: Optional[str] = None):
        """Initialize configuration with optional path to config file.
        
        Args:
            config_path: Path to configuration file. If None, looks for default locations.
            base_dir: Base directory to search for config files. If None, uses current directory.
        """
        self.base_dir = base_dir or os.getcwd()
        self.config_path = config_path or self._find_config()
        self.config = self._load_config()
        
    def _find_config(self) -> Optional[str]:
        """Search for configuration file in standard locations.
        
        Returns:
            Path to config file if found, None otherwise.
        """
        search_paths = [
            'sonne.yaml', 'sonne.yml', 'sonne.json', '.sonne/config.yaml',
            'sonne.config', '.sonne.yaml', '.sonne.json'
        ]
        
        # Look in specified base directory and parent directories
        current_dir = os.path.abspath(self.base_dir)
        
        # Search in current and parent directories (up to 3 levels)
        for _ in range(3):
            for path in search_paths:
                full_path = os.path.join(current_dir, path)
                if os.path.exists(full_path):
                    print(f"Found configuration file at {full_path}")
                    return full_path
            
            # Move up one directory
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:  # Reached root
                break
            current_dir = parent_dir
                
        print("No configuration file found, using defaults")
        return None
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file and merge with defaults.
        
        Returns:
            Complete configuration dictionary.
        """
        config = DEFAULT_CONFIG.copy()
        
        if not self.config_path:
            return config
            
        try:
            ext = Path(self.config_path).suffix.lower()
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if ext in ['.yaml', '.yml']:
                    user_config = yaml.safe_load(f)
                elif ext == '.json' or ext == '.config':
                    user_config = json.load(f)
                else:
                    logger.warning(f"Unsupported config format: {ext}")
                    return config
                    
                # Deep merge with defaults
                self._deep_merge(user_config, config)
                logger.debug(f"Loaded configuration from {self.config_path}")
                
        except Exception as e:
            logger.error(f"Error loading configuration file: {e}")
            logger.warning("Using default configuration")
            
        return config
        
    def _deep_merge(self, source: Dict[str, Any], destination: Dict[str, Any]) -> None:
        """Recursively merge source dictionary into destination.
        
        Args:
            source: Source dictionary with new values.
            destination: Destination dictionary to update.
        """
        for key, value in source.items():
            if key in destination and isinstance(destination[key], dict) and isinstance(value, dict):
                self._deep_merge(value, destination[key])
            else:
                destination[key] = value
                
    def get(self, *keys, default=None):
        """Get configuration value using dot notation or nested keys.
        
        Args:
            *keys: Key path to the desired configuration value.
            default: Default value if key is not found.
            
        Returns:
            Configuration value or default if not found.
        """
        if not keys:
            return default
        
        current = self.config

        for key in keys:
            if not isinstance(current, dict):
                return default
            if key not in current:
                return default
            current = current[key]

        return current
        
    def set(self, *keys, value=None):
        """Set configuration value using dot notation or nested keys.
        
        Args:
            *keys: Key path to the configuration value to set.
            value: Value to set.
        """
        if not keys:
            return
            
        # Navigate to the nested dictionary
        current = self.config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            elif not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
            
        # Set the value
        current[keys[-1]] = value
        
    def save(self, path: Optional[str] = None) -> None:
        """Save configuration to file.
        
        Args:
            path: Path to save configuration to. If None, uses current config path.
        """
        save_path = path or self.config_path
        
        if not save_path:
            logger.warning("No configuration path specified, not saving")
            return
            
        try:
            ext = Path(save_path).suffix.lower()
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            
            with open(save_path, 'w', encoding='utf-8') as f:
                if ext in ['.yaml', '.yml']:
                    yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
                elif ext == '.json' or ext == '.config':
                    json.dump(self.config, f, indent=2)
                else:
                    logger.warning(f"Unsupported config format for saving: {ext}")
                    return
                    
            logger.debug(f"Configuration saved to {save_path}")
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            
    def normalize_paths(self, base_dir: str) -> Dict[str, str]:
        """Normalize all path configurations to absolute paths.
        
        Args:
            base_dir: Base directory to resolve relative paths against.
            
        Returns:
            Dictionary of normalized paths.
        """
        paths = {}
        path_keys = self.get('paths')
        
        for key, value in path_keys.items():
            if not value:
                continue
                
            if not os.path.isabs(value):
                full_path = os.path.abspath(os.path.join(base_dir, value))
            else:
                full_path = value
                
            # Ensure the directory exists for output paths
            if key in ['output', 'cache']:
                os.makedirs(full_path, exist_ok=True)
                
            paths[key] = full_path
            
        return paths
    
    def get_url_style(self) -> str:
        """Get the URL style based on configuration and environment.
        
        Returns:
            One of 'clean', 'html', or 'directory'.
        """
        url_style = self.get('url_style')
        environment = self.get('environment', default='prod')
        
        logger.debug(f"URL style from config: {url_style}, Environment: {environment}")
        
        # If url_style is a string, use it directly
        if isinstance(url_style, str):
            return url_style
        
        # If url_style is a dict, get the environment-specific value
        if isinstance(url_style, dict):
            style = url_style.get(environment, 'clean')
            logger.debug(f"Using URL style '{style}' for environment '{environment}'")
            return style
        
        # Default to 'clean' if not specified
        logger.debug("Using default URL style 'clean'")
        return 'clean'
        
    def format_url(self, url: str) -> str:
        """Format a URL based on the current URL style configuration.
        
        Args:
            url: The URL to format (e.g. '/about')
            
        Returns:
            Formatted URL according to the current URL style.
        """
        # Skip external URLs or URLs that already have an extension
        if url.startswith(('http://', 'https://')) or url.endswith(('.html', '.htm')):
            return url
            
        url_style = self.get_url_style()
        logger.debug(f"Formatting URL '{url}' with style '{url_style}'")
        
        # Handle different URL styles
        if url_style == 'html':
            # Add .html extension
            if url.endswith('/'):
                # For URLs ending with /, use index.html
                return f"{url}index.html"
            else:
                return f"{url}.html"
        elif url_style == 'directory':
            # Ensure URL ends with / for directory style
            if not url.endswith('/'):
                return f"{url}/"
            return url
        else:  # 'clean' style - default
            # For clean URLs, strip trailing slash if present
            if url.endswith('/') and url != '/':
                return url[:-1]
            return url