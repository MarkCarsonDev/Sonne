"""
Configuration management for Sonne.
Supports multiple configuration formats and provides validation.
"""

import os
import json
import yaml
from pathlib import Path
import logging
from typing import Dict, Any, Optional, List, Literal
from enum import Enum

logger = logging.getLogger('sonne')


class MergeStrategy(Enum):
    """Strategy for merging configuration values."""
    REPLACE = 'replace'  # Replace with new value
    EXTEND = 'extend'  # Extend lists, merge dicts
    UNIQUE = 'unique'  # Extend lists with unique values only

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
        'only_used': False,
    },
    'variables': {
        'file': 'sonne_variables.json',
        'preserve_prior': False,
    },
    'security': {
        # WARNING: Enabling embedded Python allows arbitrary code execution in content files
        # Only enable this if you trust all content authors. NEVER enable for user-submitted content.
        # Use data scripts in the scripts/ directory as a safer alternative.
        'allow_embedded_python': False,
        'csp': {
            'enabled': False,
            'directives': {},
        },
    },
    'url_style': {
        'prod': 'clean',
        'dev': 'directory',
    },
    'serve': {
        'host': 'localhost',
        'port': 8000,
    },
    'environment': 'prod',
    'build': {
        'incremental': True,
        'show_progress': True,
        'statistics': True,
    },
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
                    logger.info(f"Found configuration file at {full_path}")
                    return full_path
            
            # Move up one directory
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:  # Reached root
                break
            current_dir = parent_dir
                
        logger.info("No configuration file found, using defaults")
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
        
    def _deep_merge(
        self,
        source: Dict[str, Any],
        destination: Dict[str, Any],
        strategy: MergeStrategy = MergeStrategy.REPLACE,
        list_merge_keys: Optional[List[str]] = None
    ) -> None:
        """Recursively merge source dictionary into destination with configurable strategies.

        Args:
            source: Source dictionary with new values.
            destination: Destination dictionary to update.
            strategy: Default merge strategy for lists.
            list_merge_keys: Keys that should use EXTEND strategy for lists.
        """
        if list_merge_keys is None:
            # Keys where we want to extend lists instead of replacing
            list_merge_keys = ['keywords', 'formats']

        for key, value in source.items():
            if key in destination:
                # Both are dicts - recurse
                if isinstance(destination[key], dict) and isinstance(value, dict):
                    self._deep_merge(value, destination[key], strategy, list_merge_keys)

                # Both are lists - apply strategy
                elif isinstance(destination[key], list) and isinstance(value, list):
                    if key in list_merge_keys or strategy == MergeStrategy.EXTEND:
                        # Extend the list
                        destination[key].extend(value)
                    elif strategy == MergeStrategy.UNIQUE:
                        # Extend with unique values only
                        for item in value:
                            if item not in destination[key]:
                                destination[key].append(item)
                    else:  # REPLACE strategy
                        destination[key] = value

                # Types don't match or not special case - replace
                else:
                    destination[key] = value
            else:
                # Key doesn't exist in destination - just set it
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

    def validate(self) -> List[str]:
        """Validate the configuration and return a list of warnings/errors.

        Returns:
            List of validation messages. Empty list means configuration is valid.
        """
        warnings = []

        # Validate site configuration
        site_config = self.get('site')
        if not site_config:
            warnings.append("Missing 'site' configuration section")
        else:
            if not site_config.get('title'):
                warnings.append("Site title is not set")
            if not site_config.get('base_url'):
                warnings.append("Site base_url is not set")

        # Validate paths
        paths = self.get('paths')
        if not paths:
            warnings.append("Missing 'paths' configuration section")
        else:
            required_paths = ['content', 'output', 'templates']
            for path_key in required_paths:
                if not paths.get(path_key):
                    warnings.append(f"Required path '{path_key}' is not set")

        # Validate image configuration
        images = self.get('images')
        if images:
            formats = images.get('formats', [])
            if formats and not isinstance(formats, list):
                warnings.append("images.formats should be a list")
            sizes = images.get('sizes', [])
            if sizes and not isinstance(sizes, list):
                warnings.append("images.sizes should be a list")
            elif sizes and not all(isinstance(s, int) and s > 0 for s in sizes):
                warnings.append("images.sizes should contain only positive integers")

        # Security warnings
        security = self.get('security', default={})
        if security and security.get('allow_embedded_python'):
            warnings.append("WARNING: Embedded Python execution is enabled. This allows arbitrary code execution from content files. Only enable this if you trust all content authors.")

        # Validate blog configuration if enabled
        blog = self.get('blog')
        if blog and blog.get('enabled'):
            if not blog.get('directory'):
                warnings.append("Blog is enabled but directory is not set")
            if not blog.get('template'):
                warnings.append("Blog is enabled but template is not set")

        return warnings

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

    def generate_csp_header(self) -> Optional[str]:
        """Generate Content Security Policy header if enabled.

        Returns:
            CSP header value or None if disabled.
        """
        csp_config = self.get('security', 'csp')
        if not csp_config or not csp_config.get('enabled'):
            return None

        directives = csp_config.get('directives', {})
        if not directives:
            logger.warning("CSP enabled but no directives configured")
            return None

        # Build CSP header
        policy_parts = []
        for directive, sources in directives.items():
            if isinstance(sources, list):
                sources_str = ' '.join(sources)
                policy_parts.append(f"{directive} {sources_str}")
            else:
                logger.warning(f"CSP directive '{directive}' has invalid format (should be list)")

        if policy_parts:
            return '; '.join(policy_parts)

        return None

    def get_csp_meta_tag(self) -> Optional[str]:
        """Generate CSP meta tag for HTML if enabled.

        Returns:
            HTML meta tag string or None if disabled.
        """
        csp_header = self.generate_csp_header()
        if not csp_header:
            return None

        return f'<meta http-equiv="Content-Security-Policy" content="{csp_header}">'