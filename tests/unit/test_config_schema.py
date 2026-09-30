"""Config lockstep: DEFAULT_CONFIG and sonne/schemas/sonne.schema.json agree.

CLAUDE.md requires config keys to change together in DEFAULT_CONFIG, the
schema, README and CHANGELOG. These tests pin the first two against each
other and against the bundled site configs.
"""

import json
from pathlib import Path

import pytest
import yaml

from sonne.core.config import DEFAULT_CONFIG
from sonne.core.deprecations import DEPRECATED_CONFIG_KEYS, REMOVED_CONFIG_KEYS

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((REPO_ROOT / "sonne" / "schemas" / "sonne.schema.json").read_text("utf-8"))

# Schema keys that intentionally have no DEFAULT_CONFIG entry.
DERIVED_DEFAULTS = {
    # Unset means "the smallest of images.sizes"; no fixed default can say that.
    "images.dither_sizes",
}
RETIRED_KEYS = {".".join(path) for path in DEPRECATED_CONFIG_KEYS} | {
    ".".join(path) for path in REMOVED_CONFIG_KEYS
}
UNUSED_BUT_DOCUMENTED = {
    # No effect; slated for removal (docs/plans/08-dead-config-keys.md).
    "images.grayscale_before_dither",
}
TEMPLATE_SPECIFIC = {
    # Site data consumed by bundled templates/scripts, not by Sonne itself.
    "site.nav",
    "site.footer",
    "site.footer.text",
    "site.footer.links",
    "site.weather",
    "solar",
}
EXEMPT_FROM_DEFAULTS = DERIVED_DEFAULTS | RETIRED_KEYS | UNUSED_BUT_DOCUMENTED | TEMPLATE_SPECIFIC


def resolve(node):
    if "$ref" in node:
        return SCHEMA["definitions"][node["$ref"].split("/")[-1]]
    object_options = [option for option in node.get("oneOf", []) if option.get("type") == "object"]
    return object_options[0] if object_options else node


def schema_properties(node=SCHEMA, prefix=""):
    """{dotted key: schema node} for every object property, following $ref/oneOf."""
    found = {}
    for key, sub in resolve(node).get("properties", {}).items():
        dotted = prefix + key
        found[dotted] = resolve(sub)
        found.update(schema_properties(sub, dotted + "."))
    return found


def default_config_values(mapping=DEFAULT_CONFIG, prefix=""):
    """{dotted key: value} for every key in DEFAULT_CONFIG, sections included."""
    found = {}
    for key, value in mapping.items():
        dotted = prefix + key
        found[dotted] = value
        if isinstance(value, dict) and value:
            found.update(default_config_values(value, dotted + "."))
    return found


SCHEMA_KEYS = schema_properties()
DEFAULT_KEYS = default_config_values()


def unknown_keys(data, node=SCHEMA, prefix=""):
    """Dotted keys in a config mapping that the schema does not describe."""
    node = resolve(node)
    unknown = []
    for key, value in data.items():
        sub = node.get("properties", {}).get(key)
        if sub is None:
            if node.get("additionalProperties") in (None, False):
                unknown.append(prefix + key)
            continue
        if isinstance(value, dict):
            unknown += unknown_keys(value, sub, prefix + key + ".")
    return unknown


class TestDefaultsMatchSchema:
    @pytest.mark.parametrize("key", sorted(DEFAULT_KEYS))
    def test_every_default_key_is_documented(self, key):
        assert key in SCHEMA_KEYS

    @pytest.mark.parametrize(
        "key", sorted(k for k in DEFAULT_KEYS if "default" in SCHEMA_KEYS.get(k, {}))
    )
    def test_schema_default_equals_default_config(self, key):
        assert SCHEMA_KEYS[key]["default"] == DEFAULT_KEYS[key]

    @pytest.mark.parametrize("key", sorted(set(SCHEMA_KEYS) - EXEMPT_FROM_DEFAULTS))
    def test_every_documented_key_has_a_default(self, key):
        assert key in DEFAULT_KEYS

    @pytest.mark.parametrize("key", sorted(RETIRED_KEYS))
    def test_retired_keys_have_no_default(self, key):
        assert key not in DEFAULT_KEYS


class TestBundledConfigsMatchSchema:
    @pytest.mark.parametrize(
        "config_path",
        sorted(
            list((REPO_ROOT / "sonne" / "templates").glob("*/sonne.yaml"))
            + list((REPO_ROOT / "sonne" / "examples").glob("*/sonne.yaml"))
        ),
        ids=lambda path: path.parent.name,
    )
    def test_bundled_config_uses_only_documented_keys(self, config_path):
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

        assert unknown_keys(config) == []
