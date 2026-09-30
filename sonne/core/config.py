"""
Configuration management for Sonne.
Supports multiple configuration formats and provides validation.
"""

import copy
import os
import json
import yaml
from pathlib import Path
import logging
from typing import Dict, Any, Optional, List

from sonne.core.deprecations import apply_config_deprecations
from sonne.utils.path_utils import CONFIG_FILENAMES

logger = logging.getLogger("sonne")

# Default configuration settings
DEFAULT_CONFIG = {
    "site": {
        "title": "My Sonne Site",
        "base_url": "http://localhost",
        "description": "A site built with Sonne",
        "author": "Sonne User",
        "keywords": [],
        "language": "en",
    },
    "paths": {
        "content": "content",
        "output": "output",
        "static": "static",
        "templates": "templates",
        "data": "data",
        "cache": ".cache",
        "scripts": "scripts",
    },
    "blog": {
        "enabled": True,
        "directory": "blog",
        "template": "blog_post.html",
        "list_template": "blog_list.html",
        "posts_per_page": 10,
        "excerpt_length": 200,
        "url_pattern": "{year}/{month}/{day}/{slug}",
        "include_drafts": False,
        "taxonomies": {
            "tags": {
                "enabled": True,
                "template": "tag.html",
                "list_template": "tags.html",
            },
            "categories": {
                "enabled": True,
                "template": "category.html",
                "list_template": "categories.html",
            },
        },
    },
    "images": {
        "dither": True,
        "optimize": True,
        "formats": ["webp", "png"],
        "sizes": [1200, 800, 400],
        "lazy_loading": True,
        "only_used": False,
        "parallel": True,
        "parallel_workers": 0,  # 0 = auto (min(4, cpu_count))
    },
    "variables": {
        "file": "sonne_variables.json",
        "preserve_prior": False,
    },
    "content": {
        # Render content files (markdown/HTML pages and posts) through Jinja
        # before markdown conversion. Off by default so literal {{ }} in
        # content (code samples) can never break by surprise; a per-file
        # front matter key `jinja: true|false` overrides this either way.
        "render_jinja": False,
    },
    "security": {
        "csp": {
            "enabled": False,
            "directives": {},
        },
    },
    "url_style": {
        "prod": "clean",
        "dev": "directory",
    },
    "serve": {
        "host": "localhost",
        "port": 8000,
    },
    "environment": "prod",
    "build": {
        "incremental": True,
        "show_progress": True,
        "statistics": True,
        "show_page_size": False,
    },
}


YAML_EXTENSIONS = (".yaml", ".yml")
JSON_EXTENSIONS = (".json", ".config")

# How many directories config discovery examines: the base directory and
# its ancestors.
CONFIG_SEARCH_DEPTH = 3

DEFAULT_URL_STYLE = "clean"
MAX_PORT = 65535


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
        """Search the base directory, then its parents, for a config file.

        Returns:
            Path to the first config file found, or None.
        """
        start_dir = os.path.abspath(self.base_dir)
        for level, directory in enumerate(_self_and_ancestors(start_dir, CONFIG_SEARCH_DEPTH)):
            config_path = _config_file_in(directory)
            if not config_path:
                continue
            if level == 0:
                logger.info(f"Found configuration file at {config_path}")
            else:
                # Adopting a config from a parent directory is easy to do by
                # accident (e.g. running from a subfolder of another Sonne
                # project) — be loud about it.
                logger.warning(
                    f"Using configuration from a parent directory: "
                    f"{config_path} (searched from {start_dir})"
                )
            return config_path

        logger.info("No configuration file found, using defaults")
        return None

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file and merge with defaults.

        An unreadable or unsupported file is logged and the defaults are used.

        Returns:
            Complete configuration dictionary.
        """
        config = copy.deepcopy(DEFAULT_CONFIG)
        if not self.config_path:
            return config

        try:
            self._merge_user_config(config)
        except Exception as e:
            logger.error(f"Error loading configuration file: {e}")
            logger.warning("Using default configuration")
        return config

    def _merge_user_config(self, config: Dict[str, Any]) -> None:
        ext = Path(self.config_path).suffix.lower()
        if ext not in YAML_EXTENSIONS + JSON_EXTENSIONS:
            logger.warning(f"Unsupported config format: {ext}")
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) if ext in YAML_EXTENSIONS else json.load(f)

        if isinstance(user_config, dict):
            apply_config_deprecations(user_config)
            _deep_merge(user_config, config)
        elif user_config is not None:
            logger.warning(f"Configuration file {self.config_path} is not a mapping; ignoring it")
        logger.debug(f"Loaded configuration from {self.config_path}")

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
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current

    def set(self, *keys, value=None):
        """Set configuration value using dot notation or nested keys.

        Intermediate keys that are missing or not mappings become empty dicts.

        Args:
            *keys: Key path to the configuration value to set.
            value: Value to set.
        """
        if not keys:
            return

        current = self.config
        for key in keys[:-1]:
            if not isinstance(current.get(key), dict):
                current[key] = {}
            current = current[key]
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
            self._write(save_path)
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    def _write(self, save_path: str) -> None:
        ext = Path(save_path).suffix.lower()
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)

        with open(save_path, "w", encoding="utf-8") as f:
            if ext in YAML_EXTENSIONS:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
            elif ext in JSON_EXTENSIONS:
                json.dump(self.config, f, indent=2)
            else:
                logger.warning(f"Unsupported config format for saving: {ext}")
                return

        logger.debug(f"Configuration saved to {save_path}")

    def normalize_paths(self, base_dir: str) -> Dict[str, str]:
        """Normalize all path configurations to absolute paths.

        Output and cache directories are created if missing.

        Args:
            base_dir: Base directory to resolve relative paths against.

        Returns:
            Dictionary of normalized paths (keys with empty values omitted).
        """
        paths = {}
        for key, value in self.get("paths").items():
            if not value:
                continue
            full_path = (
                value if os.path.isabs(value) else os.path.abspath(os.path.join(base_dir, value))
            )
            if key in ["output", "cache"]:
                os.makedirs(full_path, exist_ok=True)
            paths[key] = full_path
        return paths

    def validate(self) -> List[str]:
        """Validate the configuration and return a list of warnings/errors.

        Returns:
            List of validation messages. Empty list means configuration is valid.
        """
        return (
            self._site_problems()
            + self._path_problems()
            + self._image_problems()
            + self._blog_problems()
            + self._serve_problems()
            + self._environment_problems()
        )

    def _site_problems(self) -> List[str]:
        site_config = self.get("site")
        if not site_config:
            return ["Missing 'site' configuration section"]
        problems = []
        if not site_config.get("title"):
            problems.append("Site title is not set")
        if not site_config.get("base_url"):
            problems.append("Site base_url is not set")
        return problems

    def _path_problems(self) -> List[str]:
        paths = self.get("paths")
        if not paths:
            return ["Missing 'paths' configuration section"]
        return [
            f"Required path '{path_key}' is not set"
            for path_key in ["content", "output", "templates"]
            if not paths.get(path_key)
        ]

    def _image_problems(self) -> List[str]:
        images = self.get("images")
        if not images:
            return []
        problems = []
        formats = images.get("formats", [])
        if formats and not isinstance(formats, list):
            problems.append("images.formats should be a list")
        sizes = images.get("sizes", [])
        if sizes and not isinstance(sizes, list):
            problems.append("images.sizes should be a list")
        elif sizes and not all(isinstance(size, int) and size > 0 for size in sizes):
            problems.append("images.sizes should contain only positive integers")
        return problems

    def _blog_problems(self) -> List[str]:
        blog = self.get("blog")
        if not blog or not blog.get("enabled"):
            return []
        problems = []
        if not blog.get("directory"):
            problems.append("Blog is enabled but directory is not set")
        if not blog.get("template"):
            problems.append("Blog is enabled but template is not set")
        posts_per_page = blog.get("posts_per_page", 10)
        if not _is_strict_int(posts_per_page) or posts_per_page < 1:
            problems.append("blog.posts_per_page must be a positive integer")
        return problems

    def _serve_problems(self) -> List[str]:
        port = self.get("serve", "port")
        if port is not None and (not _is_strict_int(port) or not 0 <= port <= MAX_PORT):
            return [f"serve.port must be an integer between 0 and {MAX_PORT}"]
        return []

    def _environment_problems(self) -> List[str]:
        environment = self.get("environment", default="prod")
        url_style = self.get("url_style")
        if isinstance(url_style, dict) and environment not in url_style:
            return [
                f"environment '{environment}' has no url_style entry; "
                f"the '{DEFAULT_URL_STYLE}' URL style will be used"
            ]
        return []

    def get_url_style(self) -> str:
        """Get the URL style based on configuration and environment.

        url_style may be a single style or a mapping of environment to style;
        an environment missing from the mapping, or no setting, means 'clean'.

        Returns:
            One of 'clean', 'html', or 'directory'.
        """
        url_style = self.get("url_style")
        environment = self.get("environment", default="prod")
        logger.debug(f"URL style from config: {url_style}, Environment: {environment}")

        if isinstance(url_style, str):
            return url_style
        if isinstance(url_style, dict):
            style = url_style.get(environment, DEFAULT_URL_STYLE)
            logger.debug(f"Using URL style '{style}' for environment '{environment}'")
            return style

        logger.debug("Using default URL style 'clean'")
        return DEFAULT_URL_STYLE

    def format_url(self, url: str) -> str:
        """Format a URL based on the current URL style configuration.

        External URLs and URLs already ending in .html/.htm are returned
        unchanged. 'html' appends .html (index.html after a trailing slash),
        'directory' ensures a trailing slash, 'clean' strips one (except '/').

        Args:
            url: The URL to format (e.g. '/about')

        Returns:
            Formatted URL according to the current URL style.
        """
        if url.startswith(("http://", "https://")) or url.endswith((".html", ".htm")):
            return url

        url_style = self.get_url_style()
        logger.debug(f"Formatting URL '{url}' with style '{url_style}'")

        if url_style == "html":
            return f"{url}index.html" if url.endswith("/") else f"{url}.html"
        if url_style == "directory":
            return url if url.endswith("/") else f"{url}/"
        if url.endswith("/") and url != "/":
            return url[:-1]
        return url

    def generate_csp_header(self) -> Optional[str]:
        """Generate Content Security Policy header if enabled.

        Directives whose sources are not a list are skipped with a warning.

        Returns:
            CSP header value, or None if disabled or no valid directives.
        """
        csp_config = self.get("security", "csp")
        if not csp_config or not csp_config.get("enabled"):
            return None

        directives = csp_config.get("directives", {})
        if not directives:
            logger.warning("CSP enabled but no directives configured")
            return None

        policy_parts = []
        for directive, sources in directives.items():
            if isinstance(sources, list):
                policy_parts.append(f"{directive} {' '.join(sources)}")
            else:
                logger.warning(f"CSP directive '{directive}' has invalid format (should be list)")
        return "; ".join(policy_parts) or None

    def get_csp_meta_tag(self) -> Optional[str]:
        """Generate CSP meta tag for HTML if enabled.

        Returns:
            HTML meta tag string or None if disabled.
        """
        csp_header = self.generate_csp_header()
        if not csp_header:
            return None
        return f'<meta http-equiv="Content-Security-Policy" content="{csp_header}">'


def _self_and_ancestors(directory: str, depth: int) -> List[str]:
    """directory followed by up to depth-1 of its ancestors (stopping at the root)."""
    directories = [directory]
    while len(directories) < depth:
        parent = os.path.dirname(directories[-1])
        if parent == directories[-1]:
            break
        directories.append(parent)
    return directories


def _config_file_in(directory: str) -> Optional[str]:
    """The first recognized config file in directory, in discovery order."""
    for filename in CONFIG_FILENAMES:
        candidate = os.path.join(directory, filename)
        if os.path.exists(candidate):
            return candidate
    return None


def _deep_merge(source: Dict[str, Any], destination: Dict[str, Any]) -> None:
    """Recursively merge source dictionary into destination.

    Nested dicts are merged; lists and scalars from source replace the
    destination value outright (a user setting `images.formats: [png]`
    means exactly that list, not an extension of the default).

    Args:
        source: Source dictionary with new values.
        destination: Destination dictionary to update.
    """
    for key, value in source.items():
        if key in destination and isinstance(destination[key], dict) and isinstance(value, dict):
            _deep_merge(value, destination[key])
        else:
            destination[key] = value


def _is_strict_int(value: Any) -> bool:
    """An int that is not a bool (YAML `true` would otherwise pass as 1)."""
    return isinstance(value, int) and not isinstance(value, bool)
