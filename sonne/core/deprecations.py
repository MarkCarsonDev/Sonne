"""
Deprecation shims for Sonne configuration keys.

All config key renames go through this module so old site configs keep
working with a warning. Add an entry to DEPRECATED_CONFIG_KEYS and update
the schema (mark the old key deprecated) plus README and CHANGELOG.
"""

import logging
import warnings
from typing import Any, Dict

logger = logging.getLogger("sonne")

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

    Args:
        user_config: Parsed user configuration (mutated in place).
    """
    for old_path, new_path in DEPRECATED_CONFIG_KEYS.items():
        section = user_config
        for part in old_path[:-1]:
            section = section.get(part) if isinstance(section, dict) else None
            if section is None:
                break
        if not isinstance(section, dict) or old_path[-1] not in section:
            continue

        value = section.pop(old_path[-1])

        target = user_config
        for part in new_path[:-1]:
            target = target.setdefault(part, {})
        if new_path[-1] not in target:
            target[new_path[-1]] = value

        if old_path not in _warned:
            _warned.add(old_path)
            message = (
                f"Config key '{'.'.join(old_path)}' is deprecated; "
                f"use '{'.'.join(new_path)}' instead"
            )
            logger.warning(message)
            warnings.warn(message, DeprecationWarning, stacklevel=2)

    for removed_path, guidance in REMOVED_CONFIG_KEYS.items():
        section = user_config
        for part in removed_path[:-1]:
            section = section.get(part) if isinstance(section, dict) else None
            if section is None:
                break
        if not isinstance(section, dict) or removed_path[-1] not in section:
            continue

        section.pop(removed_path[-1])

        if removed_path not in _warned:
            _warned.add(removed_path)
            message = f"Config key '{'.'.join(removed_path)}' no longer exists: {guidance}"
            logger.warning(message)
            warnings.warn(message, DeprecationWarning, stacklevel=2)
