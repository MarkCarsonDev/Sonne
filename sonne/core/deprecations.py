"""
Deprecation shims for Sonne configuration keys.

All config key renames and retirements go through this module so old site
configs keep working with a warning (and `sonne migrate` can rewrite them).
Add an entry to the matching table and update the schema (mark the old key
deprecated) plus README and CHANGELOG.
"""

import logging
import warnings
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger("sonne")

KeyPath = tuple[str, ...]

# Returned by _pop_key when the key is absent (None is a valid config value).
_MISSING = object()

# (old key path) -> (new key path). The code-facing names are canonical.
DEPRECATED_CONFIG_KEYS: dict[KeyPath, KeyPath] = {
    ("images", "parallel_processing"): ("images", "parallel"),
    ("images", "max_workers"): ("images", "parallel_workers"),
}

# (key path) -> guidance. Keys that no longer exist at all; their presence
# gets a once-per-process warning and the key is dropped from the config.
REMOVED_CONFIG_KEYS: dict[KeyPath, str] = {
    ("security", "allow_embedded_python"): (
        "embedded Python blocks ({p}{#...#}) were removed; use a data script "
        "with sonne_global()/sonne_filter() plus Jinja in content "
        "(content.render_jinja) instead"
    ),
}

# (key path) -> hint. Keys that are still accepted but never did anything;
# they warn once, are dropped, and will be removed in a later release.
NO_EFFECT_CONFIG_KEYS: dict[KeyPath, str] = {
    ("build", "incremental"): "every build is a full build",
    ("build", "show_progress"): "use `sonne build --no-progress` instead",
    ("build", "statistics"): "use `sonne build --perf` for the build report",
    ("security", "csp"): (
        "Sonne never added the policy to pages; send a Content-Security-Policy "
        "header from your web server instead"
    ),
}


@dataclass(frozen=True)
class ConfigChange:
    """One rewrite of a user config: a rename (new_path set) or a removal."""

    path: KeyPath
    new_path: Optional[KeyPath]
    message: str

    @property
    def is_rename(self) -> bool:
        return self.new_path is not None


# Keys already warned about in this process. Deliberately per process, not
# per Config load: `sonne serve --watch` reloads the config on every
# rebuild, and repeating the same warning on each save would bury real
# output. Tests reset this set (see tests/unit/test_deprecations.py).
_warned: set[KeyPath] = set()


def apply_config_deprecations(user_config: dict[str, Any]) -> None:
    """Rewrite deprecated keys in a user config dict, in place, with warnings.

    Must run on the raw user config BEFORE it is merged over defaults, so
    "the user explicitly set the new key" can be detected. Each key warns
    once per process.

    Args:
        user_config: Parsed user configuration (mutated in place).
    """
    for change in migrate_config(user_config):
        _warn_once(change.path, change.message)


def migrate_config(user_config: dict[str, Any]) -> list[ConfigChange]:
    """Apply every rename and removal to a user config dict, in place, silently.

    A renamed key's value moves to the new path only if the new key is not
    already set (an explicit new key wins). Removed and no-effect keys are
    dropped.

    Args:
        user_config: Parsed user configuration (mutated in place).

    Returns:
        The changes made, in table order.
    """
    changes = []
    for old_path, new_path in DEPRECATED_CONFIG_KEYS.items():
        value = _pop_key(user_config, old_path)
        if value is _MISSING:
            continue
        _set_key_unless_present(user_config, new_path, value)
        message = (
            f"Config key '{_dotted(old_path)}' is deprecated; use '{_dotted(new_path)}' instead"
        )
        changes.append(ConfigChange(old_path, new_path, message))

    for removed_path, guidance in REMOVED_CONFIG_KEYS.items():
        if _pop_key(user_config, removed_path) is not _MISSING:
            message = f"Config key '{_dotted(removed_path)}' no longer exists: {guidance}"
            changes.append(ConfigChange(removed_path, None, message))

    for no_effect_path, hint in NO_EFFECT_CONFIG_KEYS.items():
        if _pop_key(user_config, no_effect_path) is not _MISSING:
            message = (
                f"Config key '{_dotted(no_effect_path)}' has no effect and will be removed; {hint}"
            )
            changes.append(ConfigChange(no_effect_path, None, message))
    return changes


def _pop_key(config: dict[str, Any], key_path: KeyPath) -> Any:
    """Remove and return the value at key_path, or _MISSING if absent."""
    section = _parent_section(config, key_path)
    if section is None or key_path[-1] not in section:
        return _MISSING
    return section.pop(key_path[-1])


def _parent_section(config: dict[str, Any], key_path: KeyPath) -> Optional[dict[str, Any]]:
    """The mapping that would hold key_path's last key, or None if there is none."""
    section = config
    for part in key_path[:-1]:
        section = section.get(part) if isinstance(section, dict) else None
        if section is None:
            return None
    return section if isinstance(section, dict) else None


def _set_key_unless_present(config: dict[str, Any], key_path: KeyPath, value: Any) -> None:
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
