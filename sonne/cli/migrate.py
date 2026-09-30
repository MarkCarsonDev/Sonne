"""
`sonne migrate`: rewrite a site config to drop deprecated and no-effect keys.

The rules come from sonne.core.deprecations (the same tables that make old
keys keep working at build time). YAML files are edited line by line so
comments and layout survive; the edit is only used if re-parsing it gives
exactly the migrated config. Anything the line editor cannot handle (e.g.
flow-style mappings) falls back to re-serializing the whole file, which
loses comments, and the plan says so.
"""

import copy
import difflib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

from sonne.core.config import JSON_EXTENSIONS, YAML_EXTENSIONS
from sonne.core.deprecations import (
    NO_EFFECT_CONFIG_KEYS,
    REMOVED_CONFIG_KEYS,
    ConfigChange,
    KeyPath,
    migrate_config,
)

# "key:" at the start of a YAML line, key optionally quoted.
YAML_KEY_LINE = re.compile(
    r"""^(?P<indent>[ ]*)(?P<quote>["']?)(?P<key>[^"'#:\s][^"'#:]*?)(?P=quote)[ ]*:(?:[ ]|$)"""
)
BLOCK_SCALAR_VALUE = re.compile(r":[ ]*[|>][-+0-9]*[ ]*(#.*)?$")


@dataclass
class MigrationPlan:
    """What `sonne migrate` would do to one config file."""

    config_path: Path
    changes: list[ConfigChange]
    original_text: str
    migrated_text: str
    # False when the whole file was re-serialized (YAML comments are lost;
    # JSON has none, but its formatting is normalized).
    edited_in_place: bool
    newline: str = "\n"  # the file's own line ending, kept on write

    @property
    def needed(self) -> bool:
        return bool(self.changes)

    @property
    def is_json(self) -> bool:
        return self.config_path.suffix.lower() in JSON_EXTENSIONS

    def descriptions(self) -> list[str]:
        """One line per change, e.g. "rename images.max_workers -> images.parallel_workers"."""
        original = _parse(self.original_text, is_yaml=not self.is_json)
        return [_describe(change, original) for change in self.changes]

    def diff(self) -> str:
        name = self.config_path.name
        return "".join(
            difflib.unified_diff(
                self.original_text.splitlines(keepends=True),
                self.migrated_text.splitlines(keepends=True),
                fromfile=f"{name} (current)",
                tofile=f"{name} (migrated)",
            )
        )


def plan_migration(config_path: Path) -> MigrationPlan:
    """Work out the migrated text of a config file without writing anything.

    Args:
        config_path: A YAML (.yaml/.yml) or JSON (.json/.config) config file.

    Returns:
        The plan; plan.needed is False when there is nothing to change.

    Raises:
        ValueError: For an unsupported extension or a file that is not a mapping.
    """
    ext = config_path.suffix.lower()
    if ext not in YAML_EXTENSIONS + JSON_EXTENSIONS:
        raise ValueError(f"Unsupported config format: {config_path.name}")
    raw = config_path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    original_text = raw.decode("utf-8").replace("\r\n", "\n")
    is_yaml = ext in YAML_EXTENSIONS
    parsed = _parse(original_text, is_yaml)
    if not isinstance(parsed, dict):
        raise ValueError(f"{config_path.name} is not a mapping of settings")

    migrated = copy.deepcopy(parsed)
    changes = migrate_config(migrated)
    _prune_emptied_sections(migrated, changes)
    if not changes:
        return MigrationPlan(config_path, [], original_text, original_text, True, newline)
    if not is_yaml:
        text = json.dumps(migrated, indent=2, ensure_ascii=False) + "\n"
        return MigrationPlan(config_path, changes, original_text, text, False, newline)

    edited = _edit_yaml_text(original_text, parsed, changes, migrated)
    if edited is not None:
        return MigrationPlan(config_path, changes, original_text, edited, True, newline)
    dumped = yaml.safe_dump(migrated, sort_keys=False, default_flow_style=False, allow_unicode=True)
    return MigrationPlan(config_path, changes, original_text, dumped, False, newline)


def write_migration(plan: MigrationPlan) -> Path:
    """Back up the config file, then write the migrated text.

    Returns:
        The backup path: <name>.bak, or <name>.bak.1, .bak.2, ... so an
        existing backup is never overwritten.
    """
    backup = plan.config_path.with_name(plan.config_path.name + ".bak")
    counter = 1
    while backup.exists():
        backup = plan.config_path.with_name(f"{plan.config_path.name}.bak.{counter}")
        counter += 1
    shutil.copy2(plan.config_path, backup)  # byte-for-byte
    with open(plan.config_path, "w", encoding="utf-8", newline=plan.newline) as f:
        f.write(plan.migrated_text)
    return backup


def _parse(text: str, is_yaml: bool) -> Any:
    return (yaml.safe_load(text) if is_yaml else json.loads(text)) or {}


def _describe(change: ConfigChange, original: dict[str, Any]) -> str:
    old = ".".join(change.path)
    if change.path in NO_EFFECT_CONFIG_KEYS:
        return f"remove {old} (has no effect): {NO_EFFECT_CONFIG_KEYS[change.path]}"
    if change.path in REMOVED_CONFIG_KEYS:
        return f"remove {old} (no longer exists): {REMOVED_CONFIG_KEYS[change.path]}"
    if change.new_path is None:
        return f"remove {old}"
    new = ".".join(change.new_path)
    if _exists(original, change.new_path):
        return f"remove {old} ({new} is already set and takes precedence)"
    return f"rename {old} -> {new}"


def _prune_emptied_sections(config: dict[str, Any], changes: list[ConfigChange]) -> None:
    """Drop sections that only held migrated keys (build: {} after removing build.statistics)."""
    for change in changes:
        for depth in range(len(change.path) - 1, 0, -1):
            parent = _section(config, change.path[: depth - 1])
            key = change.path[depth - 1]
            if isinstance(parent, dict) and parent.get(key) == {}:
                del parent[key]


def _section(config: dict[str, Any], path: KeyPath) -> Optional[dict[str, Any]]:
    node: Any = config
    for part in path:
        node = node.get(part) if isinstance(node, dict) else None
    return node if isinstance(node, dict) else None


# --- Comment-preserving YAML editing -------------------------------------


@dataclass
class _KeyLine:
    path: KeyPath
    index: int
    indent: int


def _edit_yaml_text(
    text: str, original: dict[str, Any], changes: list[ConfigChange], expected: dict[str, Any]
) -> Optional[str]:
    """Apply changes to YAML text line by line; None if that cannot be done faithfully."""
    lines = text.splitlines(keepends=True)
    for change in changes:
        key_line = _find_key_line(lines, change.path)
        if key_line is None:
            return None
        if change.new_path is None or _exists(original, change.new_path):
            # Removal, or a rename whose new key is already set (the new key wins).
            lines = _without_block(lines, key_line)
        elif change.new_path[:-1] == change.path[:-1]:
            lines[key_line.index] = _renamed_key(
                lines[key_line.index], change.path[-1], change.new_path[-1]
            )
        else:
            return None  # a move to another section; leave it to the full rewrite
        lines = _without_empty_parents(lines, change.path[:-1])
    edited = "".join(lines)
    try:
        reparsed = yaml.safe_load(edited) or {}
    except yaml.YAMLError:
        return None
    return edited if reparsed == expected else None


def _key_lines(lines: list[str]) -> list[_KeyLine]:
    """Every mapping key line with its full key path (not inside lists or block scalars)."""
    found: list[_KeyLine] = []
    stack: list[tuple[int, str]] = []
    skip_deeper_than: Optional[int] = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if skip_deeper_than is not None:
            if indent > skip_deeper_than:
                continue
            skip_deeper_than = None
        if stripped.startswith("- ") or stripped == "-":
            skip_deeper_than = indent  # list items: their keys are not config paths
            continue
        match = YAML_KEY_LINE.match(line)
        if not match:
            continue
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, match.group("key")))
        found.append(_KeyLine(tuple(key for _, key in stack), index, indent))
        if BLOCK_SCALAR_VALUE.search(line.rstrip("\r\n")):
            skip_deeper_than = indent
    return found


def _find_key_line(lines: list[str], path: KeyPath) -> Optional[_KeyLine]:
    matches = [key_line for key_line in _key_lines(lines) if key_line.path == path]
    return matches[0] if len(matches) == 1 else None


def _block_end(lines: list[str], key_line: _KeyLine) -> int:
    """Index just past the key's own line and everything nested under it."""
    end = key_line.index + 1
    last_content = key_line.index
    while end < len(lines):
        stripped = lines[end].strip()
        indent = len(lines[end]) - len(lines[end].lstrip(" "))
        if stripped and indent <= key_line.indent:
            break
        if stripped:
            last_content = end
        end += 1
    return last_content + 1  # blank lines after the block stay


def _without_block(lines: list[str], key_line: _KeyLine) -> list[str]:
    start = key_line.index
    result = lines[:start] + lines[_block_end(lines, key_line) :]
    # Don't leave two blank lines meeting at the seam, or a blank line at the end.
    blank_before_seam = start > 0 and not result[start - 1].strip()
    blank_or_end_after_seam = start == len(result) or not result[start].strip()
    if blank_before_seam and blank_or_end_after_seam:
        del result[start - 1]
    return result


def _without_empty_parents(lines: list[str], section_path: KeyPath) -> list[str]:
    """Remove section key lines left with nothing (but comments) beneath them."""
    for depth in range(len(section_path), 0, -1):
        key_line = _find_key_line(lines, section_path[:depth])
        if key_line is None or _has_value_on_line(lines[key_line.index]):
            return lines
        children = lines[key_line.index + 1 : _block_end(lines, key_line)]
        if any(line.strip() and not line.strip().startswith("#") for line in children):
            return lines
        lines = _without_block(lines, key_line)
    return lines


def _has_value_on_line(line: str) -> bool:
    after_colon = line.split(":", 1)[1] if ":" in line else ""
    return bool(after_colon.split("#", 1)[0].strip())


def _renamed_key(line: str, old_key: str, new_key: str) -> str:
    match = YAML_KEY_LINE.match(line)
    if match is None:
        return line
    start, end = match.span("key")
    return line[:start] + new_key + line[end:]


def _exists(config: dict[str, Any], path: KeyPath) -> bool:
    section = _section(config, path[:-1])
    return section is not None and path[-1] in section
