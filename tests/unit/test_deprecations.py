"""Config key deprecation shims: renames alias, removed keys drop, warn once."""

import logging

import pytest

import sonne.core.deprecations as deprecations
from sonne.core.deprecations import apply_config_deprecations


@pytest.fixture(autouse=True)
def fresh_warning_state(monkeypatch):
    monkeypatch.setattr(deprecations, "_warned", set())


def deprecation_warnings(caplog, key):
    return [r for r in caplog.records if r.levelno == logging.WARNING and key in r.message]


class TestRenamedKeys:
    def test_old_key_moves_to_new_key(self):
        user_config = {"images": {"max_workers": 2}}

        with pytest.warns(DeprecationWarning):
            apply_config_deprecations(user_config)

        assert user_config == {"images": {"parallel_workers": 2}}

    def test_explicit_new_key_wins_over_old(self):
        user_config = {"images": {"max_workers": 2, "parallel_workers": 8}}

        with pytest.warns(DeprecationWarning):
            apply_config_deprecations(user_config)

        assert user_config == {"images": {"parallel_workers": 8}}

    def test_warns_once_per_process(self, caplog):
        with caplog.at_level(logging.WARNING, logger="sonne"), pytest.warns(DeprecationWarning):
            apply_config_deprecations({"images": {"max_workers": 2}})
            apply_config_deprecations({"images": {"max_workers": 3}})

        assert len(deprecation_warnings(caplog, "images.max_workers")) == 1

    def test_non_mapping_section_is_ignored(self):
        user_config = {"images": "fast"}

        apply_config_deprecations(user_config)

        assert user_config == {"images": "fast"}


class TestRemovedKeys:
    def test_removed_key_is_dropped_with_guidance(self, caplog):
        user_config = {"security": {"allow_embedded_python": True, "csp": {}}}

        with caplog.at_level(logging.WARNING, logger="sonne"), pytest.warns(DeprecationWarning):
            apply_config_deprecations(user_config)

        assert user_config == {"security": {"csp": {}}}
        [warning] = deprecation_warnings(caplog, "security.allow_embedded_python")
        assert "no longer exists" in warning.message
