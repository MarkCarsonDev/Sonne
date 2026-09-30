"""
Variable management for Sonne.
Handles loading, processing, and substituting variables in templates.
"""

import os
import json
import yaml
import csv
import importlib.util
import sys
import time
from datetime import datetime
from pathlib import Path
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("sonne")

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


DEFAULT_VARIABLE_FILE = "sonne_variables.json"
DATA_FILE_PATTERNS = ["*.json", "*.yaml", "*.yml", "*.csv"]

# Blog variables collected before load_variables() runs; they are carried
# over each reload so data scripts can see posts.
BLOG_VARIABLE_NAMES = ["all_blog_posts", "tags", "categories"]

FALLBACK_SITE_TITLE = "My Sonne Site"

# Returned by _parse_data_file for extensions it cannot read.
_UNSUPPORTED_FORMAT = object()


class VariableManager:
    """Manages variables and their substitution in templates."""

    # Derived state must never persist across builds: it is recomputed from
    # content every build, and stale copies were previously served when the
    # blog was later disabled or posts changed.
    _NEVER_PERSIST = {"all_blog_posts", "tags", "categories", "build_time"}

    def __init__(self, config, base_dir: str):
        """Initialize variable manager.

        Args:
            config: Site configuration.
            base_dir: Base directory of the site. Defaults to the current directory.
        """
        self.config = config
        self.base_dir = base_dir or os.getcwd()
        self.variables = {"global": {}, "site": {}, "page": {}}
        self.stats = None  # Injected by SiteGenerator

        # Provenance tracking: names set by data scripts (the only variables
        # that persist across builds when variables.preserve_prior is on),
        # and script paths already executed this load (prevents double runs).
        self._script_vars = set()
        self._executed_scripts = set()

        # Jinja extensions registered by data scripts via sonne_filter /
        # sonne_global. SiteGenerator hands these to the TemplateProcessor
        # after load_variables().
        self.custom_filters = {}
        self.custom_globals = {}

        var_file = config.get("variables", "file", default=DEFAULT_VARIABLE_FILE)
        self.variable_file = os.path.join(self.base_dir, var_file or DEFAULT_VARIABLE_FILE)
        self.data_dir = self._existing_dir(config.get("paths", "data", default="data"))
        self.scripts_dir = self._existing_dir(config.get("paths", "scripts", default="scripts"))

    def _existing_dir(self, configured_path: Optional[str]) -> Optional[str]:
        """configured_path joined to base_dir if that directory exists, else None."""
        if not configured_path:
            return None
        directory = os.path.join(self.base_dir, configured_path)
        return directory if os.path.exists(directory) else None

    def load_variables(self) -> None:
        """Load all variables from configured sources.

        In order: fresh defaults plus carried-over blog variables, site
        config, the prior variable file (when variables.preserve_prior),
        data files, data scripts, then the footer script.
        """
        self._reset_script_state()
        blog_variables = self._current_blog_variables()
        self.variables = self._fresh_scopes(blog_variables)
        self._add_site_config()
        self._load_prior_variables()
        # Saved variables may hold stale post data (old dates, old URLs).
        self._restore_blog_variables(blog_variables)
        self._load_data_directory()
        self._run_data_scripts_logging_errors()
        self._run_footer_script()
        self._mirror_globals_into_site()

    def _reset_script_state(self) -> None:
        self._script_vars = set()
        self._executed_scripts = set()
        self.custom_filters = {}
        self.custom_globals = {}

    def _current_blog_variables(self) -> Dict[str, Any]:
        """Blog variables already set by BlogProcessor.collect_post_metadata()."""
        global_scope = self.variables.get("global", {})
        return {name: global_scope[name] for name in BLOG_VARIABLE_NAMES if name in global_scope}

    def _fresh_scopes(self, blog_variables: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        now = datetime.now()
        site_scope = {
            "generator": "Sonne",
            "generator_version": self._get_version(),
            "build_time": now.isoformat(),
            "year": now.year,
            # Defaults templates rely on
            "footer": {"custom": None},
            "nav": [],
            "language": "en",
        }
        site_scope.update(blog_variables)
        return {"global": dict(blog_variables), "site": site_scope, "page": {}}

    def _get_version(self) -> str:
        """Get the current version of Sonne (single-sourced in sonne/__init__.py)."""
        import sonne

        return getattr(sonne, "__version__", "unknown")

    def _add_site_config(self) -> None:
        """Expose the site config section in site scope.

        A dict-valued title contributes its 'text' (or a fallback title);
        a footer mapping is merged into the default footer structure.
        """
        site_config = self.config.get("site", default={})
        if not isinstance(site_config, dict):
            return
        site_scope = self.variables["site"]
        for key, value in site_config.items():
            if key == "title" and isinstance(value, dict):
                site_scope[key] = value.get("text", FALLBACK_SITE_TITLE)
            elif key == "footer" and isinstance(value, dict):
                site_scope["footer"].update(value)
            else:
                site_scope[key] = value

    def _load_prior_variables(self) -> None:
        """Load the variable file, only when persistence is explicitly enabled.

        By default every build starts fresh — the variable file otherwise
        becomes a self-perpetuating stale cache.
        """
        preserve_prior = self.config.get("variables", "preserve_prior", default=False)
        if not preserve_prior or not os.path.exists(self.variable_file):
            return
        try:
            self._load_variable_file()
            logger.debug(f"Loaded variables from {self.variable_file}")
        except Exception as e:
            logger.error(f"Error loading variables from {self.variable_file}: {e}")

    def _load_variable_file(self) -> None:
        """Load Sonne's own variable file into global scope.

        Unwraps the legacy ``{"var": {"data": value}}`` format that save()
        writes. Only valid for this file — user data files may legitimately
        contain a "data" key and must never be unwrapped.
        """
        data = _parse_data_file(self.variable_file)
        if data is _UNSUPPORTED_FORMAT:
            return
        if _is_legacy_wrapped(data):
            for key, wrapped in data.items():
                self.variables["global"][key] = wrapped.get("data")
        else:
            self._store_data(data, Path(self.variable_file).stem, "global")

    def _restore_blog_variables(self, blog_variables: Dict[str, Any]) -> None:
        self.variables["global"].update(blog_variables)
        self.variables["site"].update(blog_variables)

    def _load_data_directory(self) -> None:
        if not self.data_dir:
            return
        for pattern in DATA_FILE_PATTERNS:
            for file_path in Path(self.data_dir).glob(f"**/{pattern}"):
                try:
                    self._load_data_file(str(file_path), "site")
                except Exception as e:
                    logger.error(f"Error loading data from {file_path}: {e}")
        logger.debug(f"Loaded data from {self.data_dir}")

    def _load_data_file(self, file_path: str, scope: str) -> None:
        """Load one user data file into scope.

        Args:
            file_path: Path to a JSON, YAML or CSV file.
            scope: Variable scope ('global', 'site', or 'page').
        """
        data = _parse_data_file(file_path)
        if data is not _UNSUPPORTED_FORMAT:
            self._store_data(data, Path(file_path).stem, scope)

    def _store_data(self, data: Any, name: str, scope: str) -> None:
        """Merge a mapping into scope; store anything else (e.g. CSV rows) under name."""
        if isinstance(data, dict):
            self.variables[scope].update(data)
        else:
            self.variables[scope][name] = data

    def data_script_paths(self) -> List[Path]:
        """Data scripts that load_variables() runs, in run order.

        Every ``*.py`` directly in the scripts directory except names
        starting with an underscore.
        """
        if not self.scripts_dir:
            return []
        return [
            script_path
            for script_path in Path(self.scripts_dir).glob("*.py")
            if not script_path.name.startswith("_")
        ]

    def _run_data_scripts_logging_errors(self) -> None:
        if not self.scripts_dir:
            return
        try:
            self._run_data_scripts()
            logger.debug(f"Scripts complete. Globals: {list(self.variables['global'].keys())}")
        except Exception as e:
            logger.error(f"Error running data scripts from {self.scripts_dir}: {e}")

    def _run_data_scripts(self) -> None:
        """Run each data script; a failing script is logged and skipped."""
        for script_path in self.data_script_paths():
            logger.info(f"  Script: {script_path.name}")
            try:
                self._run_timed_script(script_path)
            except Exception as e:
                logger.error(
                    f"Error running script {script_path}: {e}",
                    exc_info=logger.isEnabledFor(logging.DEBUG),
                )

    def _run_timed_script(self, script_path: Path) -> None:
        started = time.perf_counter()
        self._execute_script(script_path, f"sonne_script_{script_path.stem}")
        if self.stats:
            self.stats.record_script(script_path.name, time.perf_counter() - started)
        logger.debug(f"After {script_path.name}: globals={list(self.variables['global'].keys())}")

    def _execute_script(self, script_path: Path, module_name: str) -> None:
        """Run a trusted site script as a module with the Sonne hooks injected.

        Scripts are trusted by design: they run with full process privileges.
        """
        self._executed_scripts.add(str(script_path.resolve()))
        spec = importlib.util.spec_from_file_location(module_name, script_path)
        module = importlib.util.module_from_spec(spec)
        for hook_name, hook in self._script_hooks().items():
            setattr(module, hook_name, hook)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

    def _script_hooks(self) -> Dict[str, Callable]:
        """The functions every site script can call without importing anything."""

        def sonne_var(name, value):
            self.variables["global"][name] = value
            self.variables["site"][name] = value
            self._script_vars.add(name)
            logger.debug(f"Variable set: {name}")

        def get_post(slug=None, tag=None):
            """Get a blog post by slug, or the first post with a tag; None if not found."""
            posts = self.variables.get("global", {}).get("all_blog_posts", [])
            if not posts:
                posts = self.variables.get("site", {}).get("all_blog_posts", [])
            return _find_post(posts, slug, tag)

        # Jinja extension hooks: scripts can register real Python callables
        # usable from every template and (with content.render_jinja) every
        # content file.
        def sonne_filter(name, fn):
            self.custom_filters[name] = fn
            logger.debug(f"Jinja filter registered by script: {name}")

        def sonne_global(name, value):
            self.custom_globals[name] = value
            logger.debug(f"Jinja global registered by script: {name}")

        return {
            "sonne_var": sonne_var,
            "get_post": get_post,
            "sonne_filter": sonne_filter,
            "sonne_global": sonne_global,
        }

    def _run_footer_script(self) -> None:
        """Run the first footer.py that works, and mark its footer_custom HTML-safe.

        Candidates in order: <site>/data/footer.py, <paths.data>/footer.py,
        <site>/scripts/footer.py. One already run as a data script counts as
        found without running again; one that fails falls through to the next.
        """
        for footer_path in self._footer_script_candidates():
            if not os.path.exists(footer_path):
                continue
            if str(Path(footer_path).resolve()) in self._executed_scripts:
                self._mark_footer_html_safe()
                return
            try:
                self._execute_script(Path(footer_path), "sonne_script_footer")
                self._mark_footer_html_safe()
                logger.debug(f"Loaded footer script: {footer_path}")
                return
            except Exception as e:
                logger.error(f"Error running footer script at {footer_path}: {e}")
        logger.debug("No footer.py script found")

    def _footer_script_candidates(self) -> List[str]:
        candidates = [os.path.join(self.base_dir, "data", "footer.py")]
        data_path = self.config.get("paths", "data")
        if data_path:
            candidates.append(os.path.join(data_path, "footer.py"))
        candidates.append(os.path.join(self.base_dir, "scripts", "footer.py"))
        return candidates

    def _mark_footer_html_safe(self) -> None:
        """footer_custom is trusted script HTML: wrap it in Markup everywhere it lives."""
        if "footer_custom" not in self.variables.get("global", {}):
            return
        footer_content = Markup(self.variables["global"]["footer_custom"])
        self.variables["global"]["footer_custom"] = footer_content
        self.variables["site"]["footer_custom"] = footer_content
        self.variables["site"]["footer"]["custom"] = footer_content

    def _mirror_globals_into_site(self) -> None:
        """Copy every global variable into site scope unless site already has it."""
        for key, value in self.variables.get("global", {}).items():
            if key not in self.variables.get("site", {}):
                self.variables["site"][key] = value

    def render_scopes(self) -> Dict[str, Dict[str, Any]]:
        """Variable scopes for rendering one content page.

        Globals set since load_variables() (e.g. by the blog processor) are
        mirrored into site scope first; the page scope starts empty.

        Returns:
            Mapping with 'global', 'site' and 'page' scopes.
        """
        self._mirror_globals_into_site()
        return {
            "global": self.variables.get("global", {}),
            "site": self.variables.get("site", {}),
            "page": {},
        }

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

        for current_scope in ["page", "site", "global"]:
            if key in self.variables.get(current_scope, {}):
                return self.variables[current_scope][key]

        return default

    def get_all(self) -> Dict[str, Any]:
        """Get all variables merged into a single dictionary.

        Returns:
            Dictionary containing all variables; page beats site beats global.
        """
        result = {}
        result.update(self.variables.get("global", {}))
        result.update(self.variables.get("site", {}))
        result.update(self.variables.get("page", {}))
        return result

    def set(self, key: str, value: Any, scope: str = "site") -> None:
        """Set a variable value in the specified scope.

        ``footer_custom`` containing HTML is marked safe, and a global
        ``footer_custom`` is also mirrored to ``site.footer.custom``.

        Args:
            key: Variable name.
            value: Variable value.
            scope: Variable scope ('global', 'site', or 'page').
        """
        if scope not in self.variables:
            self.variables[scope] = {}

        if key == "footer_custom" and _looks_like_html(value):
            value = Markup(value)

        logger.debug(f"Setting variable {key} in scope {scope}")
        self.variables[scope][key] = value

        if key == "footer_custom" and scope == "global":
            self.variables.setdefault("site", {}).setdefault("footer", {})["custom"] = value

    def set_page_variables(self, variables: Dict[str, Any]) -> None:
        """Set page-level variables.

        Args:
            variables: Dictionary of page variables.
        """
        self.variables["page"] = variables

    def save(self) -> None:
        """Persist script-produced variables to the variable file.

        Does nothing unless ``variables.preserve_prior`` is enabled. Only
        variables set via ``sonne_var`` in data scripts are written — derived
        state (posts, taxonomies, generator info) is always excluded.
        """
        if not self.config.get("variables", "preserve_prior", default=False):
            logger.debug("variables.preserve_prior disabled; not saving variable file")
            return

        try:
            self._write_variable_file()
            logger.debug(f"Saved variables to {self.variable_file}")
        except Exception as e:
            logger.error(f"Error saving variables: {e}")

    def _write_variable_file(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.variable_file)), exist_ok=True)
        # Keep the {"var": {"data": ...}} format for backward compatibility
        saved_at = datetime.now().isoformat()
        wrapped = {
            key: {"data": str(value) if hasattr(value, "__html__") else value, "datetime": saved_at}
            for key, value in self.variables.get("global", {}).items()
            if self._is_persistable(key)
        }
        with open(self.variable_file, "w", encoding="utf-8") as f:
            json.dump(wrapped, f, indent=2, default=str)

    def _is_persistable(self, key: str) -> bool:
        return (
            key in self._script_vars
            and key not in self._NEVER_PERSIST
            and not key.startswith("generator")
        )


def _parse_data_file(file_path: str) -> Any:
    """Parse a JSON, YAML or CSV file (CSV as a list of row dicts).

    Returns:
        The parsed data, or _UNSUPPORTED_FORMAT (after a warning) for any
        other extension.
    """
    ext = Path(file_path).suffix.lower()
    with open(file_path, "r", encoding="utf-8") as f:
        if ext == ".json":
            return json.load(f)
        if ext in (".yaml", ".yml"):
            return yaml.safe_load(f)
        if ext == ".csv":
            return list(csv.DictReader(f))
    logger.warning(f"Unsupported data file format: {ext}")
    return _UNSUPPORTED_FORMAT


def _is_legacy_wrapped(data: Any) -> bool:
    """Whether data is the non-empty {"var": {"data": value, ...}} save format."""
    return (
        isinstance(data, dict)
        and bool(data)
        and all(isinstance(value, dict) and "data" in value for value in data.values())
    )


def _find_post(posts: List[Dict], slug: Optional[str], tag: Optional[str]) -> Optional[Dict]:
    """The post with this slug, else (when no slug is given) the first with this tag."""
    if slug:
        return next((post for post in posts if post.get("slug") == slug), None)
    if tag:
        return next((post for post in posts if tag in post.get("tags", [])), None)
    return None


def _looks_like_html(value: Any) -> bool:
    return isinstance(value, str) and "<" in value and ">" in value
