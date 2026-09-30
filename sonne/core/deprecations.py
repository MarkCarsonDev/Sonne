"""
Deprecation shims for Sonne configuration keys.

All config key renames go through this module so old site configs keep
working with a warning. Add an entry to DEPRECATED_CONFIG_KEYS and update
the schema (mark the old key deprecated) plus README and CHANGELOG.
"""

import logging
import warnings
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("sonne")

KeyPath = Tuple[str, ...]

# Returned by _pop_key when the key is absent (None is a valid config value).
_MISSING = object()

# (old key path) -> (new key path). The code-facing names are canonical.
DEPRECATED_CONFIG_KEYS = {
    ("images", "parallel_processing"): ("images", "parallel"),
    ("images", "max_workers"): ("images", "parallel_workers"),
}

# (key path) -> guidance. Keys that no longer exist at all; their presence
# gets a once-per-process warning and the key is dropped from the config.
REMOVED_CONFIG_KEYS = {
    ("security", "allow_embedded_python"): (
        "embedded Python blocks ({p}{#...#}) were removed; use a data script "
        "with sonne_global()/sonne_filter() plus Jinja in content "
        "(content.render_jinja) instead"
    ),
}

# Keys we have warned about already (once per process, not per Config load).
_warned = set()


def apply_config_deprecations(user_config: Dict[str, Any]) -> None:
    """Rewrite deprecated keys in a user config dict, in place.

    Must run on the raw user config BEFORE it is merged over defaults, so
    "the user explicitly set the new key" can be detected. The old key's
    value moves to the new path only if the new key is not already set.
    Removed keys are dropped. Each key warns once per process.

    Args:
        user_config: Parsed user configuration (mutated in place).
    """
    for old_path, new_path in DEPRECATED_CONFIG_KEYS.items():
        value = _pop_key(user_config, old_path)
        if value is _MISSING:
            continue
        _set_key_unless_present(user_config, new_path, value)
        _warn_once(
            old_path,
            f"Config key '{_dotted(old_path)}' is deprecated; use '{_dotted(new_path)}' instead",
        )

    for removed_path, guidance in REMOVED_CONFIG_KEYS.items():
        if _pop_key(user_config, removed_path) is not _MISSING:
            _warn_once(
                removed_path, f"Config key '{_dotted(removed_path)}' no longer exists: {guidance}"
            )


def _pop_key(config: Dict[str, Any], key_path: KeyPath) -> Any:
    """Remove and return the value at key_path, or _MISSING if absent."""
    section = _parent_section(config, key_path)
    if section is None or key_path[-1] not in section:
        return _MISSING
    return section.pop(key_path[-1])


def _parent_section(config: Dict[str, Any], key_path: KeyPath) -> Optional[Dict[str, Any]]:
    """The mapping that would hold key_path's last key, or None if there is none."""
    section = config
    for part in key_path[:-1]:
        section = section.get(part) if isinstance(section, dict) else None
        if section is None:
            return None
    return section if isinstance(section, dict) else None


def _set_key_unless_present(config: Dict[str, Any], key_path: KeyPath, value: Any) -> None:
    section = config
    for part in key_path[:-1]:
        section = section.setdefault(part, {})
    section.setdefault(key_path[-1], value)


def _warn_once(key_path: KeyPath, message: str) -> None:
    if key_path in _warned:
        return
    _warned.add(key_path)
    logger.warning(message)
    # stacklevel 3: attribute the warning to apply_config_deprecations' caller
    warnings.warn(message, DeprecationWarning, stacklevel=3)


def _dotted(key_path: KeyPath) -> str:
    return ".".join(key_path)
