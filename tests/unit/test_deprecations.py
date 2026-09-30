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
        user_config = {"security": {"allow_embedded_python": True}, "site": {"title": "T"}}

        with caplog.at_level(logging.WARNING, logger="sonne"), pytest.warns(DeprecationWarning):
            apply_config_deprecations(user_config)

        assert user_config == {"security": {}, "site": {"title": "T"}}
        [warning] = deprecation_warnings(caplog, "security.allow_embedded_python")
        assert "no longer exists" in warning.message


class TestNoEffectKeys:
    @pytest.mark.parametrize(
        "section, key",
        [
            ("build", "incremental"),
            ("build", "show_progress"),
            ("build", "statistics"),
            ("security", "csp"),
        ],
    )
    def test_no_effect_key_warns_once_and_is_dropped(self, caplog, section, key):
        with caplog.at_level(logging.WARNING, logger="sonne"), pytest.warns(DeprecationWarning):
            first = {section: {key: True, "kept": 1}}
            apply_config_deprecations(first)
            apply_config_deprecations({section: {key: False}})

        assert first == {section: {"kept": 1}}
        [warning] = deprecation_warnings(caplog, f"'{section}.{key}'")
        assert "has no effect and will be removed" in warning.message

    def test_migrate_config_reports_changes_without_warning(self, caplog):
        user_config = {"images": {"max_workers": 2}, "build": {"statistics": True}}

        with caplog.at_level(logging.WARNING, logger="sonne"):
            changes = deprecations.migrate_config(user_config)

        assert user_config == {"images": {"parallel_workers": 2}, "build": {}}
        assert [(c.path, c.new_path) for c in changes] == [
            (("images", "max_workers"), ("images", "parallel_workers")),
            (("build", "statistics"), None),
        ]
        assert caplog.records == []
